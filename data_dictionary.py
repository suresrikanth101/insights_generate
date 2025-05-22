"""
Data dictionary for SMB (Small and Medium Business) data columns.
This dictionary provides descriptions of what each column represents in the dataset.
"""

import pandas as pd
import os
import logging
from typing import Dict

def load_data_dictionary(excel_path: str = "data/data_dictionary.xlsx") -> Dict[str, str]:
    """
    Load data dictionary from Excel file.
    
    Args:
        excel_path: Path to the Excel file containing data dictionary
        
    Returns:
        Dictionary mapping column names to their descriptions
    """
    try:
        # Check if file exists
        if not os.path.exists(excel_path):
            logging.warning(f"Data dictionary Excel file not found at {excel_path}. Using default dictionary.")
            return SMB_DATA_DICTIONARY
            
        # Read Excel file
        df = pd.read_excel(excel_path)
        
        # Validate required columns
        required_columns = ['column_name', 'description']
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"Excel file must contain columns: {required_columns}")
            
        # Create dictionary from Excel data
        data_dict = dict(zip(df['column_name'], df['description']))
        
        logging.info(f"Successfully loaded data dictionary from {excel_path}")
        return data_dict
        
    except Exception as e:
        logging.error(f"Error loading data dictionary from Excel: {str(e)}")
        logging.warning("Using default data dictionary")
        return SMB_DATA_DICTIONARY

# Default data dictionary (fallback)
SMB_DATA_DICTIONARY = {
    "BUSINESS_ID": "Unique identifier for each business",
    "LEGAL_NAME": "Official legal name of the business",
    "DBA_NAME": "Doing Business As name (alternative business name)",
    "BUSINESS_TYPE": "Type of business entity (e.g., Corporation, LLC, Sole Proprietorship)",
    "INDUSTRY_CODE": "Standard industry classification code",
    "INDUSTRY_DESCRIPTION": "Description of the business industry",
    "EMPLOYEE_COUNT": "Number of employees in the business",
    "ANNUAL_REVENUE": "Annual revenue of the business",
    "BUSINESS_AGE": "Number of years the business has been operating",
    "LOCATION_TYPE": "Type of business location (e.g., Retail, Office, Warehouse)",
    "SQUARE_FOOTAGE": "Size of business premises in square feet",
    "CUSTOMER_BASE_SIZE": "Estimated number of customers",
    "DIGITAL_PRESENCE": "Indicates if business has online presence (website, social media)",
    "CURRENT_SERVICES": "List of services currently used by the business",
    "TECHNOLOGY_USAGE": "Level of technology adoption in the business",
    "PAYMENT_METHODS": "Payment methods accepted by the business",
    "SECURITY_REQUIREMENTS": "Security needs and requirements",
    "COMPLIANCE_REQUIREMENTS": "Regulatory compliance requirements",
    "GROWTH_PLAN": "Business growth plans and objectives",
    "PAIN_POINTS": "Current challenges and pain points",
    "BUDGET_RANGE": "Budget range for new services/products",
    "DECISION_MAKER_ROLE": "Role of the primary decision maker",
    "PURCHASE_TIMELINE": "Expected timeline for new purchases",
    "COMPETITORS": "Main competitors in the market",
    "TARGET_MARKET": "Target market segment",
    "GEOGRAPHIC_COVERAGE": "Geographic area of operation",
    "OPERATING_HOURS": "Business operating hours",
    "SEASONAL_PATTERNS": "Seasonal business patterns",
    "CUSTOMER_FEEDBACK": "Recent customer feedback and ratings",
    "MARKET_TRENDS": "Relevant market trends affecting the business",
    "INNOVATION_READINESS": "Business readiness for new technologies",
    "INTEGRATION_REQUIREMENTS": "Requirements for integrating new solutions",
    "SCALABILITY_NEEDS": "Business scalability requirements",
    "DISASTER_RECOVERY": "Disaster recovery and business continuity needs",
    "DATA_STORAGE_NEEDS": "Data storage and management requirements",
    "NETWORK_REQUIREMENTS": "Network infrastructure requirements",
    "MOBILITY_NEEDS": "Mobile and remote work requirements",
    "CUSTOMER_SERVICE_NEEDS": "Customer service and support requirements",
    "REPORTING_NEEDS": "Business reporting and analytics needs",
    "AUTOMATION_POTENTIAL": "Areas for potential automation"
}

def get_all_descriptions(excel_path: str = None) -> dict:
    """
    Get the complete data dictionary.
    
    Args:
        excel_path: Optional path to Excel file containing data dictionary
        
    Returns:
        Dictionary containing all column descriptions
    """
    if excel_path:
        return load_data_dictionary(excel_path)
    return SMB_DATA_DICTIONARY 