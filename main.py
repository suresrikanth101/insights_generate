import json
from tqdm import tqdm
from nbx_recom.config import *
from nbx_recom.scraper import scrape_marketplace, save_products_csv
from nbx_recom.data_utils import load_smb_data
from nbx_recom.prompt_builder import build_prompt
from nbx_recom.genai_client import get_recommendations
from nbx_recom.feature_analyzer import analyze_customer_features
import pandas as pd
import os
import logging
import re

def setup_logging():
    os.makedirs('logs', exist_ok=True)
    logging.basicConfig(
        filename='logs/nbx_recom.log',
        filemode='a',
        format='%(asctime)s %(levelname)s: %(message)s',
        level=logging.INFO
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

def list_smb_columns(smb_df: pd.DataFrame, output_path: str = "data/smb_columns.csv"):
    """
    List all SMB data columns and save them to a CSV file.
    
    Args:
        smb_df: DataFrame containing SMB data
        output_path: Path to save the columns CSV file
    """
    try:
        # Create a DataFrame with column information
        columns_info = pd.DataFrame({
            'column_name': smb_df.columns,
            'data_type': smb_df.dtypes.astype(str),
            'non_null_count': smb_df.count(),
            'null_count': smb_df.isnull().sum(),
            'unique_values': [smb_df[col].nunique() for col in smb_df.columns],
            'sample_values': [str(smb_df[col].dropna().head(3).tolist()) for col in smb_df.columns]
        })
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save to CSV
        columns_info.to_csv(output_path, index=False)
        logging.info(f"Saved SMB columns information to {output_path}")
        
        # Print summary
        print(f"\nSMB Data Columns Summary:")
        print(f"Total columns: {len(smb_df.columns)}")
        print(f"Columns information saved to: {output_path}")
        print("\nFirst few columns:")
        print(columns_info.head().to_string())
        
    except Exception as e:
        logging.error(f"Failed to list SMB columns: {e}")
        raise

def clean_json_response(response):
    """
    Clean JSON response from LLM.
    
    Args:
        response: Response from LLM (can be string or dict)
        
    Returns:
        Cleaned response as string
    """
    # If response is a dictionary, convert to string first
    if isinstance(response, dict):
        response = json.dumps(response)
    # If response is not a string, raise error
    elif not isinstance(response, str):
        raise ValueError(f"Unexpected response type: {type(response)}")
        
    # Clean the response string
    # Remove markdown code block markers
    response = re.sub(r"^```json|^```|```$", "", response.strip(), flags=re.MULTILINE)
    # Remove leading 'json\n' or similar
    response = re.sub(r"^json\s*", "", response.strip(), flags=re.IGNORECASE)
    # Strip whitespace
    response = response.strip()
    
    # Validate and re-format JSON
    try:
        # Parse and re-serialize to ensure consistent formatting
        json_obj = json.loads(response)
        return json.dumps(json_obj, indent=2)
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON after cleaning: {str(e)}")
        logging.error(f"Response text: {response}")
        raise ValueError(f"Invalid JSON after cleaning: {str(e)}")

def main():
    setup_logging()
    logging.info('NBX Recommendation pipeline started.')
    
    # 1. Load products data
    try:
        if os.path.exists(PRODUCTS_CSV_PATH):
            products_df = pd.read_csv(PRODUCTS_CSV_PATH)
            logging.info(f"Loaded products from {PRODUCTS_CSV_PATH}")
        else:
            logging.info("Scraping products from marketplace...")
            products_df = scrape_marketplace(PRODUCTS_URL)
            save_products_csv(products_df, PRODUCTS_CSV_PATH)
            logging.info(f"Saved products to {PRODUCTS_CSV_PATH}")
    except Exception as e:
        logging.error(f"Failed to load or scrape products: {e}")
        return

    # 2. Load SMB data
    try:
        smb_df = load_smb_data(SMB_DATA_PATH)
        logging.info(f"Loaded SMB data from {SMB_DATA_PATH} with {len(smb_df)} rows.")
        
        # List SMB columns
        list_smb_columns(smb_df)
    except Exception as e:
        logging.error(f"Failed to load SMB data: {e}")
        return

    # 3. Analyze customer data to identify important features
    try:
        logging.info("Analyzing customer data to identify important features...")
        feature_analysis = analyze_customer_features(smb_df)
        logging.info(f"Identified {feature_analysis['summary']['total_features_analyzed']} important features")
    except Exception as e:
        logging.error(f"Failed to analyze customer features: {e}")
        return

    # 4. Prompt user for BUSINESS_ID
    try:
        TARGET_BUSINESS_ID = int(input("Enter the BUSINESS_ID to process: "))
    except ValueError:
        logging.error("Invalid BUSINESS_ID entered. Please enter a numeric value.")
        return

    # Filter the DataFrame to just this business
    smb_df = smb_df[smb_df["BUSINESS_ID"] == TARGET_BUSINESS_ID]
    if smb_df.empty:
        logging.error(f"No SMB found with BUSINESS_ID={TARGET_BUSINESS_ID}")
        print(f"No SMB found with BUSINESS_ID={TARGET_BUSINESS_ID}")
        return

    # 5. Generate recommendations using identified features
    all_results = []
    for idx, smb_row in tqdm(smb_df.iterrows(), total=smb_df.shape[0]):
        try:
            prompt = build_prompt(smb_row, products_df, feature_analysis)
            rec_json = get_recommendations(prompt)
            # Clean and parse the JSON response
            cleaned_json = clean_json_response(rec_json)
            recommendations = json.loads(cleaned_json)
            logging.info(f"Generated recommendations for BUSINESS_ID={smb_row.get('BUSINESS_ID','')}.")
        except Exception as e:
            recommendations = {"error": str(e)}
            logging.error(f"Error for BUSINESS_ID={smb_row.get('BUSINESS_ID','')}: {e}")
        all_results.append({
            "BUSINESS_ID": smb_row.get("BUSINESS_ID", ""),
            "LEGAL_NAME": smb_row.get("LEGAL_NAME", ""),
            "feature_analysis": feature_analysis,
            "recommendations": recommendations
        })

    # 6. Save all results
    try:
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            json.dump(all_results, f, indent=2)
        logging.info(f"Saved recommendations to {OUTPUT_PATH}")
    except Exception as e:
        logging.error(f"Failed to save recommendations: {e}")

    logging.info('NBX Recommendation pipeline finished.')

if __name__ == "__main__":
    main() 