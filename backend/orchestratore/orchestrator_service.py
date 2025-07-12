from flask import Flask, request, jsonify, send_file
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
import firebase_admin
from firebase_admin import auth
from google.cloud import storage
from sqlalchemy import create_engine, text

# Configurations (environment variables)
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
BUCKET_NAME = os.environ.get("BUCKET_NAME")
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SQLAlchemy engine with connection pool
DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
engine = create_engine(
    DATABASE_URL,
    pool_size=20,           # Max number of connections in pool
    max_overflow=30,        # Overflow connections
    pool_timeout=30,        # Timeout for getting a connection
    pool_recycle=1800       # Recycle connections every 30 min
)

def init_db():
    with engine.connect() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                user_id TEXT,
                filename TEXT,
                rows INTEGER,
                metadata TEXT,
                path_file_analyzed TEXT,
                method TEXT,
                anonymized_preview TEXT,
                path_file_anonymized TEXT,
                upload_at TEXT,
                completed_at TEXT,
                status TEXT,
                error_message TEXT,
            )
        '''))
        conn.commit()

init_db()

app = Flask(__name__)
CORS(app)

# Initialize Firebase Admin SDK
firebase_admin.initialize_app()

# Initialize Google Cloud Storage client
storage_client = storage.Client()

def firebase_auth_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', None)
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        id_token = auth_header.split(" ")[1]
        try:
            decoded_token = auth.verify_id_token(id_token)
            request.user_id = decoded_token["uid"]
            return f(*args, **kwargs)
        except Exception as e:
            logging.warning(f"Firebase Auth failed: {e}")
            return jsonify({"error": "Invalid auth token"}), 401
    return decorated_function

# Initialize PubSub Manager
try:
    from google_pubsub_manager import get_pubsub_manager, Topics
    pubsub_manager = get_pubsub_manager()
    logger.info("PubSub Manager initialized for publishing.")
except ImportError:
    logger.warning("google_pubsub_manager not found. Publishing capabilities might be disabled.")
    pubsub_manager = None

# ==== NEW FILE FLOW ====
@app.route('/upload_and_analyze', methods=['POST'])
@firebase_auth_required
def upload_and_analyze():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        job_id = str(uuid.uuid4()) + '-' + datetime.now().strftime("%Y%m%d%H%M%S")
        original_filename = file.filename

        file_content_bytes = file.read()
        encoded_file_content = base64.b64encode(file_content_bytes).decode('utf-8')

        upload_at = datetime.now().isoformat()
        
        with engine.connect() as conn:
            conn.execute(text('''
                INSERT INTO jobs (job_id, user_id, filename, rows, metadata, path_file_analyzed, method, anonymized_preview, path_file_anonymized, upload_at, completed_at, status)
                VALUES (:job_id, :user_id, :filename, :rows, :metadata, :path_file_analyzed, :method, :anonymized_preview, :path_file_anonymized, :upload_at, :completed_at, :status)
            '''), {
                "job_id": job_id,
                "user_id": request.user_id,
                "filename": original_filename,
                "rows": 0,
                "metadata": None,
                "path_file_analyzed": None,
                "method": None,
                "anonymized_preview": None,
                "path_file_anonymized": None,
                "upload_at": upload_at,
                "completed_at": None,
                "status": 'uploaded',
                "error_message": None
            })
            conn.commit()

        if pubsub_manager:
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

@app.route('/request_anonymization', methods=['POST'])
@firebase_auth_required
def request_anonymization():
    data = request.json
    job_id = data.get('job_id')
    method = data.get('method')
    params = data.get('params')
    user_selections = data.get('user_selections')

    if not all([job_id, method, user_selections is not None]):
        return jsonify({"error": "Missing job_id, method, or user_selections"}), 400

    with engine.connect() as conn:
        result = conn.execute(text('SELECT * FROM jobs WHERE job_id = :job_id'), {"job_id": job_id})
        job = result.mappings().first()
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job['user_id'] != request.user_id:
        return jsonify({"error": "Unauthorized access to this job"}), 403
    if job['status'] != 'analyzed':
        return jsonify({"error": "Job is not ready for anonymization"}), 400

    # Download processed file from GCP bucket
    gcp_path = job['path_file_analyzed']
    if not gcp_path:
        return jsonify({"error": "No analyzed file path found for this job"}), 400

    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(gcp_path)
        processed_csv_content = blob.download_as_text()
        encoded_processed_csv = base64.b64encode(processed_csv_content.encode('utf-8')).decode('utf-8')

        metadata_json_content = job['metadata']
        encoded_metadata_json = base64.b64encode(metadata_json_content.encode('utf-8')).decode('utf-8')

        if pubsub_manager:
            pubsub_manager.publish(Topics.ANONYMIZATION_REQUESTS, {
                'job_id': job_id,
                'method': method,
                'params': params,
                'user_selections': user_selections,
                'processed_data_content_base64': encoded_processed_csv,
                'metadata_content_base64': encoded_metadata_json
            }, attributes={'job_id': job_id})

        with engine.connect() as conn:
            conn.execute(text('UPDATE jobs SET status = :status, method = :method WHERE job_id = :job_id'), 
                       {"status": 'anonymization_requested', "method": method, "job_id": job_id})
            conn.commit()

        return jsonify({"message": "Anonymization request published", "job_id": job_id}), 202
    
    except Exception as e:
        logger.error(f"Error in request_anonymization: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/get_status/<job_id>', methods=['GET'])
@firebase_auth_required
def get_status(job_id):
    with engine.connect() as conn:
        result = conn.execute(text('SELECT * FROM jobs WHERE job_id = :job_id'), {"job_id": job_id})
        job = result.mappings().first()
    
    if not job:
        return jsonify({'error': 'not_found', 'details': 'Job ID not found'}), 404
    if job['user_id'] != request.user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    response_status = {
        "job_id": job['job_id'],
        "filename": job['filename'],
        "status": job['status'],
        "upload_at": job['upload_at'],
        "completed_at": job['completed_at'],
        "rows": job['rows'],
        "method": job['method'],
        "metadata": json.loads(job['metadata']) if job['metadata'] else None,        
        "anonymized_preview": json.loads(job['anonymized_preview']) if job['anonymized_preview'] else None,
        "error_message": job['error_message'] if job['error_message'] else None
    }
    return jsonify(response_status), 200

@app.route('/get_files', methods=['GET'])
@firebase_auth_required
def get_files():
    with engine.connect() as conn:
        result = conn.execute(text('SELECT * FROM jobs WHERE user_id = :user_id'), {"user_id": request.user_id})
        jobs = list(result.mappings())
    files_info = []
    for job in jobs:
        if job['status'] == 'anonymized':
            files_info.append({
                'job_id': job['job_id'],
                'anonymized_preview': json.loads(job['anonymized_preview']) if job['anonymized_preview'] else None,
                'filename': job['filename'],
                'status': job['status'],
                'method': job['method'],
                'rows': job['rows'],
                'download_url': f"/download/{job['job_id']}",
                'delete_url': f"/delete/{job['job_id']}",
                'datetime_completition':job['completed_at'],
                'datetime_upload': job['upload_at']
            })
        else:
            files_info.append({
                'job_id': job['job_id'],
                'filename': job['filename'],
                'status': job['status']
            })
    
    total_datasets = len(files_info)
    total_rows = sum(file.get('rows', 0) for file in files_info if file.get('rows'))
    stats = [{'datasets': total_datasets, 'total_rows': total_rows}]
    result = [{'stats': stats}, {'files': files_info}]
    return jsonify(result), 200

@app.route('/download/<job_id>', methods=['GET'])
@firebase_auth_required
def download_full_file(job_id):
    with engine.connect() as conn:
        result = conn.execute(text('SELECT * FROM jobs WHERE job_id = :job_id'), {"job_id": job_id})
        job = result.mappings().first()
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job['user_id'] != request.user_id:
        return jsonify({"error": "Unauthorized access to this job"}), 403
    if job['status'] != 'anonymized':
        return jsonify({"error": "File not ready. Still processing."}), 400
    
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(job['path_file_anonymized'])
        if not blob.exists():
            return jsonify({"error": "Anonymized file not found in GCP bucket"}), 404
        
        file_content = blob.download_as_text()
        download_name = job['filename'] if job['filename'] else f"anonymized_file_{job_id}.csv"
        
        return send_file(
            BytesIO(file_content.encode("utf-8")),
            as_attachment=True,
            download_name=download_name,
            mimetype='text/csv'
        )
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return jsonify({"error": "Error downloading file"}), 500

@app.route('/delete/<job_id>', methods=['DELETE'])
@firebase_auth_required
def delete_job(job_id):
    with engine.connect() as conn:
        result = conn.execute(text('SELECT * FROM jobs WHERE job_id = :job_id'), {"job_id": job_id})
        job = result.mappings().first()
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job['user_id'] != request.user_id:
        return jsonify({"error": "Unauthorized access to this job"}), 403

    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        if job['path_file_anonymized']:
            blobAnonymized = bucket.blob(job['path_file_anonymized'])
            if blobAnonymized.exists():
                blobAnonymized.delete()
        if job['path_file_analyzed']:
            blobAnalyzed = bucket.blob(job['path_file_analyzed'])
            if blobAnalyzed.exists():
                blobAnalyzed.delete()

        with engine.connect() as conn:
            conn.execute(text('DELETE FROM jobs WHERE job_id = :job_id'), {"job_id": job_id})
            conn.commit()

        return jsonify({"message": "File deleted successfully"}), 200
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        return jsonify({"error": "Error deleting file"}), 500

# === PUB/SUB ENDPOINTS ===
@app.route('/receive_analysis_results', methods=['POST'])
def receive_analysis_results():
    envelope = request.get_json()
    if not envelope or 'message' not in envelope:
        logger.error("Invalid Pub/Sub message format")
        return 'Bad Request', 200
    
    pubsub_message = envelope['message']
    try:
        payload = base64.b64decode(pubsub_message['data']).decode('utf-8')
        message_data = json.loads(payload)
        logger.info(f"Received analysis results: {message_data}")
        
        data = message_data.get('data')
        job_id = data.get('job_id')
        processed_data_content_base64 = data.get('processed_data_content_base64')
        metadata_content_base64 = data.get('metadata_content_base64')

        with engine.connect() as conn:
            result = conn.execute(text('SELECT * FROM jobs WHERE job_id = :job_id'), {"job_id": job_id})
            job = result.mappings().first()
        
        if not job:
            logger.warning(f"Received analysis results for unknown job {job_id}")
            return jsonify({"error": "Job ID not found"}), 200

        try:
            processed_csv = base64.b64decode(processed_data_content_base64).decode('utf-8')
            processed_df = pd.read_csv(StringIO(processed_csv))
            metadata_json = base64.b64decode(metadata_content_base64).decode('utf-8')

            gcp_path = f"{job_id}/processed_data.csv"
            bucket = storage_client.bucket(BUCKET_NAME)
            blob = bucket.blob(gcp_path)
            blob.upload_from_string(processed_df.to_csv(index=False), content_type='text/csv')
            
            with engine.connect() as conn:
                conn.execute(text('''
                    UPDATE jobs
                    SET status = :status, path_file_analyzed = :path_file_analyzed, metadata = :metadata, rows = :rows
                    WHERE job_id = :job_id
                '''), {
                    "status": 'analyzed',
                    "path_file_analyzed": gcp_path,
                    "metadata": metadata_json,
                    "rows": len(processed_df),
                    "job_id": job_id
                })
                conn.commit()
            
            return jsonify({"message": "Analysis results received successfully"}), 200
            
        except Exception as e:
            logger.error(f"Error processing analysis results for job {job_id}: {e}")
            with engine.connect() as conn:
                conn.execute(text('UPDATE jobs SET status = :status WHERE job_id = :job_id'), {"status": "error", "job_id": job_id})
                conn.commit()
            return jsonify({"error": str(e)}), 200
            
    except Exception as e:
        logger.error(f"Failed to process incoming Pub/Sub push: {e}", exc_info=True)
        return 'Bad Request', 200

@app.route('/receive_anonymization_results', methods=['POST'])
def receive_anonymization_results():
    envelope = request.get_json()
    if not envelope or 'message' not in envelope:
        logger.error("Invalid Pub/Sub message format")
        return 'Bad Request', 200
    
    pubsub_message = envelope['message']
    try:
        payload = base64.b64decode(pubsub_message['data']).decode('utf-8')
        message_data = json.loads(payload)
        logger.info(f"Received anonymization results: {message_data}")
        
        data = message_data.get('data')
        job_id = data.get('job_id')
        anonymized_file_content_base64 = data.get('anonymized_file_content_base64')
        anonymized_sample_content_base64 = data.get('anonymized_sample_content_base64')
        completed_at = datetime.now().isoformat()

        anonymized_csv = base64.b64decode(anonymized_file_content_base64).decode('utf-8')
        anonymized_df = pd.read_csv(StringIO(anonymized_csv))

        anonymized_sample_csv = base64.b64decode(anonymized_sample_content_base64).decode('utf-8')
        anonymized_sample_df = pd.read_csv(StringIO(anonymized_sample_csv))

        gcp_path = f"{job_id}/anonymized_data.csv"
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(gcp_path)
        blob.upload_from_string(anonymized_df.to_csv(index=False), content_type='text/csv')

        with engine.connect() as conn:
            result = conn.execute(text('SELECT path_file_analyzed FROM jobs WHERE job_id = :job_id'), {"job_id": job_id})
            job = result.mappings().first()
        analyzed_file_path = job['path_file_analyzed']
        if analyzed_file_path:
            analyzed_blob = bucket.blob(analyzed_file_path)
            if analyzed_blob.exists():
                analyzed_blob.delete()

        anonymized_preview_json = anonymized_sample_df.to_json(orient='records', indent=4)

        with engine.connect() as conn:
            conn.execute(text('''
                UPDATE jobs
                SET path_file_analyzed = :path_file_analyzed, status = :status, anonymized_preview = :anonymized_preview, path_file_anonymized = :path_file_anonymized, completed_at = :completed_at
                WHERE job_id = :job_id
            '''), {
                "path_file_analyzed": None,
                "status": "anonymized",
                "anonymized_preview": anonymized_preview_json,
                "path_file_anonymized": gcp_path,
                "completed_at": completed_at,
                "job_id": job_id
            })
            conn.commit()

        logger.info(f"Anonymization results received for job {job_id}")
        return jsonify({"message": "Anonymization results received successfully"}), 200
        
    except Exception as e:
        logger.error(f"Failed to process anonymization results: {e}", exc_info=True)
        return 'Bad Request', 200

@app.route('/receive_error_notifications', methods=['POST'])
def receive_error_notifications():
    envelope = request.get_json()
    if not envelope or 'message' not in envelope:
        logger.error("Invalid Pub/Sub message format")
        return 'Bad Request', 200
    
    pubsub_message = envelope['message']
    try:
        payload = base64.b64decode(pubsub_message['data']).decode('utf-8')
        message_data = json.loads(payload)
        logger.info(f"Received Pub/Sub push: {message_data}")
        data = message_data.get('data')
        job_id = data.get('job_id')
        stage = data.get('stage')
        error_message = data.get('error')

        if not job_id or not stage or not error_message:
            logger.error("Missing job_id, stage or error message in Pub/Sub notification")
            return jsonify({"error": "Missing job_id, stage or error message"}), 200

        with engine.connect() as conn:
            result = conn.execute(text('SELECT job_id FROM jobs WHERE job_id = :job_id'), {"job_id": job_id})
            job = result.mappings().first()
            
            if job:
                conn.execute(text('UPDATE jobs SET status = :status, completed_at = :completed_at, error_message = :error_message WHERE job_id = :job_id'), 
                           {"status": 'error', "completed_at": datetime.now().isoformat(), "error_message":error_message, "job_id": job_id})
                conn.commit()
                logger.error(f"Error notification received for job {job_id} in stage {stage}: {error_message}")
                return jsonify({"message": "Error notification received successfully"}), 200
            else:
                logger.warning(f"Received error for unknown job {job_id} in stage {stage}")
                return jsonify({"error": "Job ID not found"}), 200
                    
    except Exception as e:
        logger.error(f"Failed to process incoming Pub/Sub push: {e}", exc_info=True)
        return 'Bad Request', 200

# ==== API FOR TESTING PURPOSES ====
MOCK_USER_ID = "mocked-user"

@app.route('/noauth_upload_and_analyze', methods=['POST'])
def noauth_upload_and_analyze():
    request.user_id = MOCK_USER_ID
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        job_id = str(uuid.uuid4()) + '-' + datetime.now().strftime("%Y%m%d%H%M%S")
        original_filename = file.filename

        file_content_bytes = file.read()
        encoded_file_content = base64.b64encode(file_content_bytes).decode('utf-8')

        upload_at = datetime.now().isoformat()
        
        with engine.connect() as conn:
            conn.execute(text('''
                INSERT INTO jobs (job_id, user_id, filename, rows, metadata, path_file_analyzed, method, anonymized_preview, path_file_anonymized, upload_at, completed_at, status)
                VALUES (:job_id, :user_id, :filename, :rows, :metadata, :path_file_analyzed, :method, :anonymized_preview, :path_file_anonymized, :upload_at, :completed_at, :status)
            '''), {
                "job_id": job_id,
                "user_id": request.user_id,
                "filename": original_filename,
                "rows": 0,
                "metadata": None,
                "path_file_analyzed": None,
                "method": None,
                "anonymized_preview": None,
                "path_file_anonymized": None,
                "upload_at": upload_at,
                "completed_at": None,
                "status": 'uploaded'
            })
            conn.commit()

        if pubsub_manager:
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

@app.route('/noauth_request_anonymization', methods=['POST'])
def noauth_request_anonymization():
    request.user_id = MOCK_USER_ID
    data = request.json
    job_id = data.get('job_id')
    method = data.get('method')
    params = data.get('params')
    user_selections = data.get('user_selections')

    if not all([job_id, method, user_selections is not None]):
        return jsonify({"error": "Missing job_id, method, or user_selections"}), 400

    with engine.connect() as conn:
        result = conn.execute(text('SELECT * FROM jobs WHERE job_id = :job_id'), {"job_id": job_id})
        job = result.mappings().first()
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job['user_id'] != request.user_id:
        return jsonify({"error": "Unauthorized access to this job"}), 403
    if job['status'] != 'analyzed':
        return jsonify({"error": "Job is not ready for anonymization"}), 400

    gcp_path = job['path_file_analyzed']
    if not gcp_path:
        return jsonify({"error": "No analyzed file path found for this job"}), 400

    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(gcp_path)
        processed_csv_content = blob.download_as_text()
        encoded_processed_csv = base64.b64encode(processed_csv_content.encode('utf-8')).decode('utf-8')

        metadata_json_content = job['metadata']
        encoded_metadata_json = base64.b64encode(metadata_json_content.encode('utf-8')).decode('utf-8')

        if pubsub_manager:
            pubsub_manager.publish(Topics.ANONYMIZATION_REQUESTS, {
                'job_id': job_id,
                'method': method,
                'params': params,
                'user_selections': user_selections,
                'processed_data_content_base64': encoded_processed_csv,
                'metadata_content_base64': encoded_metadata_json
            }, attributes={'job_id': job_id})

        with engine.connect() as conn:
            conn.execute(text('UPDATE jobs SET status = :status, method = :method WHERE job_id = :job_id'), 
                       {"status": 'anonymization_requested', "method": method, "job_id": job_id})
            conn.commit()

        return jsonify({"message": "Anonymization request published", "job_id": job_id}), 202
    
    except Exception as e:
        logger.error(f"Error in request_anonymization: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/noauth_get_status/<job_id>', methods=['GET'])
def noauth_get_status(job_id):
    request.user_id = MOCK_USER_ID
    with engine.connect() as conn:
        result = conn.execute(text('SELECT * FROM jobs WHERE job_id = :job_id'), {"job_id": job_id})
        job = result.mappings().first()
    
    if not job:
        return jsonify({'error': 'not_found', 'details': 'Job ID not found'}), 404
    if job['user_id'] != request.user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    response_status = {
        "job_id": job['job_id'],
        "filename": job['filename'],
        "status": job['status'],
        "upload_at": job['upload_at'],
        "completed_at": job['completed_at'],
        "rows": job['rows'],
        "method": job['method'],
        "metadata": json.loads(job['metadata']) if job['metadata'] else None,        
        "anonymized_preview": json.loads(job['anonymized_preview']) if job['anonymized_preview'] else None
    }
    return jsonify(response_status), 200

@app.route('/noauth_download/<job_id>', methods=['GET'])
def noauth_download(job_id):
    request.user_id = MOCK_USER_ID
    with engine.connect() as conn:
        result = conn.execute(text('SELECT * FROM jobs WHERE job_id = :job_id'), {"job_id": job_id})
        job = result.mappings().first()
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job['user_id'] != request.user_id:
        return jsonify({"error": "Unauthorized access to this job"}), 403
    if job['status'] != 'anonymized':
        return jsonify({"error": "File not ready. Still processing."}), 400
    
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(job['path_file_anonymized'])
        if not blob.exists():
            return jsonify({"error": "Anonymized file not found in GCP bucket"}), 404
        
        file_content = blob.download_as_text()
        download_name = job['filename'] if job['filename'] else f"anonymized_file_{job_id}.csv"
        
        return send_file(
            BytesIO(file_content.encode("utf-8")),
            as_attachment=True,
            download_name=download_name,
            mimetype='text/csv'
        )
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return jsonify({"error": "Error downloading file"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)