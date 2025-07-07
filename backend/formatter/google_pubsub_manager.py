# google_pubsub_manager.py
# This library is general purpose for all of the backend services, all the topics are setted via enviroments variables, if not specified on the Terraform, the call would be made to 'None' and would fail

import os
import json
import logging
from typing import Dict, Any, Callable, Optional
from google.cloud import pubsub_v1
import uuid
from datetime import datetime
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurazione del progetto Google Cloud
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT_ID')
if not PROJECT_ID:
    logger.error("GOOGLE_CLOUD_PROJECT_ID environment variable not set. Please set it.")
    raise ValueError("GOOGLE_CLOUD_PROJECT_ID environment variable not set.")

# Topics
class Topics:
    DATA_UPLOAD_REQUESTS = os.environ.get('FORMATTER_INPUT_TOPIC')
    ANALYSIS_RESULTS = os.environ.get('FORMATTER_OUTPUT_TOPIC')
    ANONYMIZATION_REQUESTS = os.environ.get('ANONYMIZER_INPUT_TOPIC')
    ANONYMIZATION_RESULTS = os.environ.get('ANONYMIZER_OUTPUT_TOPIC')
    ERROR_NOTIFICATIONS = os.environ.get('ERROR_INFORMATIONS_TOPIC')

class GooglePubSubManager:
    def __init__(self):
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()
        self.subscriptions: Dict[str, str] = {}
        logger.info(f"Initialized Google Cloud Pub/Sub Manager for project: {PROJECT_ID}")

    def _full_topic_name(self, topic_id: str) -> str:
        return self.publisher.topic_path(PROJECT_ID, topic_id)

    def _full_subscription_name(self, subscription_id: str) -> str:
        return self.subscriber.subscription_path(PROJECT_ID, subscription_id)

    def publish(self, topic_id: str, data: Dict[str, Any], attributes: Optional[Dict[str, str]] = None):
        """Pubblica un messaggio su un topic Pub/Sub."""
        topic_path = self._full_topic_name(topic_id)
        
        # Aggiungi un ID unico e timestamp al messaggio
        message_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Aggiungi meta-informazioni al payload del messaggio
        payload = {
            "message_id": message_id,
            "timestamp": timestamp,
            "data": data
        }

        data_json = json.dumps(payload).encode("utf-8")
        
        if attributes is None:
            attributes = {}
        
        # Esempio di attributo per un job_id, se presente nei dati principali
        if 'job_id' in data:
            attributes['job_id'] = str(data['job_id'])
        
        future = self.publisher.publish(topic_path, data_json, **attributes)
        future.add_done_callback(lambda future: logger.info(
            f"Published message {message_id} to {topic_id} (job_id: {attributes.get('job_id', 'N/A')}). Result: {future.result()}"
        ))
        
        return message_id

    def close(self):
        """Chiude i client Pub/Sub."""
        self.publisher.api.transport.close()
        self.subscriber.api.transport.close()
        logger.info("Pub/Sub clients closed.")

# Singleton instance per il manager
_pubsub_manager_instance = None

def get_pubsub_manager() -> GooglePubSubManager:
    global _pubsub_manager_instance
    if _pubsub_manager_instance is None:
        _pubsub_manager_instance = GooglePubSubManager()
    return _pubsub_manager_instance