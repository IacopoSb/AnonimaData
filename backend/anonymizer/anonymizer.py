import pandas as pd
import numpy as np
import argparse
from pathlib import Path
import random
import hashlib
import logging
from collections import Counter, defaultdict
from sklearn.preprocessing import KBinsDiscretizer
from sklearn.cluster import KMeans
import json
import uuid
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Anonymizer:
    """Base class for anonymization algorithms."""
    def __init__(self, df, metadata):
        self.df = df.copy()
        self.metadata = metadata
        self.column_types = dict(zip(metadata['column_name'], metadata['data_type']))
        
        # Check if metadata has user selections (extended metadata)
        self.has_user_selections = 'is_quasi_identifier' in metadata.columns and 'should_anonymize' in metadata.columns
        
        if self.has_user_selections:
            logger.info("Using extended metadata with user selections")
            self.user_qi_selections = dict(zip(metadata['column_name'], metadata['is_quasi_identifier']))
            self.user_anon_selections = dict(zip(metadata['column_name'], metadata['should_anonymize']))
        else:
            logger.warning("No user selections found in metadata. Using automatic detection.")
            self.user_qi_selections = {}
            self.user_anon_selections = {}
        
    def anonymize(self):
        """Abstract method to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement anonymize method")
    
    def get_quasi_identifiers(self):
        """Return columns selected by user as quasi-identifiers, or auto-detect if no selections."""
        if self.has_user_selections:
            # Use user selections
            qi_columns = [col for col, is_qi in self.user_qi_selections.items() if is_qi]
            logger.info(f"Using user-selected quasi-identifiers: {qi_columns}")
            return qi_columns
        else:
            # Fallback to automatic detection
            logger.info("No user selections found, using automatic quasi-identifier detection")
            potential_qis = []
            for col, dtype in self.column_types.items():
                if dtype in ['text', 'alphanumeric', 'date', 'numeric']:
                    potential_qis.append(col)
            return potential_qis

    def get_sensitive_attributes(self):
        """Return columns that should be anonymized based on user selection or auto-detection."""
        if self.has_user_selections:
            # Use user selections for anonymization
            sensitive_cols = [col for col, should_anon in self.user_anon_selections.items() if should_anon]
            logger.info(f"Using user-selected columns for anonymization: {sensitive_cols}")
            return sensitive_cols
        else:
            # Fallback to automatic detection
            logger.info("No user selections found, using automatic sensitive attribute detection")
            sensitive = []
            for col, dtype in self.column_types.items():
                if dtype in ['email', 'phone_number']:
                    sensitive.append(col)
            return sensitive
    
    def get_columns_to_preserve(self):
        """Return columns that should NOT be anonymized."""
        if self.has_user_selections:
            preserve_cols = [col for col, should_anon in self.user_anon_selections.items() if not should_anon]
            logger.info(f"Preserving columns (not anonymizing): {preserve_cols}")
            return preserve_cols
        else:
            return []
    
    def save_result(self, output_path):
        """Save the anonymized dataframe to a CSV file."""
        self.df.to_csv(output_path, index=False)
        logger.info(f"Anonymized data saved to {output_path}")
        
        # Also save a sample of rows for quick inspection
        sample_path = output_path.replace('.csv', '_sample.csv')
        self.df.head(10).to_csv(sample_path, index=False)
        logger.info(f"Sample of anonymized data saved to {sample_path}")
        
        return self.df

class KAnonymityAnonymizer(Anonymizer):
    """Implements k-anonymity by generalizing quasi-identifiers."""
    
    def __init__(self, df, metadata, k=3):
        super().__init__(df, metadata)
        self.k = k
        
    def anonymize(self):
        logger.info(f"Applying k-anonymity with k={self.k}")
        
        # Get user-selected quasi-identifiers
        quasi_identifiers = self.get_quasi_identifiers()
        if not quasi_identifiers:
            logger.warning("No quasi-identifiers found. Skipping k-anonymity.")
            return self.df
        
        # Limit to reasonable number of quasi-identifiers to avoid excessive sparsity
        if len(quasi_identifiers) > 5:
            logger.warning(f"Many quasi-identifiers selected ({len(quasi_identifiers)}). This may cause excessive data sparsity.")
            logger.info(f"Consider using fewer quasi-identifiers for better results.")
            
        logger.info(f"Using quasi-identifiers: {quasi_identifiers}")
        
        # Step 1: Generalize only the quasi-identifier columns
        self._generalize_columns(quasi_identifiers)
        
        # Step 2: Check for k-anonymity and suppress groups smaller than k
        self._enforce_k_anonymity(quasi_identifiers)
        
        return self.df
    
    def _generalize_columns(self, columns):
        """Generalize columns based on their data type."""
        
        for col in columns:
            if col not in self.df.columns:
                logger.warning(f"Column {col} not found in dataset. Skipping.")
                continue
                
            dtype = self.column_types.get(col, 'unknown')
            
            if pd.api.types.is_numeric_dtype(self.df[col]):
                # Generalize numeric columns using binning
                logger.info(f"Generalizing numeric column: {col}")
                n_bins = min(10, max(2, self.df[col].nunique() // self.k))
                
                # Handle the case where all values are the same
                if self.df[col].nunique() <= 1:
                    logger.info(f"Column {col} has only one unique value. Skipping generalization.")
                    continue
                    
                try:
                    # Use quantile binning to create more balanced bins
                    discretizer = KBinsDiscretizer(n_bins=n_bins, encode='ordinal', strategy='quantile')
                    
                    # Reshape for sklearn and handle NaN values
                    values = self.df[col].fillna(self.df[col].mean()).values.reshape(-1, 1)
                    bins = discretizer.fit_transform(values).flatten()
                    
                    # Create range labels for the bins
                    bin_edges = discretizer.bin_edges_[0]
                    bin_labels = [f"{bin_edges[i]:.2f}-{bin_edges[i+1]:.2f}" for i in range(len(bin_edges)-1)]
                    
                    # Map bin indices to labels
                    self.df[col] = [bin_labels[int(b)] if not pd.isna(self.df[col].iloc[i]) else np.nan 
                                     for i, b in enumerate(bins)]
                except Exception as e:
                    logger.error(f"Error generalizing column {col}: {e}")
                    
            elif dtype == 'date':
                # Generalize dates to month or year level
                logger.info(f"Generalizing date column: {col}")
                try:
                    self.df[col] = pd.to_datetime(self.df[col], errors='coerce')
                    # For dates, generalize to month-year
                    self.df[col] = self.df[col].dt.strftime('%Y-%m')
                except Exception as e:
                    logger.error(f"Error generalizing date column {col}: {e}")
                    
            elif dtype in ['text', 'alphanumeric']:
                # For text columns, truncate or mask partially
                logger.info(f"Generalizing text column: {col}")
                try:
                    # Keep first character and mask the rest
                    self.df[col] = self.df[col].astype(str).apply(
                        lambda x: x[0] + '*' * (len(x) - 1) if len(x) > 1 else x)
                except Exception as e:
                    logger.error(f"Error generalizing text column {col}: {e}")
    
    def _enforce_k_anonymity(self, quasi_identifiers):
        """Ensure each combination of quasi-identifiers appears at least k times."""
        if not quasi_identifiers:
            return
            
        # Verify all quasi-identifiers exist in the dataframe
        valid_qis = [qi for qi in quasi_identifiers if qi in self.df.columns]
        if not valid_qis:
            logger.warning("No valid quasi-identifiers found in dataframe.")
            return
            
        # Count occurrences of each combination of quasi-identifiers
        group_counts = self.df.groupby(valid_qis).size()
        
        # Identify groups smaller than k
        small_groups = group_counts[group_counts < self.k].index.tolist()
        
        if small_groups:
            logger.info(f"Found {len(small_groups)} groups with fewer than {self.k} records. Applying suppression...")
            
            # Create a mask for rows belonging to small groups
            if len(valid_qis) == 1:
                # Handle single column case
                mask = self.df[valid_qis[0]].isin(small_groups)
            else:
                # Handle multiple columns case
                mask = self.df[valid_qis].apply(tuple, axis=1).isin([tuple(g) if isinstance(g, (list, tuple)) else (g,) for g in small_groups])
            
            # Get columns that should be anonymized
            columns_to_anonymize = self.get_sensitive_attributes()
            columns_to_preserve = self.get_columns_to_preserve()
            
            # Apply suppression only to rows in small groups
            for col in self.df.columns:
                if col in columns_to_preserve:
                    # Skip columns that user wants to preserve
                    logger.info(f"Preserving column {col} as requested by user")
                    continue
                    
                if col in columns_to_anonymize or col in valid_qis:
                    if pd.api.types.is_numeric_dtype(self.df[col]) and col not in valid_qis:
                        # For numeric sensitive attributes, use range suppression
                        min_val = self.df[col].min()
                        max_val = self.df[col].max()
                        self.df.loc[mask, col] = f"[{min_val:.2f}-{max_val:.2f}]"
                    else:
                        # For quasi-identifiers and text attributes, use generic suppression
                        self.df.loc[mask, col] = '***SUPPRESSED***'
        else:
            logger.info("All groups satisfy k-anonymity requirement.")

class LDiversityAnonymizer(KAnonymityAnonymizer):
    """Extends k-anonymity with l-diversity for sensitive attributes."""
    
    def __init__(self, df, metadata, k=3, l=2):
        super().__init__(df, metadata, k)
        self.l = l
        
    def anonymize(self):
        logger.info(f"Applying l-diversity with k={self.k}, l={self.l}")
        
        # First apply k-anonymity
        super().anonymize()
        
        # Get user-selected sensitive attributes
        sensitive_attrs = self.get_sensitive_attributes()
        if not sensitive_attrs:
            logger.warning("No sensitive attributes selected for anonymization. Skipping l-diversity.")
            return self.df
            
        # Get quasi-identifiers
        quasi_identifiers = self.get_quasi_identifiers()
        if not quasi_identifiers:
            logger.warning("No quasi-identifiers selected. Skipping l-diversity.")
            return self.df
            
        # Verify columns exist
        valid_qis = [qi for qi in quasi_identifiers if qi in self.df.columns]
        valid_sensitive = [sa for sa in sensitive_attrs if sa in self.df.columns]
        
        if not valid_qis or not valid_sensitive:
            logger.warning("No valid quasi-identifiers or sensitive attributes found.")
            return self.df
            
        logger.info(f"Using quasi-identifiers: {valid_qis}")
        logger.info(f"Using sensitive attributes: {valid_sensitive}")
        
        # Apply l-diversity for each sensitive attribute
        for sensitive_attr in valid_sensitive:
            self._enforce_l_diversity(valid_qis, sensitive_attr)
            
        return self.df
        
    def _enforce_l_diversity(self, quasi_identifiers, sensitive_attr):
        """Ensure each group has at least l distinct values for the sensitive attribute."""
        if sensitive_attr not in self.df.columns:
            return
            
        # For each group of quasi-identifiers, count distinct values of sensitive attribute
        diversity_counts = self.df.groupby(quasi_identifiers)[sensitive_attr].nunique()
        
        # Identify groups with diversity less than l
        low_diversity_groups = diversity_counts[diversity_counts < self.l].index.tolist()
        
        if low_diversity_groups:
            logger.info(f"Found {len(low_diversity_groups)} groups with diversity less than {self.l} for {sensitive_attr}. Applying suppression...")
            
            # Create a mask for rows belonging to low diversity groups
            if len(quasi_identifiers) == 1:
                mask = self.df[quasi_identifiers[0]].isin(low_diversity_groups)
            else:
                mask = self.df[quasi_identifiers].apply(tuple, axis=1).isin([tuple(g) if isinstance(g, (list, tuple)) else (g,) for g in low_diversity_groups])
            
            # Suppression - replace sensitive attribute values with general category
            self.df.loc[mask, sensitive_attr] = '***DIVERSE***'
        else:
            logger.info(f"All groups satisfy l-diversity requirement for {sensitive_attr}.")

class DifferentialPrivacyAnonymizer(Anonymizer):
    """Implements differential privacy by adding noise to numeric data."""
    
    def __init__(self, df, metadata, epsilon=1.0):
        super().__init__(df, metadata)
        self.epsilon = epsilon  # Privacy parameter (smaller = more privacy)
        
    def anonymize(self):
        logger.info(f"Applying differential privacy with epsilon={self.epsilon}")
        
        # Get columns selected for anonymization
        columns_to_anonymize = self.get_sensitive_attributes()
        columns_to_preserve = self.get_columns_to_preserve()
        
        if not columns_to_anonymize:
            logger.warning("No columns selected for anonymization.")
            return self.df
        
        logger.info(f"Applying differential privacy to: {columns_to_anonymize}")
        logger.info(f"Preserving: {columns_to_preserve}")
        
        # Apply differential privacy to selected columns
        for col in columns_to_anonymize:
            if col in columns_to_preserve:
                logger.info(f"Skipping {col} - marked for preservation")
                continue
                
            if col not in self.df.columns:
                logger.warning(f"Column {col} not found in dataset")
                continue
                
            dtype = self.column_types.get(col, 'unknown')
            
            # For numerical columns, add Laplace noise
            if pd.api.types.is_numeric_dtype(self.df[col]):
                self._add_laplace_noise(col)
            # For categorical columns, use randomized response
            elif dtype in ['text', 'alphanumeric', 'email', 'phone_number']:
                self._apply_randomized_response(col)
        
        return self.df
    
    def _add_laplace_noise(self, column):
        """Add Laplace noise to a numeric column to achieve differential privacy."""
        if column not in self.df.columns:
            return
            
        try:
            # Skip if column contains non-numeric values
            if not pd.api.types.is_numeric_dtype(self.df[column]):
                return
                
            logger.info(f"Adding Laplace noise to {column}")
            
            # Calculate sensitivity (using range as a simple approximation)
            data_range = self.df[column].max() - self.df[column].min()
            if data_range == 0:
                logger.info(f"Column {column} has no variance. Skipping noise addition.")
                return
                
            sensitivity = data_range * 0.01  # Using 1% of range as sensitivity
            
            # Add Laplace noise to each value
            scale = sensitivity / self.epsilon
            noise = np.random.laplace(0, scale, size=len(self.df))
            
            # Add noise to the data
            self.df[column] = self.df[column] + noise
            
            # Round to reasonable precision to avoid exposing too much information
            decimal_places = max(0, int(-np.log10(scale)) + 1)
            self.df[column] = self.df[column].round(decimal_places)
            
        except Exception as e:
            logger.error(f"Error applying Laplace noise to {column}: {e}")
    
    def _apply_randomized_response(self, column):
        """Apply randomized response to categorical data."""
        if column not in self.df.columns:
            return
            
        try:
            logger.info(f"Applying randomized response to {column}")
            
            # Probability of returning true value
            p = 1 / (1 + np.exp(self.epsilon))
            
            # Get unique values for randomization
            unique_values = self.df[column].dropna().unique().tolist()
            if not unique_values:
                logger.warning(f"No values found for randomized response in {column}")
                return
            
            # For each value, decide whether to randomize
            for i in range(len(self.df)):
                if random.random() < p and not pd.isna(self.df.at[i, column]):
                    # Randomly select another value from the column
                    self.df.at[i, column] = random.choice(unique_values)
                        
        except Exception as e:
            logger.error(f"Error applying randomized response to {column}: {e}")

def process_anonymization(df: pd.DataFrame, metadata: pd.DataFrame, method: str, params: dict):
    """Process the dataset with the specified anonymization method."""
    try:
        logger.info(f"Loaded dataset with {len(df)} rows and {len(df.columns)} columns")
        
        # Create anonymizer based on method
        if method == "k-anonymity":
            k = params.get("k", 3)
            anonymizer = KAnonymityAnonymizer(df, metadata, k=k)
        elif method == "l-diversity":
            k = params.get("k", 3)
            l = params.get("l", 2)
            anonymizer = LDiversityAnonymizer(df, metadata, k=k, l=l)
        elif method == "differential-privacy":
            epsilon = params.get("epsilon", 1.0)
            anonymizer = DifferentialPrivacyAnonymizer(df, metadata, epsilon=epsilon)
        else:
            logger.error(f"Unknown anonymization method: {method}")
            return None, "Unknown anonymization method"
        
        # Apply anonymization
        anonymized_df = anonymizer.anonymize()
        
        # Instead of saving to a file directly, return the DataFrame
        # The web server will handle saving/serving the file
        logger.info("Anonymization completed successfully! Returning anonymized DataFrame.")
        return anonymized_df, None
        
    except Exception as e:
        logger.error(f"Error during anonymization: {e}")
        return None, str(e)
"""
def main():
    parser = argparse.ArgumentParser(description="Advanced anonymization algorithms for datasets with user-defined parameters")
    parser.add_argument("--input", required=True, help="Path to the input structured CSV file")
    parser.add_argument("--metadata", required=True, help="Path to the extended metadata CSV file (from parameterSelector)")
    parser.add_argument("--output", required=True, help="Path to save the anonymized output")
    parser.add_argument("--method", default="k-anonymity", choices=["k-anonymity", "l-diversity", "differential-privacy"], 
                       help="Anonymization method to use")
    parser.add_argument("--k", type=int, default=3, help="k value for k-anonymity (default: 3)")
    parser.add_argument("--l", type=int, default=2, help="l value for l-diversity (default: 2)")
    parser.add_argument("--epsilon", type=float, default=1.0, help="Epsilon for differential privacy (default: 1.0)")
    
    args = parser.parse_args()
    
    # Prepare parameters based on the method
    params = {}
    if args.method == "k-anonymity":
        params["k"] = args.k
    elif args.method == "l-diversity":
        params["k"] = args.k
        params["l"] = args.l
    elif args.method == "differential-privacy":
        params["epsilon"] = args.epsilon
    
    # Process the anonymization
    result = process_anonymization(args.input, args.metadata, args.output, args.method, params)
    
    if result is not None:
        logger.info("Anonymization completed successfully!")
    else:
        logger.error("Anonymization failed!")

if __name__ == "__main__":
    main()
"""