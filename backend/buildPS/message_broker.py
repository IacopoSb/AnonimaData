import redis
import json
import logging
import threading
import time
from typing import Dict, Callable, Any
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Message:
    """Rappresenta un messaggio nel sistema pub/sub"""
    id: str
    topic: str
    data: Dict[str, Any]
    timestamp: str
    
    def to_dict(self):
        return {
            'id': self.id,
            'topic': self.topic,
            'data': self.data,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data['id'],
            topic=data['topic'],
            data=data['data'],
            timestamp=data['timestamp']
        )

class MessageBroker:
    """Message Broker basato su Redis per gestire pub/sub"""
    
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0):
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        self.pubsub = self.redis_client.pubsub()
        self.subscribers: Dict[str, Callable] = {}
        self.running = False
        self.listener_thread = None
        
        # Test connection
        try:
            self.redis_client.ping()
            logger.info("Connesso a Redis")
        except redis.ConnectionError:
            logger.error("Impossibile connettersi a Redis")
            raise
    
    def publish(self, topic: str, message_data: Dict[str, Any], message_id: str = None) -> str:
        """Pubblica un messaggio su un topic"""
        if message_id is None:
            message_id = f"{topic}_{int(time.time() * 1000)}"
        
        message = Message(
            id=message_id,
            topic=topic,
            data=message_data,
            timestamp=datetime.now().isoformat()
        )
        
        try:
            # Pubblica il messaggio
            self.redis_client.publish(topic, json.dumps(message.to_dict()))
            
            # Salva anche in una lista per persistenza (opzionale)
            self.redis_client.lpush(f"messages:{topic}", json.dumps(message.to_dict()))
            self.redis_client.ltrim(f"messages:{topic}", 0, 999)  # Mantieni solo gli ultimi 1000 messaggi
            
            logger.info(f"Messaggio pubblicato su {topic}: {message_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"Errore nella pubblicazione del messaggio: {e}")
            raise
    
    def subscribe(self, topic: str, callback: Callable[[Message], None]):
        """Iscrive un callback a un topic"""
        self.subscribers[topic] = callback
        self.pubsub.subscribe(topic)
        logger.info(f"Iscritto al topic: {topic}")
    
    def start_listening(self):
        """Avvia il listener per i messaggi in arrivo"""
        if self.running:
            logger.warning("Il listener è già in esecuzione")
            return
        
        self.running = True
        self.listener_thread = threading.Thread(target=self._listen_loop)
        self.listener_thread.daemon = True
        self.listener_thread.start()
        logger.info("Listener avviato")
    
    def stop_listening(self):
        """Ferma il listener"""
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=5)
        self.pubsub.close()
        logger.info("Listener fermato")
    
    def _listen_loop(self):
        """Loop principale per ascoltare i messaggi"""
        try:
            for message in self.pubsub.listen():
                if not self.running:
                    break
                
                if message['type'] == 'message':
                    try:
                        # Deserializza il messaggio
                        message_data = json.loads(message['data'])
                        msg_obj = Message.from_dict(message_data)
                        
                        # Chiama il callback appropriato
                        topic = message['channel']
                        if topic in self.subscribers:
                            callback = self.subscribers[topic]
                            threading.Thread(
                                target=self._safe_callback,
                                args=(callback, msg_obj)
                            ).start()
                        else:
                            logger.warning(f"Nessun subscriber per il topic: {topic}")
                            
                    except Exception as e:
                        logger.error(f"Errore nel processare il messaggio: {e}")
                        
        except Exception as e:
            logger.error(f"Errore nel listener loop: {e}")
    
    def _safe_callback(self, callback: Callable, message: Message):
        """Esegue il callback in modo sicuro"""
        try:
            callback(message)
        except Exception as e:
            logger.error(f"Errore nel callback per il messaggio {message.id}: {e}")
    
    def get_message_history(self, topic: str, limit: int = 10) -> list:
        """Recupera la cronologia dei messaggi per un topic"""
        try:
            messages = self.redis_client.lrange(f"messages:{topic}", 0, limit - 1)
            return [json.loads(msg) for msg in messages]
        except Exception as e:
            logger.error(f"Errore nel recuperare la cronologia: {e}")
            return []
    
    def set_job_status(self, job_id: str, status: str, data: Dict[str, Any] = None):
        """Imposta lo status di un job"""
        job_data = {
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'data': data or {}
        }
        self.redis_client.setex(f"job:{job_id}", 3600, json.dumps(job_data))  # Expire dopo 1 ora
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Recupera lo status di un job"""
        try:
            data = self.redis_client.get(f"job:{job_id}")
            if data:
                return json.loads(data)
            return {'status': 'not_found'}
        except Exception as e:
            logger.error(f"Errore nel recuperare lo status del job {job_id}: {e}")
            return {'status': 'error', 'error': str(e)}

# Topics utilizzati nel sistema
class Topics:
    DATA_UPLOADED = "data_uploaded"
    DATA_ANALYZED = "data_analyzed"
    DATA_ANONYMIZED = "data_anonymized"
    JOB_STATUS_UPDATE = "job_status_update"
    ERROR_OCCURRED = "error_occurred"

# Singleton instance per il broker
_broker_instance = None

def get_broker() -> MessageBroker:
    """Restituisce l'istanza singleton del message broker"""
    global _broker_instance
    if _broker_instance is None:
        _broker_instance = MessageBroker()
    return _broker_instance

if __name__ == "__main__":
    # Test del message broker
    broker = MessageBroker()
    
    def test_callback(message: Message):
        print(f"Ricevuto messaggio: {message.id} su topic {message.topic}")
        print(f"Dati: {message.data}")
    
    # Test subscription
    broker.subscribe("test_topic", test_callback)
    broker.start_listening()
    
    # Test publication
    broker.publish("test_topic", {"test": "data", "number": 123})
    
    # Aspetta un po' per vedere il messaggio
    time.sleep(2)
    
    broker.stop_listening()