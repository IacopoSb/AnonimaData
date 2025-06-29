from flask import Flask, request, jsonify, render_template, send_file
import pandas as pd
import os
from io import BytesIO, StringIO
import logging
import uuid # Per nomi di file unici

# Importa le tue classi e funzioni di anonimizzazione
from anonymizer import process_anonymization 
from dataAnalyzer import read_dataset_for_web, structure_dataset, identify_column_type # Potresti voler esporre identify_column_type per l'analisi in tempo reale

# Configura il logging per Flask
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ANONYMIZED_FOLDER'] = 'anonymized_data'

# Crea le cartelle se non esistono
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['ANONYMIZED_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_and_analyze', methods=['POST'])
def upload_and_analyze():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file:
        try:
            filename = file.filename
            file_extension = os.path.splitext(filename)[1].lower()
            
            # Read file content
            if file_extension in ['.csv', '.txt', '.json']:
                file_content = file.stream.read().decode('utf-8')
            elif file_extension in ['.xlsx', '.xls']:
                file_content = file.stream.read() # Read as bytes for excel
            else:
                return jsonify({"error": f"Unsupported file extension: {file_extension}"}), 400

            df = read_dataset_for_web(file_content, file_extension)
            
            # Analyze metadata
            _, metadata = structure_dataset(df)
            
            # Convert metadata to a list of dicts for JSON serialization
            metadata_list = metadata.to_dict(orient='records')
            
            # Store the DataFrame in session or a temporary file if you need it across requests
            # For simplicity in this demo, we'll return the metadata and expect the front-end
            # to re-upload or send the data back if needed, or manage state more robustly.
            # A better approach for production would be to save the df temporarily (e.g., to parquet)
            # and pass a UUID to the frontend.

            # For this quick demo, we will re-read the file in the anonymize endpoint
            # In a real app, save df temporarily and pass an ID to frontend
            temp_input_filename = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4()}{file_extension}")
            if file_extension in ['.csv', '.txt', '.json']:
                with open(temp_input_filename, 'w', encoding='utf-8') as f:
                    f.write(file_content)
            elif file_extension in ['.xlsx', '.xls']:
                with open(temp_input_filename, 'wb') as f:
                    f.write(file_content)
            
            return jsonify({
                "message": "File analyzed successfully",
                "metadata": metadata_list,
                "temp_filename": temp_input_filename # Send this back to identify the file later
            }), 200
        except Exception as e:
            logger.error(f"Error during upload and analysis: {e}")
            return jsonify({"error": str(e)}), 500

@app.route('/anonymize', methods=['POST'])
def anonymize_data():
    data = request.get_json()
    
    temp_filename = data.get('temp_filename')
    method = data.get('method')
    params = data.get('params', {})
    user_selections = data.get('user_selections', []) # This will contain QI, anonymize flags

    if not temp_filename or not method:
        return jsonify({"error": "Missing required parameters"}), 400

    try:
        # Re-load the original dataframe using the temp_filename
        file_extension = os.path.splitext(temp_filename)[1].lower()
        if file_extension in ['.csv', '.txt']:
            df = pd.read_csv(temp_filename)
        elif file_extension in ['.xlsx', '.xls']:
            df = pd.read_excel(temp_filename)
        elif file_extension in ['.json']:
            df = pd.read_json(temp_filename)
        else:
            return jsonify({"error": "Unsupported file type for re-loading"}), 400

        # Create metadata DataFrame from user selections received from frontend
        # This simulates the 'extended_metadata' from frontEndSimulator.py
        
        # First, get the basic metadata
        _, basic_metadata = structure_dataset(df) # Recalculate or store it from upload_and_analyze
        
        # Now, extend it with user selections
        # Create a new list of dictionaries for the extended metadata
        extended_metadata_data = []
        for col_name in basic_metadata['column_name']:
            col_info = next((item for item in user_selections if item['column_name'] == col_name), None)
            
            is_qi = col_info['is_quasi_identifier'] if col_info else False
            should_anon = col_info['should_anonymize'] if col_info else True # Default to anonymize if not specified

            extended_metadata_data.append({
                'column_name': col_name,
                'data_type': basic_metadata[basic_metadata['column_name'] == col_name]['data_type'].iloc[0],
                'is_quasi_identifier': is_qi,
                'should_anonymize': should_anon
            })
        
        extended_metadata_df = pd.DataFrame(extended_metadata_data)

        anonymized_df, error = process_anonymization(df, extended_metadata_df, method, params)
        
        if error:
            return jsonify({"error": error}), 500

        # Save the anonymized data to a temporary file
        output_filename = f"anonymized_{uuid.uuid4()}.csv"
        output_path = os.path.join(app.config['ANONYMIZED_FOLDER'], output_filename)
        anonymized_df.to_csv(output_path, index=False)
        
        # Optionally, save a sample
        sample_filename = f"anonymized_sample_{uuid.uuid4()}.csv"
        sample_path = os.path.join(app.config['ANONYMIZED_FOLDER'], sample_filename)
        anonymized_df.head(10).to_csv(sample_path, index=False)
        
        # Clean up the original uploaded file if no longer needed
        os.remove(temp_filename)

        return jsonify({
            "message": "Anonymization completed",
            "download_url": f"/download/{output_filename}",
            "sample_download_url": f"/download/{sample_filename}"
        }), 200

    except Exception as e:
        logger.error(f"Error during anonymization: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    file_path = os.path.join(app.config['ANONYMIZED_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

if __name__ == '__main__':
    app.run(debug=True) # debug=True for development, turn off in production