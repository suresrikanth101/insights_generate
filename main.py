import json
from tqdm import tqdm
from nbx_recom.config import *
from nbx_recom.scraper import scrape_marketplace, save_products_csv
from nbx_recom.data_utils import load_smb_data
from nbx_recom.prompt_builder import build_prompt
from nbx_recom.genai_client import get_recommendations
import pandas as pd
import os
PRODUCTS_URL='https://www.verizon.com/business/products/verizon-marketplace'
PRODUCTS_CSV_PATH='data/products.csv'
SMB_DATA_PATH='data/smb_data.csv'
OUTPUT_PATH='data/output/recommendations.json'
def main():
    # 1. Scrape products (or load from CSV if already scraped)
    if os.path.exists(PRODUCTS_CSV_PATH):
        products_df = pd.read_csv(PRODUCTS_CSV_PATH)
    else:
        print("Scraping products from marketplace...")
        products_df = scrape_marketplace(PRODUCTS_URL)
        save_products_csv(products_df, PRODUCTS_CSV_PATH)
        print(f"Saved products to {PRODUCTS_CSV_PATH}")

    # 2. Load SMB data
    smb_df = load_smb_data(SMB_DATA_PATH)

    # 3. For each SMB, build prompt, call GenAI, save JSON
    all_results = []
    for idx, smb_row in tqdm(smb_df.iterrows(), total=smb_df.shape[0]):
        prompt = build_prompt(smb_row, products_df)
        try:
            rec_json = get_recommendations(prompt)
        except Exception as e:
            rec_json = json.dumps({"error": str(e)})
        all_results.append({
            "BUSINESS_ID": smb_row.get("BUSINESS_ID", ""),
            "LEGAL_NAME": smb_row.get("LEGAL_NAME", ""),
            "recommendations": rec_json
        })

    # 4. Save all results
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"Saved recommendations to {OUTPUT_PATH}")

if __name__ == "__main__":
    main() 