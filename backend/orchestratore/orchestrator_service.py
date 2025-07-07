# orchestrator_service.py
from flask import Flask, request, jsonify, render_template, send_file
import pandas as pd
import os
from io import BytesIO, StringIO
import logging
import uuid
import json
import base64
from datetime import datetime
from typing import Any, Dict
from flask_cors import CORS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

from google_pubsub_manager import get_pubsub_manager, Topics
pubsub_manager = get_pubsub_manager()

try:
    from google_pubsub_manager import get_pubsub_manager, Topics
    pubsub_manager = get_pubsub_manager()
    logger.info("PubSub Manager initialized for publishing.")
except ImportError:
    logger.warning("google_pubsub_manager not found. Publishing capabilities might be disabled.")
    pubsub_manager = None # O gestisci l'errore diversamente se è critico

# In-memory job status
job_status_map: Dict[str, Dict[str, Any]] = {}

@app.route('/upload_and_analyze', methods=['POST'])
def upload_and_analyze():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file:
        job_id = str(uuid.uuid4())
        original_filename = file.filename

        file_content_bytes = file.read()
        encoded_file_content = base64.b64encode(file_content_bytes).decode('utf-8')

        job_status_map[job_id] = {
            'status': 'uploaded',
            'filename': original_filename,
            'progress': 0,
            'details': 'File uploaded, waiting for analysis.',
            'timestamp': datetime.now().isoformat(),
            'processed_data': None,
            'metadata': None,
            'anonymized_data': None,
            'anonymized_sample': None
        }

        pubsub_manager.publish(Topics.DATA_UPLOAD_REQUESTS, {
            'job_id': job_id,
            'filename': original_filename,
            'file_content_base64': encoded_file_content
        }, attributes={'job_id': job_id})
        
        return jsonify({
            "message": "File uploaded and analysis initiated",
            "job_id": job_id,
            "filename": original_filename
        }), 202
    
    return jsonify({"error": "Failed to upload file"}), 500

def dataframe_to_json_safe(df, max_rows=None):
    """Converte un DataFrame in formato JSON sicuro per la trasmissione"""
    if df is None or not isinstance(df, pd.DataFrame):
        return None
    
    try:
        # Limita il numero di righe se specificato
        if max_rows:
            df_sample = df.head(max_rows)
        else:
            df_sample = df
            
        # Converte in formato JSON con gestione dei tipi
        return df_sample.to_dict(orient='records')
    except Exception as e:
        logger.error(f"Error converting DataFrame to JSON: {e}")
        return None

@app.route('/get_analysis_status/<job_id>', methods=['GET'])
def get_analysis_status(job_id):
    status = job_status_map.get(job_id, {'status': 'not_found', 'details': 'Job ID not found'})
    
    # Crea una copia dello status per evitare modifiche al dizionario originale
    response_status = status.copy()
    
    # Convert DataFrame to JSON for preview if available
    if status.get('processed_data') is not None:
        response_status['processed_data_preview'] = dataframe_to_json_safe(status['processed_data'], max_rows=10)
        response_status['processed_data_info'] = {
            'total_rows': len(status['processed_data']),
            'total_columns': len(status['processed_data'].columns),
            'columns': list(status['processed_data'].columns)
        }
        # Rimuovi il DataFrame originale dalla risposta
        response_status.pop('processed_data', None)
    
    if status.get('anonymized_data') is not None:
        response_status['anonymized_data_preview'] = dataframe_to_json_safe(status['anonymized_data'], max_rows=10)
        response_status['anonymized_data_info'] = {
            'total_rows': len(status['anonymized_data']),
            'total_columns': len(status['anonymized_data'].columns),
            'columns': list(status['anonymized_data'].columns)
        }
        # Rimuovi il DataFrame originale dalla risposta
        response_status.pop('anonymized_data', None)
    
    if status.get('metadata') is not None:
        response_status['metadata_preview'] = dataframe_to_json_safe(status['metadata'], max_rows=50)
        # Rimuovi il DataFrame originale dalla risposta
        response_status.pop('metadata', None)
    
    if status.get('anonymized_sample') is not None:
        response_status['anonymized_sample_data'] = dataframe_to_json_safe(status['anonymized_sample'])
        # Rimuovi il DataFrame originale dalla risposta
        response_status.pop('anonymized_sample', None)
    
    return jsonify(response_status), 200

@app.route('/get_anonymization_results/<job_id>', methods=['GET'])
def get_anonymization_results(job_id):
    """Endpoint dedicato per ottenere i risultati completi dell'anonimizzazione in JSON"""
    job_status = job_status_map.get(job_id)
    
    if not job_status:
        return jsonify({"error": "Job not found"}), 404
    
    if job_status.get('status') != 'completed':
        return jsonify({
            "error": f"Anonymization not completed. Current status: {job_status.get('status')}",
            "details": job_status.get('details')
        }), 400
    
    anonymized_data = job_status.get('anonymized_data')
    if anonymized_data is None:
        return jsonify({"error": "Anonymized data not available"}), 404
    
    # Parametri per la paginazione (opzionali)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    # Prepara la risposta JSON completa
    response_data = {
        'job_id': job_id,
        'status': job_status.get('status'),
        'method_used': job_status.get('method_used'),
        'params_used': job_status.get('params_used'),
        'anonymization_completed_at': job_status.get('anonymization_completed_at'),
        'data_info': {
            'total_rows': len(anonymized_data),
            'total_columns': len(anonymized_data.columns),
            'columns': list(anonymized_data.columns)
        },
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_pages': (len(anonymized_data) + per_page - 1) // per_page,
            'has_next': end_idx < len(anonymized_data),
            'has_prev': page > 1
        },
        'data': dataframe_to_json_safe(anonymized_data.iloc[start_idx:end_idx])
    }
    
    return jsonify(response_data), 200

@app.route('/get_anonymization_summary/<job_id>', methods=['GET'])
def get_anonymization_summary(job_id):
    """Endpoint per ottenere un riassunto dei risultati dell'anonimizzazione"""
    job_status = job_status_map.get(job_id)
    
    if not job_status:
        return jsonify({"error": "Job not found"}), 404
    
    if job_status.get('status') != 'completed':
        return jsonify({
            "error": f"Anonymization not completed. Current status: {job_status.get('status')}",
            "details": job_status.get('details')
        }), 400
    
    original_data = job_status.get('processed_data')
    anonymized_data = job_status.get('anonymized_data')
    
    if original_data is None or anonymized_data is None:
        return jsonify({"error": "Data not available for comparison"}), 404
    
    # Calcola statistiche di confronto
    summary = {
        'job_id': job_id,
        'filename': job_status.get('filename'),
        'method_used': job_status.get('method_used'),
        'params_used': job_status.get('params_used'),
        'anonymization_completed_at': job_status.get('anonymization_completed_at'),
        'original_data': {
            'rows': len(original_data),
            'columns': len(original_data.columns),
            'columns_list': list(original_data.columns)
        },
        'anonymized_data': {
            'rows': len(anonymized_data),
            'columns': len(anonymized_data.columns),
            'columns_list': list(anonymized_data.columns)
        },
        'sample_data': dataframe_to_json_safe(anonymized_data, max_rows=5),
        'data_reduction': {
            'rows_retained': len(anonymized_data) / len(original_data) if len(original_data) > 0 else 0,
            'columns_retained': len(anonymized_data.columns) / len(original_data.columns) if len(original_data.columns) > 0 else 0
        }
    }
    
    return jsonify(summary), 200

@app.route('/request_anonymization', methods=['POST'])
def request_anonymization():
    data = request.json
    job_id = data.get('job_id')
    method = data.get('method')
    params = data.get('params')
    user_selections = data.get('user_selections')

    if not all([job_id, method, user_selections is not None]):
        return jsonify({"error": "Missing job_id, method, or user_selections"}), 400

    job_status = job_status_map.get(job_id)
    if not job_status or job_status['status'] != 'analyzed':
        return jsonify({"error": "Job not analyzed yet or not found"}), 400
    
    # Convert DataFrame to CSV and then to base64 for PubSub
    processed_csv_buffer = StringIO()
    job_status['processed_data'].to_csv(processed_csv_buffer, index=False)
    processed_csv_content = processed_csv_buffer.getvalue()
    encoded_processed_csv = base64.b64encode(processed_csv_content.encode('utf-8')).decode('utf-8')

    metadata_json_buffer = StringIO()
    job_status['metadata'].to_json(metadata_json_buffer, orient='records', indent=4)
    metadata_json_content = metadata_json_buffer.getvalue()
    encoded_metadata_json = base64.b64encode(metadata_json_content.encode('utf-8')).decode('utf-8')

    job_status_map[job_id].update({
        'status': 'anonymization_requested',
        'progress': 75,
        'details': 'Anonymization requested, waiting for results.',
        'method': method,
        'params': params,
        'anonymization_request_at': datetime.now().isoformat()
    })

    pubsub_manager.publish(Topics.ANONYMIZATION_REQUESTS, {
        'job_id': job_id,
        'method': method,
        'params': params,
        'user_selections': user_selections,
        'processed_data_content_base64': encoded_processed_csv,
        'metadata_content_base64': encoded_metadata_json
    }, attributes={'job_id': job_id})
    
    return jsonify({"message": "Anonymization request published", "job_id": job_id}), 202

# Download endpoints remain the same as before
@app.route('/download/<job_id>/full', methods=['GET'])
def download_full_file(job_id):
    try:
        job_status = job_status_map.get(job_id)
        
        if not job_status:
            return jsonify({"error": "Job not found"}), 404
        
        if job_status.get('status') != 'completed':
            return jsonify({
                "error": f"File not ready. Current status: {job_status.get('status')}",
                "details": job_status.get('details')
            }), 400
        
        anonymized_data = job_status.get('anonymized_data')
        original_filename = job_status.get('filename', 'anonymized_data.csv')

        if not isinstance(anonymized_data, pd.DataFrame):
            return jsonify({"error": "Anonymized data not available"}), 404
        
        download_name = f"anonymized_{original_filename}"
        if not download_name.endswith('.csv'):
            download_name += '.csv'

        output = BytesIO()
        anonymized_data.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(output, as_attachment=True, download_name=download_name, mimetype='text/csv')
        
    except Exception as e:
        logger.error(f"Error downloading full anonymized file for job {job_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/download_sample/<job_id>', methods=['GET'])
def download_sample(job_id):
    try:
        job_status = job_status_map.get(job_id)
        
        if not job_status:
            return jsonify({"error": "Job not found"}), 404
            
        if job_status.get('status') != 'completed':
            return jsonify({
                "error": f"Sample not ready. Current status: {job_status.get('status')}",
                "details": job_status.get('details')
            }), 400
        
        anonymized_data = job_status.get('anonymized_data')
        original_filename = job_status.get('filename', 'anonymized_sample.csv')

        if not isinstance(anonymized_data, pd.DataFrame):
            return jsonify({"error": "Anonymized data not available"}), 404
        
        download_name = f"anonymized_sample_{original_filename}"
        if not download_name.endswith('.csv'):
            download_name += '.csv'

        output = BytesIO()
        anonymized_data.head(10).to_csv(output, index=False)
        output.seek(0)
        
        return send_file(output, as_attachment=True, download_name=download_name, mimetype='text/csv')
        
    except Exception as e:
        logger.error(f"Error downloading anonymized sample for job {job_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/export_anonymization_json/<job_id>', methods=['GET'])
def export_anonymization_json(job_id):
    """Endpoint per esportare i risultati dell'anonimizzazione come file JSON"""
    try:
        job_status = job_status_map.get(job_id)
        
        if not job_status:
            return jsonify({"error": "Job not found"}), 404
        
        if job_status.get('status') != 'completed':
            return jsonify({
                "error": f"Results not ready. Current status: {job_status.get('status')}",
                "details": job_status.get('details')
            }), 400
        
        anonymized_data = job_status.get('anonymized_data')
        if anonymized_data is None:
            return jsonify({"error": "Anonymized data not available"}), 404
        
        # Prepara i dati per l'export JSON
        export_data = {
            'metadata': {
                'job_id': job_id,
                'filename': job_status.get('filename'),
                'method_used': job_status.get('method_used'),
                'params_used': job_status.get('params_used'),
                'anonymization_completed_at': job_status.get('anonymization_completed_at'),
                'total_rows': len(anonymized_data),
                'total_columns': len(anonymized_data.columns),
                'columns': list(anonymized_data.columns)
            },
            'data': dataframe_to_json_safe(anonymized_data)
        }
        
        # Crea il file JSON
        json_content = json.dumps(export_data, indent=2, ensure_ascii=False)
        output = BytesIO(json_content.encode('utf-8'))
        output.seek(0)
        
        original_filename = job_status.get('filename', 'anonymized_data')
        download_name = f"anonymized_{original_filename.rsplit('.', 1)[0]}.json"
        
        return send_file(output, as_attachment=True, download_name=download_name, mimetype='application/json')
        
    except Exception as e:
        logger.error(f"Error exporting JSON for job {job_id}: {e}")
        return jsonify({"error": str(e)}), 500

# NEW: Endpoints per ricevere i risultati via POST
@app.route('/receive_analysis_results', methods=['POST'])
def receive_analysis_results():
    envelope = request.get_json()
    if not envelope or 'message' not in envelope:
        logger.error("Invalid Pub/Sub message format")
        return 'Bad Request', 400
    pubsub_message = envelope['message']
    try:
        payload = base64.b64decode(pubsub_message['data']).decode('utf-8')
        message_data = json.loads(payload)
        logger.info(f"Received Pub/Sub push: {message_data}")
        data = message_data.get('data')
        job_id = data.get('job_id')
        status = data.get('status')
        processed_data_content_base64 = data.get('processed_data_content_base64')
        metadata_content_base64 = data.get('metadata_content_base64')
        dataset_info = data.get('dataset_info')

        if job_id in job_status_map:
            try:
                # Decode and convert to DataFrame
                processed_csv = base64.b64decode(processed_data_content_base64).decode('utf-8')
                processed_df = pd.read_csv(StringIO(processed_csv))
                
                metadata_json = base64.b64decode(metadata_content_base64).decode('utf-8')
                metadata_df = pd.read_json(StringIO(metadata_json), orient='records')

                job_status_map[job_id].update({
                    'status': status,
                    'progress': 50,
                    'details': 'Data analysis completed.',
                    'dataset_info': dataset_info,
                    'processed_data': processed_df,
                    'metadata': metadata_df,
                    'analysis_completed_at': datetime.now().isoformat()
                })
                logger.info(f"Analysis results received via POST for job {job_id}")
                return jsonify({"message": "Analysis results received successfully"}), 200
            except Exception as e:
                logger.error(f"Error processing analysis results for job {job_id}: {e}")
                job_status_map[job_id].update({
                    'status': 'error',
                    'details': f"Error processing analysis results: {str(e)}"
                })
                return jsonify({"error": str(e)}), 400
        else:
            logger.warning(f"Received analysis results for unknown job {job_id}")
            return jsonify({"error": "Job ID not found"}), 404
    except Exception as e:
        logger.error(f"Failed to process incoming Pub/Sub push: {e}", exc_info=True)
        return 'Bad Request', 400

@app.route('/receive_anonymization_results', methods=['POST'])
def receive_anonymization_results():
    envelope = request.get_json()
    if not envelope or 'message' not in envelope:
        logger.error("Invalid Pub/Sub message format")
        return 'Bad Request', 400
    pubsub_message = envelope['message']
    try:
        payload = base64.b64decode(pubsub_message['data']).decode('utf-8')
        message_data = json.loads(payload)
        logger.info(f"Received Pub/Sub push: {message_data}")
        data = message_data.get('data')
        job_id = data.get('job_id')
        status = data.get('status')
        anonymized_file_content_base64 = data.get('anonymized_file_content_base64')
        anonymized_sample_content_base64 = data.get('anonymized_sample_content_base64')
        method_used = data.get('method_used')
        params_used = data.get('params_used')

        if job_id in job_status_map:
            try:
                # Decode and convert to DataFrame
                anonymized_csv = base64.b64decode(anonymized_file_content_base64).decode('utf-8')
                anonymized_df = pd.read_csv(StringIO(anonymized_csv))
                
                sample_csv = base64.b64decode(anonymized_sample_content_base64).decode('utf-8')
                sample_df = pd.read_csv(StringIO(sample_csv))

                job_status_map[job_id].update({
                    'status': status,
                    'progress': 100,
                    'details': 'Data anonymization completed.',
                    'method_used': method_used,
                    'params_used': params_used,
                    'anonymized_data': anonymized_df,
                    'anonymized_sample': sample_df,
                    'anonymization_completed_at': datetime.now().isoformat()
                })
                logger.info(f"Anonymization results received via POST for job {job_id}")
                return jsonify({"message": "Anonymization results received successfully"}), 200
            except Exception as e:
                logger.error(f"Error processing anonymization results for job {job_id}: {e}")
                job_status_map[job_id].update({
                    'status': 'error',
                    'details': f"Error processing anonymization results: {str(e)}"
                })
                return jsonify({"error": str(e)}), 400
        else:
            logger.warning(f"Received anonymization results for unknown job {job_id}")
            return jsonify({"error": "Job ID not found"}), 404
    except Exception as e:
        logger.error(f"Failed to process incoming Pub/Sub push: {e}", exc_info=True)
        return 'Bad Request', 400


@app.route('/receive_error_notifications', methods=['POST'])
def receive_error_notifications():
    envelope = request.get_json()
    if not envelope or 'message' not in envelope:
        logger.error("Invalid Pub/Sub message format")
        return 'Bad Request', 400
    pubsub_message = envelope['message']
    try:
        payload = base64.b64decode(pubsub_message['data']).decode('utf-8')
        message_data = json.loads(payload)
        logger.info(f"Received Pub/Sub push: {message_data}")
        data = message_data.get('data')
        job_id = data.get('job_id')
        stage = data.get('stage')
        error_message = data.get('error')

        if job_id in job_status_map:
            job_status_map[job_id].update({
                'status': 'error',
                'progress': -1,
                'details': f"Error during {stage}: {error_message}",
                'error_stage': stage,
                'error_message': error_message,
                'error_at': datetime.now().isoformat()
            })
            logger.error(f"Error notification received via POST for job {job_id} in stage {stage}")
            return jsonify({"message": "Error notification received successfully"}), 200
        else:
            logger.warning(f"Received error for unknown job {job_id} in stage {stage}")
            return jsonify({"error": "Job ID not found"}), 404
    except Exception as e:
        logger.error(f"Failed to process incoming Pub/Sub push: {e}", exc_info=True)
        return 'Bad Request', 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)