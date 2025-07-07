import pandas as pd
import logging
import os
import uuid
import json
import base64
from datetime import datetime
from io import StringIO
from typing import Any, Dict, Tuple
from flask import Flask, request

from google_pubsub_manager import get_pubsub_manager, Topics
from anonymizer import process_anonymization 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ANONYMIZED_DATA_FOLDER = 'anonymized_data'
PROCESSED_DATA_FOLDER = 'processed_data'
os.makedirs(ANONYMIZED_DATA_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_DATA_FOLDER, exist_ok=True)

app = Flask(__name__)

class AnonymizationService:
    def __init__(self):
        self.pubsub_manager = get_pubsub_manager()
        self._initialize_method_schemas()

    def _initialize_method_schemas(self):
        self.method_schemas = {
            'k_anonymity': {
                'parameters': {
                    'k': {'type': 'int', 'default': 3, 'min': 2, 'max': 100, 'description': 'Minimum group size for k-anonymity'}
                }
            },
            'l_diversity': {
                'parameters': {
                    'k': {'type': 'int', 'default': 3, 'min': 2, 'max': 100, 'description': 'Minimum group size for k-anonymity base'},
                    'l': {'type': 'int', 'default': 2, 'min': 2, 'description': 'Minimum distinct sensitive values in each group'}
                }
            },
            'differential_privacy': {
                'parameters': {
                    'epsilon': {'type': 'float', 'default': 1.0, 'min': 0.1, 'max': 10.0, 'description': 'Privacy budget (epsilon) for differential privacy'}
                }
            }
        }
        
    def validate_anonymization_params(self, method: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        schema = self.method_schemas.get(method)
        if not schema:
            return False, f"Unknown anonymization method: {method}"

        try:
            for param_name, param_config in schema['parameters'].items():
                param_value = params.get(param_name)
                if param_value is None and 'default' not in param_config:
                    return False, f"Missing required parameter for {method}: {param_name}"
                expected_type = param_config.get('type')
                if expected_type == 'int' and not isinstance(param_value, int):
                    try:
                        params[param_name] = int(param_value)
                        param_value = params[param_name]
                    except (ValueError, TypeError):
                        return False, f"Parameter {param_name} must be an integer."
                elif expected_type == 'float' and not isinstance(param_value, (int, float)):
                    try:
                        params[param_name] = float(param_value)
                        param_value = params[param_name]
                    except (ValueError, TypeError):
                        return False, f"Parameter {param_name} must be a float."
                if 'min' in param_config and param_value < param_config['min']:
                    return False, f"Parameter {param_name} must be at least {param_config['min']}"
                if 'max' in param_config and param_value > param_config['max']:
                    return False, f"Parameter {param_name} must be at most {param_config['max']}"
                if 'options' in param_config and param_value not in param_config['options']:
                    return False, f"Parameter {param_name} must be one of: {param_config['options']}"
            for param_name, param_config in schema['parameters'].items():
                if param_name not in params:
                    params[param_name] = param_config.get('default')
            if method == 'l_diversity' and 'k' in params and 'l' in params:
                if params['l'] > params['k'] and params['k'] is not None and params['l'] is not None:
                    return False, "l-diversity parameter 'l' cannot be greater than 'k'"
            return True, ""
        except Exception as e:
            return False, f"Parameter validation error: {str(e)}"

    def handle_anonymization_request(self, data: Dict[str, Any]):
        job_id = data.get('job_id')
        method = data.get('method')
        params = data.get('params', {})
        user_selections = data.get('user_selections', [])
        processed_data_content_base64 = data.get('processed_data_content_base64')
        metadata_content_base64 = data.get('metadata_content_base64')

        logger.info(f"Anonymization Service: Processing request for job {job_id} using method {method}")

        try:
            is_valid, validation_error = self.validate_anonymization_params(method, params)
            if not is_valid:
                raise ValueError(f"Invalid anonymization parameters: {validation_error}")
            if not processed_data_content_base64 or not metadata_content_base64:
                raise ValueError("Processed data or metadata content in Base64 is missing.")
            decoded_processed_data = base64.b64decode(processed_data_content_base64).decode('utf-8')
            decoded_metadata = base64.b64decode(metadata_content_base64).decode('utf-8')
            df = pd.read_csv(StringIO(decoded_processed_data))
            metadata_df = pd.read_json(StringIO(decoded_metadata), orient='records')

            extended_metadata_data = []
            for col_name in metadata_df['column_name']:
                col_info = next((item for item in user_selections if item['column_name'] == col_name), None)
                is_qi = col_info['is_quasi_identifier'] if col_info else False
                should_anon = col_info['should_anonymize'] if col_info else False
                extended_metadata_data.append({
                    'column_name': col_name,
                    'data_type': metadata_df[metadata_df['column_name'] == col_name]['data_type'].iloc[0],
                    'is_quasi_identifier': is_qi,
                    'should_anonymize': should_anon
                })
            extended_metadata_df = pd.DataFrame(extended_metadata_data)
            anonymized_df, error_anonymizer = process_anonymization(df, extended_metadata_df, method, params)
            if error_anonymizer:
                raise ValueError(f"Anonymization failed in core anonymizer: {error_anonymizer}")
            anonymized_csv_buffer = StringIO()
            anonymized_df.to_csv(anonymized_csv_buffer, index=False)
            anonymized_csv_content = anonymized_csv_buffer.getvalue()
            encoded_anonymized_csv = base64.b64encode(anonymized_csv_content.encode('utf-8')).decode('utf-8')
            anonymized_sample_csv_buffer = StringIO()
            anonymized_df.head(10).to_csv(anonymized_sample_csv_buffer, index=False)
            anonymized_sample_csv_content = anonymized_sample_csv_buffer.getvalue()
            encoded_anonymized_sample_csv = base64.b64encode(anonymized_sample_csv_content.encode('utf-8')).decode('utf-8')
            logger.info(f"Job {job_id}: Anonymization completed. Content encoded to Base64.")
            self.pubsub_manager.publish(Topics.ANONYMIZATION_RESULTS, {
                'job_id': job_id,
                'status': 'completed',
                'anonymized_file_content_base64': encoded_anonymized_csv,
                'anonymized_sample_content_base64': encoded_anonymized_sample_csv,
                'method_used': method,
                'params_used': params,
                'anonymized_at': datetime.now().isoformat()
            }, attributes={'job_id': job_id})
        except Exception as e:
            logger.error(f"Anonymization Service: Error processing job {job_id}: {e}", exc_info=True)
            self.pubsub_manager.publish(Topics.ERROR_NOTIFICATIONS, {
                'job_id': job_id,
                'stage': 'anonymization',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }, attributes={'job_id': job_id})

service = AnonymizationService()

@app.route("/", methods=["POST"])
def pubsub_push_handler():
    envelope = request.get_json()
    if not envelope or 'message' not in envelope:
        logger.error("Invalid Pub/Sub message format")
        return 'Bad Request', 400
    pubsub_message = envelope['message']
    try:
        payload = base64.b64decode(pubsub_message['data']).decode('utf-8')
        data = json.loads(payload)
        logger.info(f"Received Pub/Sub push: {data}")
        service.handle_anonymization_request(data.get('data'))  # From pub/sub json extract only the payload relevant for app use
    except Exception as e:
        logger.error(f"Failed to process incoming Pub/Sub push: {e}", exc_info=True)
        return 'Bad Request', 400
    return ('', 204)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))