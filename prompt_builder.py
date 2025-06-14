import logging
import json
from typing import Dict

def build_prompt(smb_row, products_df, feature_analysis: Dict, add_reasoning_to_existing=None):
    """
    Build a prompt for product recommendations using important features identified by feature analyzer.
    
    Args:
        smb_row: Series containing customer data
        products_df: DataFrame containing product information
        feature_analysis: Dictionary containing feature analysis results with scores and reasoning
        # with_reasoning: Boolean flag to include reasoning in the output JSON
        add_reasoning_to_existing: If provided, should be the existing recommendations dict to which reasoning should be added (no re-ranking)
    """
    logging.info(f"Building prompt for BUSINESS_ID={smb_row.get('BUSINESS_ID', '')}")
    
    # Create customer profile using only important features
    important_features = [f["feature_name"] for f in feature_analysis["features"]]
    smb_profile = "\n".join([
        f"{col}: {smb_row.get(col, '')}" 
        for col in important_features 
        if col in smb_row.index and smb_row.get(col, '') != ''
    ])
    
    # Add feature ranking, reasoning, and description section
    feature_ranking_section = "Feature Importance (from analysis):\n"
    for f in feature_analysis["features"]:
        feature_ranking_section += (
            f"- {f['feature_name']} (Importance: {f['importance']})\n"
            f"  Reason: {f.get('reason', 'No reason provided')}\n"
            f"  Description: {f.get('feature_description', 'No description provided')}\n"
        )
    
    # Create product list with all relevant information
    product_list = ""
    for idx, row in products_df.iterrows():
        product_list += f"{idx+1}. {row['Product Name']} (Category: {row['Category']})\n"
        product_list += f"   Cost: {row['Cost']}\n"
        product_list += f"   Description: {row['Description']}\n"
        product_list += f"   Key Features: {row['Key Features']}\n\n"
    
    # If adding reasoning to existing recommendations, use a special prompt
    if add_reasoning_to_existing is not None:
        prompt = f"""
                NBX (Next Best Experience) product recommendation

                Customer Profile (important features only):
                {smb_profile}

                {feature_ranking_section}

                Products:
                {product_list}

                Existing Ranked Recommendations:
                {json.dumps(add_reasoning_to_existing, indent=2)}

                Please add a 'reasoning' field to each recommended product, explaining why it is recommended to this customer, based on the customer profile, product features, and feature analysis.
                Do NOT change the ranking or add/remove products. Only add reasoning.
                Return the same JSON structure, but with a 'reasoning' field added to each product.
                """
        return prompt
    
    prompt = f"""
        NBX (Next Best Experience) product recommendation

        You are an AI assistant for NBX (Next Best Experience) product recommendation. You will be given:
        - A customer/company profile with relevant firmographic and behavioral data.
        - A list of products, each with descriptions, cost and key benefits.

        Your task is to analyze the customer profile, understand their likely needs and context, and return a ranked list of the products from most to least recommended.

        **First, think step by step about:**
        1. What are the most important customer needs and context based on the profile?
        2. Which product features best match those needs?
        3. How would you rank the products for this customer and why? 
               
        **Then, output only the final JSON response in the following format (no explanations in the JSON):**
        {
        "recommended_products": [
            {"rank": 1, "product_name": "Product A"},
            {"rank": 2, "product_name": "Product B"},
            {"rank": 3, "product_name": "Product C"},
            // continue all product
            ...
        ]
        }     

        Customer Profile:
        {smb_profile}

        {feature_ranking_section}

        Products:
        {product_list}

        Return only the JSON response. Do not include any other commentary.
        """
    return prompt 