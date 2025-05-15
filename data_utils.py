import pandas as pd
import logging

RELEVANT_COLS = [
    'BUSINESS_ID', 'LEGAL_NAME', 'NAICS_DESC', 'NAICS_CODE', 'TOTAL_EMPLOYEE_COUNT', 'ANNUAL_REVENUE',
    'NUMBER_OF_LOCATIONS', 'SMARTPHONE', 'TABLET', 'LINE4G', 'LINESG', 'MBB', 'ONETALK', 'OTHER',
    'SECURITY_PRODUCT', 'OUTOFCONTRACT', 'CHURN_RISK_SEG', 'CHURNMODE1', 'CHURNMODE2', 'CHURNMODE3',
    'SATISFIED', 'FRUSTRATED', 'INTENT_MOBILITY_CX', 'INTENT_SECURITY', 'INTENT_NETWORKS',
    'TMP_UPGRADE_LINES', 'FUTURE_5G_AVAILABILITY_YN', 'STATE', 'CITY', 'ZIPCODE', 'MAJOR_OS', 'PRIMARY_WEBSITE'
]

def load_smb_data(path):
    logging.info(f"Loading SMB data from {path}")
    try:
        df = pd.read_excel(path)
        cols = [c for c in RELEVANT_COLS if c in df.columns]
        logging.info(f"Loaded {len(df)} rows and {len(cols)} relevant columns.")
        missing_cols = set(RELEVANT_COLS) - set(df.columns)
        if missing_cols:
            logging.warning(f"Missing columns in SMB data: {missing_cols}")
        return df[cols]
    except Exception as e:
        logging.error(f"Error loading SMB data: {e}")
        return pd.DataFrame() 