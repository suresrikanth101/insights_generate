"""
Data dictionary for SMB (Small and Medium Business) data columns.
This dictionary provides descriptions of what each column represents in the dataset.
"""

import pandas as pd
import os
import logging
from typing import Dict

def load_data_dictionary(excel_path: str) -> Dict[str, str]:
    """
    Load data dictionary from Excel file.
    
    Args:
        excel_path: Path to Excel file containing data dictionary
        
    Returns:
        Dictionary mapping column names to their descriptions
    """
    try:
        if not os.path.exists(excel_path):
            logging.warning(f"Data dictionary not found at {excel_path}")
            return {}
            
        df = pd.read_excel(excel_path)
        
        # Create dictionary, handling empty descriptions
        data_dict = {}
        for _, row in df.iterrows():
            col_name = str(row['column_name']).strip()
            description = str(row['description']).strip() if pd.notna(row['description']) else ""
            
            if not col_name:
                logging.warning("Found empty column name in data dictionary, skipping...")
                continue
                
            if not description:
                logging.warning(f"No description provided for column '{col_name}', using default message")
                description = f"Column '{col_name}' - No description available"
                
            data_dict[col_name] = description
            
        logging.info(f"Successfully loaded data dictionary with {len(data_dict)} columns")
        return data_dict
        
    except Exception as e:
        logging.error(f"Error loading data dictionary: {e}")
        return {}

def get_all_descriptions(excel_path: str = None) -> Dict[str, str]:
    """
    Get all column descriptions from the Excel data dictionary.
    
    Args:
        excel_path: Path to Excel file containing data dictionary
        
    Returns:
        Dictionary mapping column names to their descriptions
    """
    if not excel_path:
        logging.warning("No data dictionary path provided")
        return {}
        
    return load_data_dictionary(excel_path) 