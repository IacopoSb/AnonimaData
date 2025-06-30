import pandas as pd
import logging
import os
import json
from datetime import datetime
from pathlib import Path

from message_broker import get_broker, Topics, Message
from dataAnalyzer import read_dataset, structure_dataset

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AnalysisService:
    """
    Servizio che si occupa dell'analisi dei dataset caricati.
    Subscriber del topic 'data_uploaded'.
    """
    
    def __init__(self):
        self.broker = get_broker()
        self.broker.subscribe(Topics.DATA_UPLOADED, self.handle_data_upload)
        
    def start(self):
        """Avvia il servizio di analisi"""
        logger.info("Starting Analysis Service...")
        self.broker.start_listening()
        logger.info("Analysis Service is listening for messages...")
        
        try:
            # Mantieni il servizio in esecuzione
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down Analysis Service...")
            self.broker.stop_listening()
    
    def handle_data_upload(self, message: Message):
        """
        Gestisce l'evento di caricamento dati.
        Analizza il dataset e pubblica i risultati.
        """
        try:
            logger.info(f"Processing data upload: {message.id}")
            
            # Estrai i dati dal messaggio
            job_id = message.data.get('job_id')
            filename = message.data.get('filename')
            file_path = message.data.get('file_path')
            file_extension = message.data.get('file_extension')
            
            if not all([job_id, filename, file_path, file_extension]):
                raise ValueError("Missing required data in message")
            
            # Aggiorna lo status del job
            self.broker.set_job_status(job_id, 'analyzing', {
                'stage': 'reading_file',
                'filename': filename
            })
            
            # Leggi il dataset
            logger.info(f"Reading dataset: {file_path}")
            df = read_dataset(file_path)
            
            # Aggiorna lo status
            self.broker.set_job_status(job_id, 'analyzing', {
                'stage': 'analyzing_structure',
                'filename': filename,
                'rows': len(df),
                'columns': len(df.columns)
            })
            
            # Analizza la struttura del dataset
            logger.info(f"Analyzing dataset structure for job {job_id}")
            structured_df, metadata = structure_dataset(df)
            
            # Salva i metadati in un file temporaneo
            metadata_path = file_path.replace(file_extension, '_metadata.csv')
            metadata.to_csv(metadata_path, index=False)
            
            # Salva anche il dataset strutturato se necessario
            structured_data_path = file_path.replace(file_extension, '_structured.csv')
            structured_df.to_csv(structured_data_path, index=False)
            
            # Converti i metadati in formato JSON per il messaggio
            metadata_json = metadata.to_dict(orient='records')
            
            # Aggiorna lo status finale dell'analisi
            analysis_data = {
                'filename': filename,
                'file_path': file_path,
                'structured_data_path': structured_data_path,
                'metadata_path': metadata_path,
                'metadata': metadata_json,
                'rows': len(structured_df),
                'columns': len(structured_df.columns),
                'analyzed_at': datetime.now().isoformat()
            }
            
            self.broker.set_job_status(job_id, 'analyzed', analysis_data)
            
            # Pubblica i risultati dell'analisi
            analysis_message = {
                'job_id': job_id,
                'original_filename': filename,
                'file_path': file_path,
                'structured_data_path': structured_data_path,
                'metadata_path': metadata_path,
                'metadata': metadata_json,
                'dataset_info': {
                    'rows': len(structured_df),
                    'columns': len(structured_df.columns),
                    'column_types': metadata.groupby('data_type').size().to_dict()
                },
                'analyzed_at': datetime.now().isoformat()
            }
            
            # Non pubblichiamo automaticamente su DATA_ANALYZED perché aspettiamo
            # la richiesta di anonimizzazione dall'utente con i parametri
            
            logger.info(f"Analysis completed for job {job_id}")
            
        except Exception as e:
            logger.error(f"Error processing data upload {message.id}: {e}")
            
            # Aggiorna lo status con errore
            if 'job_id' in locals():
                self.broker.set_job_status(job_id, 'error', {
                    'error': str(e),
                    'stage': 'analysis_failed',
                    'error_at': datetime.now().isoformat()
                })
                
                # Pubblica evento di errore
                error_message = {
                    'job_id': job_id,
                    'stage': 'analysis',
                    'error': str(e),
                    'original_message_id': message.id
                }
                
                self.broker.publish(Topics.ERROR_OCCURRED, error_message)

def main():
    """Avvia il servizio di analisi"""
    service = AnalysisService()
    service.start()

if __name__ == "__main__":
    main()