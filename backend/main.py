from flask import Flask, request, jsonify, send_from_directory
import os
import subprocess
import logging

# Logging configuration
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('server')

app = Flask(__name__)

# Folder definitions
UPLOAD_FOLDER = '/app/uploads'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB upload limit

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint to verify that the server is active"""
    return jsonify({"status": "healthy"}), 200

@app.route('/process/initialize', methods=['POST'])
def process_step1():
    """
    Step 1: Receives a file, saves it and calls the first microservice
    to generate the intermediate file and metadata
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file submitted"}), 400
    
    file = request.files['file']
    
    # Generate a GUID randomly
    guid = os.urandom(16).hex

    workingpath = os.path.join(UPLOAD_FOLDER, guid)
    os.makedirs(workingpath)

    # Save the uploaded file
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], guid, "original_file.csv")
    file.save(filepath)
    logger.info(f"File saved: {filepath}")
    
    try:
       
        logger.info(f"Starting first microservice...")
        result = subprocess.run(
            ["python", "dataAnalyzer/dataAnalyzer.py", filepath, "--output-dir", workingpath],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"First microservice completed: {result.stdout}")
        
        # Read metadata from file
        with open(os.path.join(workingpath, "metadata.csv"), 'r') as f:
            metadata = f.read()
        
        # Return metadata as response
        return jsonify({
            "metadata": metadata,
            "identifier": guid
        }), 200
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during execution of microservice 1: {e.stderr}")
        return jsonify({"error": f"Error during processing: {e.stderr}"}), 500
    except Exception as e:
        logger.error(f"Generic error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/process/<guid>', methods=['POST'])
def process_step2(guid):
    """
    Step 2: Receives modified metadata and reference to the original file,
    calls the second microservice for final processing
    """
    workingpath = os.path.join(UPLOAD_FOLDER, guid)
    if not os.path.exists(workingpath):
        return jsonify({"error": "Invalid GUID"}), 400

    try:
        updated_metadata_file = os.path.join(workingpath, "updated_metadata.csv")
        with open(updated_metadata_file, 'w') as f:
            f.write(request.data.decode('utf-8'))
        
        # Execute the second microservice
        logger.info(f"Starting second microservice...")
        result = subprocess.run(
            ["python", "anonymizer/anonymizer.py", 
             "--input", guid + "/structured_data.csv", 
             "--metadata", updated_metadata_file, 
             "--output-dir", os.path.join(workingpath, guid)],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Second microservice completed: {result.stdout}")
        
        with open(os.path.join(workingpath, "anonymizedData_sample.csv"), 'r') as f:
            sample_file = f.read()

        return jsonify({
            "output_file": f"download/{guid}",
            "sample_file": sample_file,
        }), 200
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during execution of microservice 2: {e.stderr}")
        return jsonify({"error": f"Error during final processing: {e.stderr}"}), 500
    except Exception as e:
        logger.error(f"Generic error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/download/<guid>', methods=['GET'])
def get_file(guid):
    """Endpoint to download processed files"""
    return send_from_directory(os.path.join(UPLOAD_FOLDER, guid), 
                               filename="anonymizedData.csv",
                               as_attachment=True)

if __name__ == '__main__':
    # In production use gunicorn or other WSGI server
    app.run(host='0.0.0.0', port=8000, debug=False)