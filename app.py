import streamlit as st
import pandas as pd
import json
import logging
from src.data_utils import load_smb_data
from src.scraper import scrape_marketplace
from src.prompt_builder import build_prompt
from src.genai_client import get_llm_response
from main import clean_json_response
from src.config import SMB_DATA_PATH, PRODUCTS_CSV_PATH, PRODUCTS_URL, DATA_DICT_PATH
from src.feature_analyzer import analyze_customer_features
import os

def setup_logging():
    logging.basicConfig(level=logging.INFO)

def load_data():
    try:
        smb_df = pd.read_csv(SMB_DATA_PATH)
        logging.info(f"Loaded SMB data from {SMB_DATA_PATH} with {len(smb_df)} rows.")
        return smb_df
    except Exception as e:
        logging.error(f"Failed to load SMB data: {e}")
        return pd.DataFrame()

def load_products():
    try:
        if os.path.exists(PRODUCTS_CSV_PATH):
            products_df = pd.read_excel(PRODUCTS_CSV_PATH, engine="openpyxl")
            logging.info(f"Loaded products from {PRODUCTS_CSV_PATH}")
        else:
            logging.info("Scraping products from marketplace...")
            products_df = scrape_marketplace(PRODUCTS_URL)
        return products_df
    except Exception as e:
        logging.error(f"Failed to load or scrape products: {e}")
        return pd.DataFrame()

def load_or_create_feature_analysis(smb_df, products_df):
    feature_analysis_path = "data/feature_analysis/feature_analysis.json"
    if os.path.exists(feature_analysis_path):
        try:
            with open(feature_analysis_path, 'r') as f:
                feature_analysis = json.load(f)
            logging.info("Loaded existing feature analysis")
            return feature_analysis
        except Exception as e:
            logging.warning(f"Error loading existing feature analysis: {e}")
    logging.info("Creating new feature analysis...")
    return analyze_customer_features(smb_df, products_df, data_dict_path=DATA_DICT_PATH)

def main():
    setup_logging()
    st.title("NBX Recommendations Generator")
    # verizon_logo_path = "assets/logo.png"  # Uncomment and use if you have a logo
    # st.image(verizon_logo_path, width=50)
    st.write("Enter a Business ID to generate product recommendations.")

    business_id = st.text_input("Enter Business ID", value="")

    if st.button("Generate Recommendations"):
        if not business_id.isdigit():
            st.error("Please enter a valid numeric Business ID.")
            return
        business_id = int(business_id)
        smb_df = load_data()
        products_df = load_products()
        if smb_df.empty or products_df.empty:
            st.error("Failed to load necessary data. Please check logs.")
            return
        # Load or create feature analysis
        feature_analysis = load_or_create_feature_analysis(smb_df, products_df)
        # Filter SMB data for the given Business ID
        smb_row = smb_df[smb_df['BUSINESS_ID'] == business_id]
        if smb_row.empty:
            st.error(f"No SMB found with Business ID={business_id}")
            return
        try:
            smb_row = smb_row.iloc[0]
            prompt = build_prompt(smb_row, products_df, feature_analysis)
            rec_json = get_llm_response(prompt)
            cleaned = clean_json_response(rec_json)
            recommendations = json.loads(cleaned)
            st.success("Recommendations generated successfully!")
            st.json(recommendations)
        except Exception as e:
            logging.error(f"Error generating recommendations: {e}")
            st.error(f"Failed to generate recommendations: {e}")

if __name__ == "__main__":
    main() 