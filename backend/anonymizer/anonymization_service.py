# anonymization_service.py
import pandas as pd
import logging
import os
import uuid
import json
import base64
from datetime import datetime
from io import StringIO # Per leggere dati stringa da csv/json
from typing import Any, Dict, Tuple
import time

from google_pubsub_manager import get_pubsub_manager, Topics
from anonymizer import process_anonymization # Assicurati che process_anonymization accetti DataFrame

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configura le cartelle di output
# Queste cartelle sono ancora necessarie per i file temporanei intermedi
ANONYMIZED_DATA_FOLDER = 'anonymized_data'
PROCESSED_DATA_FOLDER = 'processed_data'
os.makedirs(ANONYMIZED_DATA_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_DATA_FOLDER, exist_ok=True)


class AnonymizationService:
    def __init__(self):
        self.pubsub_manager = get_pubsub_manager()
        # Il servizio di anonimizzazione si iscrive alle richieste di anonimizzazione
        self.pubsub_manager.subscribe(
            Topics.ANONYMIZATION_REQUESTS, 
            self.handle_anonymization_request
        )
        self._initialize_method_schemas() # Mantiene la validazione dei parametri

    def _initialize_method_schemas(self):
        # Mappa dei metodi di anonimizzazione e i loro schemi di parametri.
        # Questa parte rimane come nel tuo anonymization_service.py originale.
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
        """Validates anonymization parameters against the schema."""
        schema = self.method_schemas.get(method)
        if not schema:
            return False, f"Unknown anonymization method: {method}"

        try:
            for param_name, param_config in schema['parameters'].items():
                param_value = params.get(param_name)

                # Check if required (all params in schema are implicitly required unless 'default' is present)
                if param_value is None and 'default' not in param_config:
                    return False, f"Missing required parameter for {method}: {param_name}"

                # Type validation
                expected_type = param_config.get('type')
                if expected_type == 'int' and not isinstance(param_value, int):
                    try: # Tentativo di conversione se arriva da JSON stringa
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

                # Range validation
                if 'min' in param_config and param_value < param_config['min']:
                    return False, f"Parameter {param_name} must be at least {param_config['min']}"
                if 'max' in param_config and param_value > param_config['max']:
                    return False, f"Parameter {param_name} must be at most {param_config['max']}"
                if 'options' in param_config and param_value not in param_config['options']:
                    return False, f"Parameter {param_name} must be one of: {param_config['options']}"
            
            # Imposta valori di default per parametri mancanti
            for param_name, param_config in schema['parameters'].items():
                if param_name not in params:
                    params[param_name] = param_config.get('default')
            
            # Validazioni specifiche per metodo
            if method == 'l_diversity' and 'k' in params and 'l' in params:
                if params['l'] > params['k'] and params['k'] is not None and params['l'] is not None:
                    return False, "l-diversity parameter 'l' cannot be greater than 'k'"
            
            return True, ""
            
        except Exception as e:
            return False, f"Parameter validation error: {str(e)}"

    def start(self):
        logger.info("Starting Anonymization Service. Listening for messages...")
        # L'oggetto StreamingPullFuture gestisce il loop di ascolto
        # Il servizio deve rimanere in esecuzione per processare i messaggi
        try:
            while True:
                time.sleep(1) # Mantieni il thread principale attivo
        except KeyboardInterrupt:
            logger.info("Shutting down Anonymization Service...")
            self.pubsub_manager.close()

    def handle_anonymization_request(self, data: Dict[str, Any]):
        job_id = data.get('job_id')
        method = data.get('method')
        params = data.get('params', {})
        user_selections = data.get('user_selections', [])
        
        # Percorsi dei file temporanei passati dal messaggio
        processed_data_content_base64 = data.get('processed_data_content_base64')
        metadata_content_base64 = data.get('metadata_content_base64')

        logger.info(f"Anonymization Service: Processing request for job {job_id} using method {method}")

        try:
            # --- Validazione dei parametri ---
            is_valid, validation_error = self.validate_anonymization_params(method, params)
            if not is_valid:
                raise ValueError(f"Invalid anonymization parameters: {validation_error}")

            # --- Carica i dati analizzati e i metadati decodificandoli da Base64 ---
            if not processed_data_content_base64 or not metadata_content_base64:
                raise ValueError("Processed data or metadata content in Base64 is missing.")

            decoded_processed_data = base64.b64decode(processed_data_content_base64).decode('utf-8')
            decoded_metadata = base64.b64decode(metadata_content_base64).decode('utf-8')

            df = pd.read_csv(StringIO(decoded_processed_data))
            metadata_df = pd.read_json(StringIO(decoded_metadata), orient='records')

            # Prepara i metadati estesi in base alle selezioni utente
            extended_metadata_data = []
            for col_name in metadata_df['column_name']:
                col_info = next((item for item in user_selections if item['column_name'] == col_name), None)
                
                is_qi = col_info['is_quasi_identifier'] if col_info else False
                should_anon = col_info['should_anonymize'] if col_info else False # Default a False se non specificato

                extended_metadata_data.append({
                    'column_name': col_name,
                    'data_type': metadata_df[metadata_df['column_name'] == col_name]['data_type'].iloc[0],
                    'is_quasi_identifier': is_qi,
                    'should_anonymize': should_anon
                })
            
            extended_metadata_df = pd.DataFrame(extended_metadata_data)

            # Esegui l'anonimizzazione
            anonymized_df, error_anonymizer = process_anonymization(df, extended_metadata_df, method, params)
            
            if error_anonymizer:
                raise ValueError(f"Anonymization failed in core anonymizer: {error_anonymizer}")

            # --- Converti DataFrame in stringhe CSV e codificale in Base64 ---
            anonymized_csv_buffer = StringIO()
            anonymized_df.to_csv(anonymized_csv_buffer, index=False)
            anonymized_csv_content = anonymized_csv_buffer.getvalue()
            encoded_anonymized_csv = base64.b64encode(anonymized_csv_content.encode('utf-8')).decode('utf-8')

            anonymized_sample_csv_buffer = StringIO()
            anonymized_df.head(10).to_csv(anonymized_sample_csv_buffer, index=False)
            anonymized_sample_csv_content = anonymized_sample_csv_buffer.getvalue()
            encoded_anonymized_sample_csv = base64.b64encode(anonymized_sample_csv_content.encode('utf-8')).decode('utf-8')
            
            logger.info(f"Job {job_id}: Anonymization completed. Content encoded to Base64.")

            # --- Pulisci i file temporanei ---
            # Questi sono i file intermedi dal servizio di analisi, non quelli anonimizzati
            # Poiché non vengono più salvati su disco dal servizio di analisi, non c'è nulla da rimuovere qui.
            # Rimuovere i seguenti 'os.remove' se non si salvano più i file temporanei.
            # Esempio: Se 'processed_data_path' e 'metadata_path' fossero ancora percorsi, li rimuoveresti qui.
            # Ma ora sono contenuti Base64, quindi non ci sono file da rimuovere.
            # try:
            #     os.remove(processed_data_path)
            #     os.remove(metadata_path)
            #     logger.info(f"Job {job_id}: Cleaned up temporary files.")
            # except OSError as e:
            #     logger.warning(f"Job {job_id}: Error cleaning up temporary files: {e}")

            # Pubblica i risultati finali dell'anonimizzazione con i contenuti Base64
            self.pubsub_manager.publish(Topics.ANONYMIZATION_RESULTS, {
                'job_id': job_id,
                'status': 'completed',
                'anonymized_file_content_base64': encoded_anonymized_csv, # Contenuto Base64 del file completo
                'anonymized_sample_content_base64': encoded_anonymized_sample_csv, # Contenuto Base64 del sample
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

if __name__ == "__main__":
    service = AnonymizationService()
    service.start()