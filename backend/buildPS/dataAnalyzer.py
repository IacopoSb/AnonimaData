import pandas as pd
import re
import argparse
from pathlib import Path
import chardet

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
            
            # Try to read with header
            df = pd.read_csv(file_path, delimiter=delimiter, encoding=encoding)
            
            # If the first row seems to be data instead of headers
            if all(isinstance(col, int) for col in df.columns) or all(col.isdigit() for col in df.columns if isinstance(col, str)):
                df = pd.read_csv(file_path, delimiter=delimiter, header=None, encoding=encoding)
                
        elif file_extension == '.xlsx' or file_extension == '.xls':
            df = pd.read_excel(file_path)
        elif file_extension == '.json':
            df = pd.read_json(file_path)
        elif file_extension == '.xml':
            df = pd.read_xml(file_path)
        elif file_extension == '.parquet':
            df = pd.read_parquet(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
        
        return df
    except Exception as e:
        print(f"Error reading dataset: {e}")
        raise

def identify_column_type(column):  
    """Identify the data type of a column."""
    # Drop NA values for type detection
    clean_column = column.dropna()
    
    if len(clean_column) == 0:
        return "empty"
    
    # Check if all values are numeric
    if pd.api.types.is_numeric_dtype(clean_column):
        # Check if potentially a phone number
        if clean_column.astype(str).str.len().mean() > 8:
            return "phone_number"
        return "numeric"
    
    # Convert to string for pattern matching
    sample = clean_column.astype(str).iloc[:100]  # Sample for efficiency
    
    # Check for email pattern
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if all(bool(email_pattern.match(str(value))) for value in sample if not pd.isna(value)):
        return "email"
    
    # Check for date pattern
    if pd.api.types.is_datetime64_dtype(clean_column) or pd.to_datetime(clean_column, errors='coerce').notna().all():
        return "date"
    
    # Check if alphanumeric (contains both letters and numbers)
    has_letters = any(any(c.isalpha() for c in str(value)) for value in sample)
    has_digits = any(any(c.isdigit() for c in str(value)) for value in sample)
    
    if has_letters and has_digits:
        return "alphanumeric"
    elif has_letters:
        return "text"
    elif has_digits:
        return "numeric"
    
    return "other"

def structure_dataset(df):
    """Structure the dataset and identify column types."""
    # Create a new DataFrame to store column metadata
    metadata = pd.DataFrame({
        'column_name': df.columns,
        'data_type': [identify_column_type(df[col]) for col in df.columns]
        # colonna tipoAnonmizzazione, k, l, epsilon
    })
    
    return df, metadata

def save_structured_data(df, metadata, output_dir):
    """Save the structured data and metadata."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Save the structured data
    df.to_csv(f"{output_dir}/structured_data.csv", index=False)
    
    # Save the metadata
    metadata.to_csv(f"{output_dir}/metadata.csv", index=False)
    
    print(f"Structured data saved to {output_dir}/structured_data.csv")
    print(f"Metadata saved to {output_dir}/metadata.csv")
    
    # Print column types for user reference
    print("\nColumn Types Identified:")
    for _, row in metadata.iterrows():
        print(f"Column: {row['column_name']} - Type: {row['data_type']}")

def read_dataset_for_web(file_content, file_extension):
    """Read a dataset from various file formats from file content."""
    try:
        if file_extension == '.csv' or file_extension == '.txt':
            # For web, we might get file content as string/bytes
            # For simplicity, assume it's a string, or you'll need BytesIO
            from io import StringIO
            df = pd.read_csv(StringIO(file_content), sep=None, engine='python') # sep=None to auto-detect delimiter
                
        elif file_extension == '.xlsx' or file_extension == '.xls':
            from io import BytesIO
            df = pd.read_excel(BytesIO(file_content))
        elif file_extension == '.json':
            from io import StringIO
            df = pd.read_json(StringIO(file_content))
        # Add other formats if needed
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
        
        return df
    except Exception as e:
        print(f"Error reading dataset for web: {e}")
        raise

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
        print(f"Error: {e}")

if __name__ == "__main__":
    main()