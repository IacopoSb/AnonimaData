from flask import Flask, request, jsonify, render_template, send_file
import pandas as pd
import os
from io import BytesIO, StringIO
import logging
import uuid
import json
from datetime import datetime
from pathlib import Path

# Importa il message broker e le classi di analisi
from message_broker import get_broker, Topics
from dataAnalyzer import read_dataset_for_web, structure_dataset

# Configura il logging per Flask
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ANONYMIZED_FOLDER'] = 'anonymized_data'

# Crea le cartelle se non esistono
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['ANONYMIZED_FOLDER'], exist_ok=True)

# Inizializza il message broker
broker = get_broker()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_and_analyze', methods=['POST'])
def upload_and_analyze():
    """
    Carica il file e pubblica un evento per l'analisi.
    Non fa più l'analisi sincrona.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file:
        try:
            # Genera un job ID unico
            job_id = str(uuid.uuid4())
            
            filename = file.filename
            file_extension = os.path.splitext(filename)[1].lower()
            
            # Salva il file temporaneamente
            temp_input_filename = os.path.join(
                app.config['UPLOAD_FOLDER'], 
                f"{job_id}_{filename}"
            )
            
            # Leggi e salva il contenuto del file
            if file_extension in ['.csv', '.txt', '.json']:
                file_content = file.stream.read().decode('utf-8')
                with open(temp_input_filename, 'w', encoding='utf-8') as f:
                    f.write(file_content)
            elif file_extension in ['.xlsx', '.xls']:
                file_content = file.stream.read()
                with open(temp_input_filename, 'wb') as f:
                    f.write(file_content)
            else:
                return jsonify({"error": f"Unsupported file extension: {file_extension}"}), 400

            # Imposta lo status iniziale del job
            broker.set_job_status(job_id, 'uploaded', {
                'filename': filename,
                'file_path': temp_input_filename,
                'file_extension': file_extension
            })
            
            # Pubblica evento per l'analisi
            message_data = {
                'job_id': job_id,
                'filename': filename,
                'file_path': temp_input_filename,
                'file_extension': file_extension,
                'uploaded_at': datetime.now().isoformat()
            }
            
            broker.publish(Topics.DATA_UPLOADED, message_data)
            
            logger.info(f"File {filename} caricato con job_id: {job_id}")
            
            return jsonify({
                "message": "File uploaded successfully, analysis started",
                "job_id": job_id,
                "status": "uploaded"
            }), 200
            
        except Exception as e:
            logger.error(f"Error during upload: {e}")
            return jsonify({"error": str(e)}), 500

@app.route('/job_status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Restituisce lo status di un job"""
    try:
        status = broker.get_job_status(job_id)
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/request_anonymization', methods=['POST'])
def request_anonymization():
    """
    Richiede l'anonimizzazione di un dataset già analizzato.
    Pubblica un evento per il servizio di anonimizzazione.
    """
    data = request.get_json()
    
    job_id = data.get('job_id')
    method = data.get('method')
    params = data.get('params', {})
    user_selections = data.get('user_selections', [])

    if not job_id or not method:
        return jsonify({"error": "Missing required parameters"}), 400

    try:
        # Verifica che il job esista e sia stato analizzato
        job_status = broker.get_job_status(job_id)
        
        if job_status.get('status') != 'analyzed':
            return jsonify({
                "error": f"Job not ready for anonymization. Current status: {job_status.get('status')}"
            }), 400
        
        # Aggiorna lo status del job
        broker.set_job_status(job_id, 'anonymization_requested', {
            'method': method,
            'params': params,
            'user_selections': user_selections
        })
        
        # Pubblica evento per l'anonimizzazione
        message_data = {
            'job_id': job_id,
            'method': method,
            'params': params,
            'user_selections': user_selections,
            'requested_at': datetime.now().isoformat()
        }
        
        # Recupera i dati del file dall'analisi precedente
        job_data = job_status.get('data', {})
        message_data.update(job_data)
        
        broker.publish(Topics.DATA_ANALYZED, message_data)
        
        logger.info(f"Anonymization requested for job_id: {job_id}")
        
        return jsonify({
            "message": "Anonymization request submitted",
            "job_id": job_id,
            "status": "anonymization_requested"
        }), 200
        
    except Exception as e:
        logger.error(f"Error requesting anonymization: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/download/<job_id>', methods=['GET'])
def download_file(job_id):
    """Download del file anonimizzato"""
    try:
        # Verifica lo status del job
        job_status = broker.get_job_status(job_id)
        
        if job_status.get('status') != 'completed':
            return jsonify({
                "error": f"File not ready. Current status: {job_status.get('status')}"
            }), 400
        
        # Recupera il percorso del file anonimizzato
        file_path = job_status.get('data', {}).get('anonymized_file_path')
        
        if not file_path or not os.path.exists(file_path):
            return jsonify({"error": "Anonymized file not found"}), 404
        
        return send_file(file_path, as_attachment=True)
        
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/download_sample/<job_id>', methods=['GET'])
def download_sample(job_id):
    """Download del sample del file anonimizzato"""
    try:
        job_status = broker.get_job_status(job_id)
        
        if job_status.get('status') != 'completed':
            return jsonify({
                "error": f"File not ready. Current status: {job_status.get('status')}"
            }), 400
        
        sample_path = job_status.get('data', {}).get('sample_file_path')
        
        if not sample_path or not os.path.exists(sample_path):
            return jsonify({"error": "Sample file not found"}), 404
        
        return send_file(sample_path, as_attachment=True)
        
    except Exception as e:
        logger.error(f"Error downloading sample: {e}")
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # Avvia il message broker listener (se necessario per i callback)
    try:
        broker.start_listening()
        logger.info("Message broker listener started")
    except Exception as e:
        logger.error(f"Could not start message broker: {e}")
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    finally:
        # Cleanup
        try:
            broker.stop_listening()
        except:
            pass