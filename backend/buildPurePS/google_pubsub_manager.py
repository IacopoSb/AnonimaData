# google_pubsub_manager.py
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
    DATA_UPLOAD_REQUESTS = "data-upload-requests"
    ANALYSIS_RESULTS = "analysis-results"
    ANONYMIZATION_REQUESTS = "anonymization-requests"
    ANONYMIZATION_RESULTS = "anonymization-results"
    ERROR_NOTIFICATIONS = "error-notifications"

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

    def subscribe(self, topic_id: str, subscription_id: str, callback: Callable[[Dict[str, Any]], None]):
        """Si sottoscrive a un topic e gestisce i messaggi tramite callback."""
        topic_path = self._full_topic_name(topic_id)
        subscription_path = self._full_subscription_name(subscription_id)
        
        # Tenta di creare la subscription se non esiste (utile per il primo avvio)
        try:
            self.subscriber.create_subscription(name=subscription_path, topic=topic_path)
            logger.info(f"Subscription '{subscription_id}' created on topic '{topic_id}'.")
        except Exception as e:
            if "AlreadyExists" in str(e):
                logger.info(f"Subscription '{subscription_id}' already exists.")
            else:
                logger.error(f"Error creating subscription '{subscription_id}': {e}")
                raise

        def _callback_wrapper(message: pubsub_v1.subscriber.message.Message):
            try:
                # Decodifica il messaggio
                decoded_data = json.loads(message.data.decode("utf-8"))
                logger.info(f"Received message {decoded_data.get('message_id')} on {topic_id} (job_id: {message.attributes.get('job_id', 'N/A')})")
                callback(decoded_data['data']) # Passa solo il payload 'data' alla callback
                message.ack() # Riconosce il messaggio dopo l'elaborazione
            except json.JSONDecodeError as e:
                logger.error(f"JSON Decode Error in message: {e}. Message data: {message.data.decode('utf-8', errors='ignore')}")
                message.nack() # Non riconosce il messaggio per rielaborarlo o metterlo in coda di dead-letter
            except Exception as e:
                logger.error(f"Error processing message {message.message_id} on {topic_id}: {e}")
                message.nack() # Non riconosce il messaggio

        self.subscriptions[subscription_id] = subscription_path
        streaming_pull_future = self.subscriber.subscribe(subscription_path, callback=_callback_wrapper)
        logger.info(f"Listening for messages on {subscription_path}...")
        return streaming_pull_future

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

if __name__ == "__main__":
    # Esempio di utilizzo e test
    # Assicurati che GOOGLE_CLOUD_PROJECT_ID sia settato nell'ambiente
    # e di aver creato i topic 'test-topic-in' e 'test-topic-out'
    # gcloud pubsub topics create test-topic-in
    # gcloud pubsub topics create test-topic-out
    # gcloud pubsub subscriptions create test-sub-in --topic test-topic-in
    # gcloud pubsub subscriptions create test-sub-out --topic test-topic-out

    manager = get_pubsub_manager()

    def test_in_callback(data: Dict[str, Any]):
        job_id = data.get('job_id')
        print(f"[{datetime.now().isoformat()}] Test Subscriber IN received: {data} for job {job_id}")
        manager.publish(Topics.ANALYSIS_RESULTS, {'job_id': job_id, 'status': 'processed', 'result': 'data_analyzed_test'})

    def test_out_callback(data: Dict[str, Any]):
        job_id = data.get('job_id')
        print(f"[{datetime.now().isoformat()}] Test Subscriber OUT received: {data} for job {job_id}")

    # Iscrivi i callback ai rispettivi topic
    in_future = manager.subscribe(Topics.DATA_UPLOAD_REQUESTS, "test-in-sub", test_in_callback)
    out_future = manager.subscribe(Topics.ANALYSIS_RESULTS, "test-out-sub", test_out_callback)

    print("Test: Publishing a message to data-upload-requests...")
    test_job_id = str(uuid.uuid4())
    manager.publish(Topics.DATA_UPLOAD_REQUESTS, {'job_id': test_job_id, 'file_content': 'some,csv,data'})

    try:
        # Mantieni l'applicazione in ascolto
        print("Listening for messages... Press Ctrl+C to exit.")
        while True:
            time.sleep(60) # Sleep per non consumare CPU
    except KeyboardInterrupt:
        print("Shutting down...")
        in_future.cancel()
        out_future.cancel()
        manager.close()