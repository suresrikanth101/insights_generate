import logging
import json
from typing import Dict

def build_prompt(smb_row, products_df, feature_analysis: Dict):
    """
    Build a prompt for product recommendations using important features identified by feature analyzer.
    
    Args:
        smb_row: Series containing customer data
        products_df: DataFrame containing product information
        feature_analysis: Dictionary containing feature analysis results with scores and reasoning
    """
    logging.info(f"Building prompt for BUSINESS_ID={smb_row.get('BUSINESS_ID', '')}")
    
    # Create customer profile using only important features
    important_features = [f["feature_name"] for f in feature_analysis["features"]]
    smb_profile = "\n".join([
        f"{col}: {smb_row.get(col, '')}" 
        for col in important_features 
        if col in smb_row.index and smb_row.get(col, '') != ''
    ])
    
    # Create product list with all relevant information
    product_list = ""
    for idx, row in products_df.iterrows():
        product_list += f"{idx+1}. {row['Product Name']} (Category: {row['Category']})\n"
        product_list += f"   Cost: {row['Cost']}\n"
        product_list += f"   Description: {row['Description']}\n"
        product_list += f"   Key Features: {row['Key Features']}\n\n"
    
    prompt = f"""
NBX (Next Best Experience) product recommendation
You are an AI assistant for NBX (Next Best Experience) product recommendation. You will be given:

A customer/company profile with relevant firmographic and behavioral data

A list of products, each with descriptions, cost, and key benefits

Your task is to analyze the customer profile using the provided important features, understand their likely needs and context, and return a ranked list of the products from most to least recommended.

Please output your response in the following JSON format:

{{
"recommendations": [
    {{
        "rank": 1,
        "product_name": "Product A",
        "reasoning": "Short explanation of why this product is the top recommendation"
    }},
    // continue for all products
]
}}

Important Features Analysis:
{json.dumps(feature_analysis, indent=2)}

Customer Profile (Based on Important Features):
{smb_profile}

Products:
{product_list}

Return only the JSON response. Do not include any other commentary.
"""
    return prompt 