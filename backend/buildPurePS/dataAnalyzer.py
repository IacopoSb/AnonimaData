# dataAnalyzer.py
import datetime
import pandas as pd
import re
import argparse
from pathlib import Path
import chardet
from io import StringIO, BytesIO # Ensure BytesIO and StringIO are imported

def detect_file_encoding(file_path):
    """Detect the encoding of a file."""
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read())
    return result['encoding']

def detect_delimiter(file_path, encoding):
    """Detect the delimiter used in a text file."""
    with open(file_path, 'r', encoding=encoding) as file:
        first_line = file.readline().strip()
        
    # Common delimiters to check
    delimiters = [',', '\t', '|', ';']
    delimiter_counts = {delimiter: first_line.count(delimiter) for delimiter in delimiters}
    
    # Return the delimiter with the highest count
    if max(delimiter_counts.values()) > 0:
        print(f"Delimiter found: {max(delimiter_counts, key=delimiter_counts.get)}")
        return max(delimiter_counts, key=delimiter_counts.get)
    else:
        print("Delimiter not found, defaulting to ,")
        return ','  # Default to comma if no delimiter is detected

def read_dataset(file_path):
    """Read a dataset from various file formats."""
    file_extension = Path(file_path).suffix.lower()
    
    try:
        if file_extension == '.csv' or file_extension == '.txt':
            # Detect encoding
            encoding = detect_file_encoding(file_path)
            # Detect delimiter
            delimiter = detect_delimiter(file_path, encoding)
            df = pd.read_csv(file_path, encoding=encoding, sep=delimiter)
                
        elif file_extension == '.xlsx' or file_extension == '.xls':
            df = pd.read_excel(file_path)
        elif file_extension == '.json':
            df = pd.read_json(file_path)
        # Add other formats if needed
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
        
        return df
    except Exception as e:
        print(f"Error reading dataset: {e}")
        raise

def read_dataset_for_web(file_stream: (StringIO | BytesIO), filename: str): # Modified signature
    """
    Read a dataset from a file-like object for web upload.
    This function handles CSV, Excel, and JSON files by sniffing their format
    from the filename extension and reads from the provided stream.
    """
    file_extension = Path(filename).suffix.lower()

    try:
        if file_extension == '.csv' or file_extension == '.txt':
            # For CSV/TXT, assume text stream (StringIO). Pandas can read from BytesIO for CSV as well
            # if the content is UTF-8, but StringIO is explicit for text.
            # If the original content for CSV was BytesIO, pd.read_csv can handle it directly.
            df = pd.read_csv(file_stream, sep=None, engine='python') # sep=None to auto-detect delimiter

        elif file_extension == '.xlsx' or file_extension == '.xls':
            # For Excel, assume binary stream (BytesIO)
            df = pd.read_excel(file_stream)
        elif file_extension == '.json':
            # For JSON, assume text stream (StringIO)
            df = pd.read_json(file_stream)
        # Add other formats if needed
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")

        return df
    except Exception as e:
        print(f"Error reading dataset for web: {e}")
        raise

def identify_column_type(series):
    """Identify the general type of data in a Pandas Series."""
    if pd.api.types.is_numeric_dtype(series):
        if all(series.dropna().apply(lambda x: x == int(x))):
            return 'integer'
        return 'float'
    elif pd.api.types.is_datetime64_any_dtype(series):
        return 'datetime'
    # Check for boolean-like strings
    elif series.astype(str).str.lower().isin(['true', 'false', 'yes', 'no', '1', '0']).any():
        return 'boolean'
    elif series.nunique() / len(series) < 0.1 and series.nunique() < 50:
        return 'categorical'
    return 'string'

def structure_dataset(df):
    """
    Structures the dataset by identifying column types and creating a metadata DataFrame.
    """
    metadata_records = []
    
    # Analyze columns for data types and basic statistics
    for col in df.columns:
        original_type = identify_column_type(df[col])
        
        # Convert columns to appropriate types based on identified type
        if original_type == 'datetime':
            # Attempt more robust datetime conversion
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce', infer_datetime_format=True)
            except Exception:
                # If conversion fails, keep as string and log warning
                df[col] = df[col].astype(str)
                original_type = 'string'
                print(f"Warning: Could not convert column '{col}' to datetime. Keeping as string.")
        elif original_type == 'integer':
            # Convert to numeric, then to Int64 to allow NaN
            df[col] = pd.to_numeric(df[col], errors='coerce').astype(pd.Int64Dtype())
        elif original_type == 'float':
            df[col] = pd.to_numeric(df[col], errors='coerce')
        # For 'boolean', 'categorical', 'string', keep as object or convert to string
        else:
            df[col] = df[col].astype(str) # Ensure all non-numeric/datetime are strings

        # Add metadata for the column
        metadata_records.append({
            'column_name': col,
            'data_type': original_type,
            'is_quasi_identifier': False, # Default
            'should_anonymize': False     # Default
        })
    
    metadata_df = pd.DataFrame(metadata_records)
    
    return df, metadata_df

def save_structured_data(df, metadata_df, output_dir):
    """Save the structured DataFrame and its metadata to specified directory."""
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    df_output_path = output_dir_path / f"structured_data_{timestamp}.csv"
    metadata_output_path = output_dir_path / f"metadata_{timestamp}.json"

    df.to_csv(df_output_path, index=False)
    metadata_df.to_json(metadata_output_path, orient='records', indent=4)

    print(f"Structured data saved to: {df_output_path}")
    print(f"Metadata saved to: {metadata_output_path}")

def main():
    parser = argparse.ArgumentParser(description='Structure a dataset into a standard format.')
    parser.add_argument('input_file', help='Path to the input dataset file.')
    parser.add_argument('--output_dir', default='output', help='Directory to save the output files.')
    
    args = parser.parse_args()
    
    try:
        # Read the dataset
        df = read_dataset(args.input_file)
        
        # Structure the dataset
        structured_df, metadata = structure_dataset(df)
        
        # Save the structured data
        save_structured_data(structured_df, metadata, args.output_dir)
        
    except Exception as e:
        print(f"An error occurred: {e}")
        import sys
        sys.exit(1)

if __name__ == "__main__":
    main()