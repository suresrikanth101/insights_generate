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

def get_recommendations_with_reasoning(base_recommendations, smb_row, products_df, feature_analysis):
    """Add reasoning to existing recommendations"""
    try:
        # Create a prompt that includes the existing rankings
        ranked_products = [item["product_name"] for item in base_recommendations["recommended_products"]]
        prompt = f"""
        Given these ranked product recommendations for a business:
        {json.dumps(base_recommendations, indent=2)}

        Please add reasoning for each recommendation, explaining why each product is recommended in this order.
        Return the same JSON structure but with a 'reasoning' field added to each product.
        """
        
        rec_json = get_llm_response(prompt, temperature=0.1)
        cleaned = clean_json_response(rec_json)
        return json.loads(cleaned)
    except Exception as e:
        logging.error(f"Error adding reasoning: {e}")
        raise

def main():
    setup_logging()
    st.title("NBX Recommendations Generator")
    # verizon_logo_path = "assets/logo.png"  # Uncomment and use if you have a logo
    # st.image(verizon_logo_path, width=50)
    st.write("Enter a Business ID to generate product recommendations.")

    business_id = st.text_input("Enter Business ID", value="")

    if not business_id:
        st.info("Please enter a Business ID to get started.")
        return

    if not business_id.isdigit():
        st.error("Please enter a valid numeric Business ID.")
        return

    business_id = int(business_id)

    # Load data ONCE
    smb_df = load_data()
    products_df = load_products()
    if smb_df.empty or products_df.empty:
        st.error("Failed to load necessary data. Please check logs.")
        return
    feature_analysis = load_or_create_feature_analysis(smb_df, products_df)
    smb_row = smb_df[smb_df['BUSINESS_ID'] == business_id]
    if smb_row.empty:
        st.error(f"No SMB found with Business ID={business_id}")
        return
    smb_row = smb_row.iloc[0]

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("Get Recommendations (Without Reasoning)"):
            with st.spinner("Generating recommendations..."):
                try:
                    prompt = build_prompt(smb_row, products_df, feature_analysis, with_reasoning=False)
                    rec_json = get_llm_response(prompt, temperature=0.1)
                    cleaned = clean_json_response(rec_json)
                    recommendations = json.loads(cleaned)
                    # Store in session state for the "With Reasoning" button
                    st.session_state['base_recommendations'] = recommendations
                    st.success("Recommendations generated successfully!")
                    st.json(recommendations)
                except Exception as e:
                    logging.error(f"Error generating recommendations: {e}")
                    st.error(f"Failed to generate recommendations: {e}")

    with col2:
        if st.button("Get Recommendations (With Reasoning)"):
            with st.spinner("Adding reasoning to recommendations..."):
                try:
                    if 'base_recommendations' not in st.session_state:
                        st.error("Please generate recommendations without reasoning first.")
                        return
                    
                    recommendations_with_reasoning = get_recommendations_with_reasoning(
                        st.session_state['base_recommendations'],
                        smb_row,
                        products_df,
                        feature_analysis
                    )
                    st.success("Recommendations with reasoning generated successfully!")
                    st.json(recommendations_with_reasoning)
                except Exception as e:
                    logging.error(f"Error generating recommendations: {e}")
                    st.error(f"Failed to generate recommendations: {e}")

if __name__ == "__main__":
    main() 