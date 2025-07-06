# analysis_service.py
import pandas as pd
import logging
import os
import json
import base64 # Importa base64 per la codifica
from datetime import datetime
from io import StringIO, BytesIO # Per leggere da base64 e scrivere a stringa
import threading
import time
from typing import Any, Dict

from google_pubsub_manager import get_pubsub_manager, Topics
# Assicurati che read_dataset_for_web ora accetti il contenuto in base64 e lo decodifichi internamente
from dataAnalyzer import read_dataset_for_web, structure_dataset 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Le cartelle di output non sono più strettamente necessarie per i dati processati e i metadati
# perché non vengono salvati su disco qui per essere passati ad altri servizi,
# ma potrebbero essere ancora utili per logging o debug locale.
PROCESSED_DATA_FOLDER = 'processed_data'
os.makedirs(PROCESSED_DATA_FOLDER, exist_ok=True)


class AnalysisService:
    def __init__(self):
        self.pubsub_manager = get_pubsub_manager()
        # Il servizio di analisi si iscrive alle richieste di upload
        self.pubsub_manager.subscribe(
            Topics.DATA_UPLOAD_REQUESTS, 
            self.handle_data_upload
        )
        
    def start(self):
        logger.info("Starting Analysis Service. Listening for messages...")
        # L'oggetto StreamingPullFuture gestisce il loop di ascolto
        # Il servizio deve rimanere in esecuzione per processare i messaggi
        try:
            while True:
                time.sleep(1) # Mantieni il thread principale attivo
        except KeyboardInterrupt:
            logger.info("Shutting down Analysis Service...")
            self.pubsub_manager.close()
    
    def handle_data_upload(self, data: Dict[str, Any]):
        job_id = data.get('job_id')
        filename = data.get('filename')
        file_content_base64 = data.get('file_content_base64') # Contenuto Base64 del file caricato

        logger.info(f"Analysis Service: Processing upload for job {job_id}, file {filename}")

        try:
            if not file_content_base64:
                raise ValueError("No file content received in Base64.")

            # Decodifica il contenuto Base64
            decoded_file_content = base64.b64decode(file_content_base64)
            
            # Utilizza BytesIO per passare i dati a read_dataset_for_web
            # read_dataset_for_web gestirà la stream in base all'estensione del filename
            file_stream = BytesIO(decoded_file_content)

            # Leggi il dataset dalla stream
            df = read_dataset_for_web(file_stream, filename)
            
            # Struttura il dataset
            structured_df, metadata = structure_dataset(df)

            logger.info(f"Job {job_id}: Data structured. Columns: {structured_df.columns.tolist()}")
            
            # --- Converti DataFrame in stringa CSV e metadati in stringa JSON, poi codifica in Base64 ---
            
            # Dati processati (CSV)
            processed_csv_buffer = StringIO()
            structured_df.to_csv(processed_csv_buffer, index=False)
            processed_csv_content = processed_csv_buffer.getvalue()
            encoded_processed_csv = base64.b64encode(processed_csv_content.encode('utf-8')).decode('utf-8')

            # Metadati (JSON)
            metadata_json_buffer = StringIO()
            metadata.to_json(metadata_json_buffer, orient='records', indent=4)
            metadata_json_content = metadata_json_buffer.getvalue()
            encoded_metadata_json = base64.b64encode(metadata_json_content.encode('utf-8')).decode('utf-8')

            logger.info(f"Job {job_id}: Processed data and metadata encoded to Base64.")
            
            # Pubblica i risultati dell'analisi con i contenuti Base64
            self.pubsub_manager.publish(Topics.ANALYSIS_RESULTS, {
                'job_id': job_id,
                'status': 'analyzed',
                'processed_data_content_base64': encoded_processed_csv, # Contenuto Base64 del CSV processato
                'metadata_content_base64': encoded_metadata_json,     # Contenuto Base64 del JSON metadata
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

if __name__ == "__main__":
    service = AnalysisService()
    service.start()