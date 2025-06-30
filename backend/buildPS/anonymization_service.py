import pandas as pd
import logging
import os
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

from message_broker import get_broker, Topics, Message
from anonymizer import process_anonymization

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AnonymizationService:
    """
    Servizio completo per l'anonimizzazione dei dataset.
    Subscriber del topic 'data_analyzed' e publisher verso 'data_anonymized'.
    Supporta tutti i metodi di anonimizzazione implementati nell'anonymizer.
    """
    
    def __init__(self, output_folder='anonymized_data'):
        self.broker = get_broker()
        self.output_folder = output_folder
        self.broker.subscribe(Topics.DATA_ANALYZED, self.handle_anonymization_request)
        
        # Create output folder if it doesn't exist
        os.makedirs(self.output_folder, exist_ok=True)
        
        # Initialize supported methods with their parameter schemas
        self._initialize_method_schemas()
        
    def _initialize_method_schemas(self):
        """Inizializza gli schemi dei parametri per ogni metodo di anonimizzazione."""
        self.method_schemas = {
            'k_anonymity': {
                'parameters': {
                    'k': {'type': 'int', 'default': 3, 'min': 2, 'max': 100, 'description': 'Minimum group size for k-anonymity'}
                },
                'description': 'Groups records so each combination of quasi-identifiers appears at least k times',
                'requires_quasi_identifiers': True,
                'supports_sensitive_attributes': False
            },
            'l_diversity': {
                'parameters': {
                    'k': {'type': 'int', 'default': 3, 'min': 2, 'max': 100, 'description': 'Minimum group size for k-anonymity'},
                    'l': {'type': 'int', 'default': 2, 'min': 2, 'max': 50, 'description': 'Minimum diversity for sensitive attributes'}
                },
                'description': 'Extends k-anonymity ensuring each group has at least l distinct sensitive values',
                'requires_quasi_identifiers': True,
                'supports_sensitive_attributes': True
            },
            't_closeness': {
                'parameters': {
                    'k': {'type': 'int', 'default': 3, 'min': 2, 'max': 100, 'description': 'Minimum group size for k-anonymity'},
                    't': {'type': 'float', 'default': 0.1, 'min': 0.01, 'max': 0.99, 'description': 'Maximum distance threshold for t-closeness'}
                },
                'description': 'Ensures sensitive attribute distribution in each group is close to overall distribution',
                'requires_quasi_identifiers': True,
                'supports_sensitive_attributes': True
            },
            'differential_privacy': {
                'parameters': {
                    'epsilon': {'type': 'float', 'default': 1.0, 'min': 0.1, 'max': 10.0, 'description': 'Privacy parameter (smaller = more privacy)'}
                },
                'description': 'Adds statistical noise to ensure differential privacy',
                'requires_quasi_identifiers': False,
                'supports_sensitive_attributes': True
            },
            'suppression': {
                'parameters': {
                    'threshold': {'type': 'float', 'default': 0.05, 'min': 0.01, 'max': 0.5, 'description': 'Suppression threshold (proportion of data to suppress)'}
                },
                'description': 'Removes or masks selected data values',
                'requires_quasi_identifiers': False,
                'supports_sensitive_attributes': True
            },
            'generalization': {
                'parameters': {
                    'levels': {'type': 'int', 'default': 2, 'min': 1, 'max': 10, 'description': 'Number of generalization levels'}
                },
                'description': 'Replaces specific values with more general ones',
                'requires_quasi_identifiers': True,
                'supports_sensitive_attributes': False
            },
            'perturbation': {
                'parameters': {
                    'noise_level': {'type': 'float', 'default': 0.1, 'min': 0.01, 'max': 1.0, 'description': 'Amount of noise to add (0-1)'},
                    'method': {'type': 'string', 'default': 'gaussian', 'options': ['gaussian', 'uniform', 'laplace'], 'description': 'Type of noise distribution'}
                },
                'description': 'Adds controlled noise to numerical data',
                'requires_quasi_identifiers': False,
                'supports_sensitive_attributes': True
            }
        }
        
    def start(self):
        """Avvia il servizio di anonimizzazione"""
        logger.info("Starting Anonymization Service...")
        logger.info(f"Available methods: {list(self.method_schemas.keys())}")
        logger.info(f"Output folder: {self.output_folder}")
        
        self.broker.start_listening()
        logger.info("Anonymization Service is listening for messages...")
        
        try:
            # Mantieni il servizio in esecuzione
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down Anonymization Service...")
            self.broker.stop_listening()
    
    def handle_anonymization_request(self, message: Message):
        """
        Gestisce la richiesta di anonimizzazione.
        Applica l'algoritmo specificato e pubblica i risultati.
        """
        job_id = None
        try:
            logger.info(f"Processing anonymization request: {message.id}")
            
            # Estrai i dati dal messaggio
            job_id = message.data.get('job_id')
            method = message.data.get('method')
            params = message.data.get('params', {})
            user_selections = message.data.get('user_selections', [])
            file_path = message.data.get('file_path')
            metadata_path = message.data.get('metadata_path')
            
            if not all([job_id, method, file_path]):
                raise ValueError("Missing required data in anonymization request")
            
            # Validate method and parameters
            validation_result = self.validate_anonymization_request(method, params, user_selections)
            if not validation_result['valid']:
                raise ValueError(f"Invalid request: {validation_result['error']}")
            
            # Aggiorna lo status del job
            self._update_job_status(job_id, 'anonymizing', {
                'stage': 'loading_data',
                'method': method,
                'params': params,
                'progress': 10
            })
            
            # Leggi il dataset originale
            logger.info(f"Loading dataset for anonymization: {file_path}")
            df = self._load_dataset(file_path)
            
            # Aggiorna lo status
            self._update_job_status(job_id, 'anonymizing', {
                'stage': 'preparing_metadata',
                'method': method,
                'rows': len(df),
                'columns': len(df.columns),
                'progress': 30
            })
            
            # Prepara i metadati estesi con le selezioni dell'utente
            extended_metadata = self._prepare_extended_metadata(metadata_path, user_selections, df)
            
            # Aggiorna lo status
            self._update_job_status(job_id, 'anonymizing', {
                'stage': 'applying_anonymization',
                'method': method,
                'algorithm': method,
                'progress': 50
            })
            
            # Applica l'anonimizzazione
            logger.info(f"Applying {method} anonymization for job {job_id}")
            anonymized_df, error = process_anonymization(df, extended_metadata, method, params)
            
            if error:
                raise Exception(f"Anonymization failed: {error}")
            
            if anonymized_df is None:
                raise Exception("Anonymization returned no data")
            
            # Aggiorna lo status
            self._update_job_status(job_id, 'anonymizing', {
                'stage': 'saving_results',
                'method': method,
                'progress': 80
            })
            
            # Genera nomi file per i risultati
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"anonymized_{method}_{job_id}_{timestamp}.csv"
            sample_filename = f"sample_{method}_{job_id}_{timestamp}.csv"
            
            output_path = os.path.join(self.output_folder, output_filename)
            sample_path = os.path.join(self.output_folder, sample_filename)
            
            # Salva i risultati
            logger.info(f"Saving anonymized data for job {job_id}")
            anonymized_df.to_csv(output_path, index=False)
            
            # Crea un campione per anteprima
            sample_size = min(100, len(anonymized_df))
            anonymized_df.head(sample_size).to_csv(sample_path, index=False)
            
            # Calcola statistiche di anonimizzazione
            stats = self._calculate_anonymization_stats(df, anonymized_df, method, params)
            
            # Aggiorna lo status finale
            completion_data = {
                'method': method,
                'params': params,
                'anonymized_file_path': output_path,
                'sample_file_path': sample_path,
                'output_filename': output_filename,
                'sample_filename': sample_filename,
                'original_rows': len(df),
                'anonymized_rows': len(anonymized_df),
                'stats': stats,
                'anonymized_at': datetime.now().isoformat(),
                'progress': 100
            }
            
            self.broker.set_job_status(job_id, 'completed', completion_data)
            
            # Pubblica evento di completamento
            completion_message = {
                'job_id': job_id,
                'method': method,
                'params': params,
                'anonymized_file_path': output_path,
                'sample_file_path': sample_path,
                'output_filename': output_filename,
                'sample_filename': sample_filename,
                'stats': stats,
                'completed_at': datetime.now().isoformat()
            }
            
            self.broker.publish(Topics.DATA_ANONYMIZED, completion_message)
            
            logger.info(f"Anonymization completed for job {job_id}")
            
            # Cleanup: rimuovi i file temporanei se necessario
            self._cleanup_temp_files(file_path, metadata_path)
            
        except Exception as e:
            logger.error(f"Error processing anonymization request {message.id}: {e}")
            
            # Aggiorna lo status con errore
            if job_id:
                error_data = {
                    'error': str(e),
                    'stage': 'anonymization_failed',
                    'method': locals().get('method', 'unknown'),
                    'error_at': datetime.now().isoformat()
                }
                
                self.broker.set_job_status(job_id, 'error', error_data)
                
                # Pubblica evento di errore
                error_message = {
                    'job_id': job_id,
                    'stage': 'anonymization',
                    'error': str(e),
                    'method': locals().get('method', 'unknown'),
                    'original_message_id': message.id,
                    'error_at': datetime.now().isoformat()
                }
                
                self.broker.publish(Topics.ERROR_OCCURRED, error_message)
    
    def _update_job_status(self, job_id: str, status: str, data: dict):
        """Helper per aggiornare lo status del job"""
        try:
            self.broker.set_job_status(job_id, status, data)
        except Exception as e:
            logger.warning(f"Failed to update job status for {job_id}: {e}")
    
    def _load_dataset(self, file_path: str) -> pd.DataFrame:
        """Carica il dataset dal percorso specificato"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Dataset file not found: {file_path}")
                
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension == '.csv':
                df = pd.read_csv(file_path)
            elif file_extension in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            elif file_extension == '.json':
                df = pd.read_json(file_path)
            elif file_extension == '.txt':
                # Assume it's a CSV with different extension
                df = pd.read_csv(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
            
            if df.empty:
                raise ValueError("Dataset is empty")
                
            logger.info(f"Loaded dataset: {len(df)} rows, {len(df.columns)} columns")
            return df
                
        except Exception as e:
            logger.error(f"Error loading dataset from {file_path}: {e}")
            raise
    
    def _prepare_extended_metadata(self, metadata_path: str, user_selections: list, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepara i metadati estesi combinando quelli dell'analisi con le selezioni dell'utente
        """
        try:
            # Carica i metadati dall'analisi se disponibili
            if metadata_path and os.path.exists(metadata_path):
                metadata = pd.read_csv(metadata_path)
                logger.info(f"Loaded metadata from {metadata_path}")
            else:
                logger.warning("Metadata file not found, creating from dataset")
                # Crea metadati di base dal dataset
                metadata = self._create_basic_metadata(df)
            
            # Assicurati che le colonne necessarie esistano
            required_columns = ['column_name', 'data_type']
            for col in required_columns:
                if col not in metadata.columns:
                    if col == 'column_name':
                        metadata['column_name'] = df.columns.tolist()
                    elif col == 'data_type':
                        metadata['data_type'] = [self._infer_data_type(df[col]) for col in df.columns]
            
            # Aggiungi colonne per le selezioni dell'utente se non esistono
            if 'is_quasi_identifier' not in metadata.columns:
                metadata['is_quasi_identifier'] = False
            if 'should_anonymize' not in metadata.columns:
                metadata['should_anonymize'] = False
            if 'anonymization_type' not in metadata.columns:
                metadata['anonymization_type'] = ''
            if 'anonymization_params' not in metadata.columns:
                metadata['anonymization_params'] = '{}'
            
            # Applica le selezioni dell'utente
            if user_selections:
                logger.info(f"Applying {len(user_selections)} user selections")
                for selection in user_selections:
                    column_name = selection.get('column')
                    is_qi = selection.get('is_quasi_identifier', False)
                    should_anonymize = selection.get('should_anonymize', False)
                    anonymization_type = selection.get('anonymization_type', '')
                    anonymization_params = selection.get('params', {})
                    
                    # Trova o crea la riga per questa colonna
                    if column_name in metadata['column_name'].values:
                        # Aggiorna i metadati esistenti
                        mask = metadata['column_name'] == column_name
                        metadata.loc[mask, 'is_quasi_identifier'] = is_qi
                        metadata.loc[mask, 'should_anonymize'] = should_anonymize
                        metadata.loc[mask, 'anonymization_type'] = anonymization_type
                        metadata.loc[mask, 'anonymization_params'] = json.dumps(anonymization_params)
                    else:
                        # Aggiungi nuova riga
                        new_row = pd.DataFrame({
                            'column_name': [column_name],
                            'data_type': [self._infer_data_type(df[column_name]) if column_name in df.columns else 'unknown'],
                            'is_quasi_identifier': [is_qi],
                            'should_anonymize': [should_anonymize],
                            'anonymization_type': [anonymization_type],
                            'anonymization_params': [json.dumps(anonymization_params)]
                        })
                        metadata = pd.concat([metadata, new_row], ignore_index=True)
            
            # Filtra solo le colonne che esistono nel dataset
            metadata = metadata[metadata['column_name'].isin(df.columns)]
            
            logger.info(f"Prepared metadata for {len(metadata)} columns")
            return metadata
            
        except Exception as e:
            logger.error(f"Error preparing extended metadata: {e}")
            # Ritorna metadati di base in caso di errore
            return self._create_basic_metadata(df)
    
    def _create_basic_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """Crea metadati di base dal dataframe"""
        metadata_data = []
        for col in df.columns:
            metadata_data.append({
                'column_name': col,
                'data_type': self._infer_data_type(df[col]),
                'is_quasi_identifier': False,
                'should_anonymize': False,
                'anonymization_type': '',
                'anonymization_params': '{}'
            })
        
        return pd.DataFrame(metadata_data)
    
    def _infer_data_type(self, series: pd.Series) -> str:
        """Inferisce il tipo di dato di una serie"""
        if pd.api.types.is_numeric_dtype(series):
            return 'numeric'
        elif pd.api.types.is_datetime64_any_dtype(series):
            return 'date'
        elif series.dtype == 'object':
            # Controlla se potrebbe essere un email o telefono
            sample_values = series.dropna().head(10).astype(str)
            if sample_values.str.contains('@').any():
                return 'email'
            elif sample_values.str.contains(r'[\d\-\+\(\)\s]+').all():
                return 'phone_number'
            else:
                return 'text'
        else:
            return 'text'
    
    def _calculate_anonymization_stats(self, original_df: pd.DataFrame, anonymized_df: pd.DataFrame, 
                                     method: str, params: dict) -> dict:
        """Calcola statistiche sull'anonimizzazione applicata"""
        stats = {
            'method': method,
            'parameters': params,
            'original_shape': original_df.shape,
            'anonymized_shape': anonymized_df.shape,
            'data_retention_rate': len(anonymized_df) / len(original_df) if len(original_df) > 0 else 0,
            'columns_processed': [],
            'suppression_rate': 0,
            'generalization_applied': False
        }
        
        try:
            # Calcola statistiche per colonna
            for col in original_df.columns:
                if col in anonymized_df.columns:
                    col_stats = {
                        'column': col,
                        'original_unique_values': original_df[col].nunique(),
                        'anonymized_unique_values': anonymized_df[col].nunique(),
                        'suppressed_values': 0,
                        'generalized_values': 0
                    }
                    
                    # Conta valori soppressi
                    if anonymized_df[col].dtype == 'object':
                        suppressed_count = anonymized_df[col].str.contains('SUPPRESSED|DIVERSE|\*', na=False).sum()
                        col_stats['suppressed_values'] = suppressed_count
                        
                        # Conta valori generalizzati (range o categorie)
                        generalized_count = anonymized_df[col].str.contains('-|\[|\]', na=False).sum()
                        col_stats['generalized_values'] = generalized_count
                    
                    stats['columns_processed'].append(col_stats)
            
            # Calcola tasso di soppressione globale
            total_suppressed = sum([col['suppressed_values'] for col in stats['columns_processed']])
            total_cells = len(anonymized_df) * len(anonymized_df.columns)
            stats['suppression_rate'] = total_suppressed / total_cells if total_cells > 0 else 0
            
            # Determina se è stata applicata generalizzazione
            stats['generalization_applied'] = any([col['generalized_values'] > 0 for col in stats['columns_processed']])
            
        except Exception as e:
            logger.warning(f"Error calculating anonymization stats: {e}")
            
        return stats
    
    def _cleanup_temp_files(self, *file_paths):
        """Pulisce i file temporanei"""
        for file_path in file_paths:
            try:
                if file_path and os.path.exists(file_path):
                    # Non eliminare i file originali, solo quelli temporanei con prefissi specifici
                    basename = os.path.basename(file_path)
                    if any(prefix in basename for prefix in ['temp_', '_metadata', '_structured', 'tmp_']):
                        os.remove(file_path)
                        logger.info(f"Cleaned up temp file: {file_path}")
            except Exception as e:
                logger.warning(f"Could not clean up file {file_path}: {e}")
    
    def get_available_methods(self) -> List[str]:
        """Restituisce la lista dei metodi di anonimizzazione disponibili"""
        return list(self.method_schemas.keys())
    
    def get_method_info(self, method: str) -> Dict[str, Any]:
        """Restituisce informazioni dettagliate su un metodo di anonimizzazione"""
        if method not in self.method_schemas:
            return {'error': f'Unknown method: {method}'}
        
        return self.method_schemas[method]
    
    def get_all_methods_info(self) -> Dict[str, Any]:
        """Restituisce informazioni su tutti i metodi disponibili"""
        return self.method_schemas
    
    def validate_anonymization_request(self, method: str, params: dict, user_selections: list) -> Dict[str, Any]:
        """
        Valida una richiesta di anonimizzazione completa
        """
        try:
            # Controlla se il metodo esiste
            if method not in self.method_schemas:
                return {
                    'valid': False,
                    'error': f'Unknown anonymization method: {method}. Available methods: {list(self.method_schemas.keys())}'
                }
            
            schema = self.method_schemas[method]
            
            # Valida i parametri del metodo
            param_validation = self.validate_anonymization_params(method, params)
            if not param_validation[0]:
                return {
                    'valid': False,
                    'error': f'Invalid parameters: {param_validation[1]}'
                }
            
            # Controlla i requisiti del metodo
            if schema.get('requires_quasi_identifiers', False):
                has_qi = any(sel.get('is_quasi_identifier', False) for sel in user_selections)
                if not has_qi:
                    return {
                        'valid': False,
                        'error': f'Method {method} requires at least one quasi-identifier to be selected'
                    }
            
            if schema.get('supports_sensitive_attributes', False):
                # Se il metodo supporta attributi sensibili, controlla che ne sia selezionato almeno uno
                # solo per metodi che li richiedono esplicitamente
                if method in ['l_diversity', 't_closeness']:
                    has_sensitive = any(sel.get('should_anonymize', False) for sel in user_selections)
                    if not has_sensitive:
                        return {
                            'valid': False,
                            'error': f'Method {method} requires at least one sensitive attribute to be selected'
                        }
            
            return {
                'valid': True,
                'error': None,
                'method_info': schema
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'Validation error: {str(e)}'
            }
    
    def validate_anonymization_params(self, method: str, params: dict) -> Tuple[bool, str]:
        """
        Valida i parametri per un metodo di anonimizzazione specifico
        Restituisce (is_valid, error_message)
        """
        try:
            if method not in self.method_schemas:
                return False, f"Unknown method: {method}"
            
            schema = self.method_schemas[method]
            parameter_schema = schema.get('parameters', {})
            
            # Valida ogni parametro
            for param_name, param_config in parameter_schema.items():
                if param_name in params:
                    value = params[param_name]
                    param_type = param_config.get('type')
                    
                    # Controlla il tipo
                    if param_type == 'int' and not isinstance(value, int):
                        try:
                            value = int(value)
                            params[param_name] = value  # Converte automaticamente
                        except (ValueError, TypeError):
                            return False, f"Parameter {param_name} must be an integer"
                    
                    elif param_type == 'float' and not isinstance(value, (int, float)):
                        try:
                            value = float(value)
                            params[param_name] = value  # Converte automaticamente
                        except (ValueError, TypeError):
                            return False, f"Parameter {param_name} must be a number"
                    
                    elif param_type == 'string' and not isinstance(value, str):
                        return False, f"Parameter {param_name} must be a string"
                    
                    # Controlla i range per parametri numerici
                    if param_type in ['int', 'float']:
                        if 'min' in param_config and value < param_config['min']:
                            return False, f"Parameter {param_name} must be >= {param_config['min']}"
                        if 'max' in param_config and value > param_config['max']:
                            return False, f"Parameter {param_name} must be <= {param_config['max']}"
                    
                    # Controlla le opzioni per parametri stringa
                    if param_type == 'string' and 'options' in param_config:
                        if value not in param_config['options']:
                            return False, f"Parameter {param_name} must be one of: {param_config['options']}"
            
            # Imposta valori di default per parametri mancanti
            for param_name, param_config in parameter_schema.items():
                if param_name not in params:
                    params[param_name] = param_config.get('default')
            
            # Validazioni specifiche per metodo
            if method == 'l_diversity' and 'k' in params and 'l' in params:
                if params['l'] > params['k']:
                    return False, "l-diversity parameter 'l' cannot be greater than 'k'"
            
            return True, ""
            
        except Exception as e:
            return False, f"Parameter validation error: {str(e)}"

def main():
    """Avvia il servizio di anonimizzazione"""
    # Controlla se esiste la cartella di output
    output_folder = os.environ.get('ANONYMIZED_DATA_FOLDER', 'anonymized_data')
    
    service = AnonymizationService(output_folder=output_folder)
    
    logger.info("=== ANONYMIZATION SERVICE STARTING ===")
    logger.info(f"Available anonymization methods: {service.get_available_methods()}")
    logger.info(f"Output folder: {output_folder}")
    
    # Mostra informazioni sui metodi disponibili
    for method in service.get_available_methods():
        info = service.get_method_info(method)
        logger.info(f"Method '{method}': {info.get('description', 'No description')}")
    
    service.start()

if __name__ == "__main__":
    main()