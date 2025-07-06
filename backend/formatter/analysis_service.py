import pandas as pd
import logging
import os
import json
import base64
from datetime import datetime
from io import StringIO, BytesIO
from flask import Flask, request
from typing import Any, Dict

from google_pubsub_manager import get_pubsub_manager, Topics
from dataAnalyzer import read_dataset_for_web, structure_dataset 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROCESSED_DATA_FOLDER = 'processed_data'
os.makedirs(PROCESSED_DATA_FOLDER, exist_ok=True)

app = Flask(__name__)

class AnalysisService:
    def __init__(self):
        self.pubsub_manager = get_pubsub_manager()

    def handle_data_upload(self, data: Dict[str, Any]):
        job_id = data.get('job_id')
        filename = data.get('filename')
        file_content_base64 = data.get('file_content_base64')

        logger.info(f"Analysis Service: Processing upload for job {job_id}, file {filename}")

        try:
            if not file_content_base64:
                raise ValueError("No file content received in Base64.")

            decoded_file_content = base64.b64decode(file_content_base64)
            file_stream = BytesIO(decoded_file_content)
            df = read_dataset_for_web(file_stream, filename)
            structured_df, metadata = structure_dataset(df)

            logger.info(f"Job {job_id}: Data structured. Columns: {structured_df.columns.tolist()}")

            processed_csv_buffer = StringIO()
            structured_df.to_csv(processed_csv_buffer, index=False)
            processed_csv_content = processed_csv_buffer.getvalue()
            encoded_processed_csv = base64.b64encode(processed_csv_content.encode('utf-8')).decode('utf-8')

            metadata_json_buffer = StringIO()
            metadata.to_json(metadata_json_buffer, orient='records', indent=4)
            metadata_json_content = metadata_json_buffer.getvalue()
            encoded_metadata_json = base64.b64encode(metadata_json_content.encode('utf-8')).decode('utf-8')

            logger.info(f"Job {job_id}: Processed data and metadata encoded to Base64.")

            self.pubsub_manager.publish(Topics.ANALYSIS_RESULTS, {
                'job_id': job_id,
                'status': 'analyzed',
                'processed_data_content_base64': encoded_processed_csv,
                'metadata_content_base64': encoded_metadata_json,
                'dataset_info': {
                    'rows': len(structured_df),
                    'columns': len(structured_df.columns),
                    'column_types': metadata.groupby('data_type').size().to_dict()
                },
                'analyzed_at': datetime.now().isoformat()
            }, attributes={'job_id': job_id})

        except Exception as e:
            logger.error(f"Analysis Service: Error processing job {job_id}: {e}", exc_info=True)
            self.pubsub_manager.publish(Topics.ERROR_NOTIFICATIONS, {
                'job_id': job_id,
                'stage': 'analysis',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }, attributes={'job_id': job_id})

service = AnalysisService()

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
        service.handle_data_upload(data)
    except Exception as e:
        logger.error(f"Failed to process incoming Pub/Sub push: {e}", exc_info=True)
        return 'Bad Request', 400
    return ('', 204)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))