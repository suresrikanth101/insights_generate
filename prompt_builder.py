import logging

def build_prompt(smb_row, products_df):
    logging.info(f"Building prompt for BUSINESS_ID={smb_row.get('BUSINESS_ID', '')}")
    smb_profile = "\n".join([f"{col}: {smb_row.get(col, '')}" for col in smb_row.index if smb_row.get(col, '') != ''])
    product_list = ""
    for idx, row in products_df.iterrows():
        product_list += f"{idx+1}. {row['Product Name']} (Category: {row['Category']})\n"
        product_list += f"   Description: {row['Description']}\n"
        product_list += f"   Key Features: {row['Key Features']}\n\n"
    prompt = f"""
NBX (Next Best Experience) product recommendation
You are an AI assistant for NBX (Next Best Experience) product recommendation. You will be given:

A customer/company profile with relevant firmographic and behavioral data

A list of products, each with descriptions and key benefits

Your task is to analyze the customer profile, understand their likely needs and context, and return a ranked list of the products from most to least recommended.

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

Evaluate products based on fit to the customer's industry, size, pain points, growth stage, and any available behavioral signals (e.g., recent engagement or device mix). Prioritize business value, ease of implementation, and relevance to current needs.

Customer Profile:
{smb_profile}

Products:
{product_list}

Return only the JSON response. Do not include any other commentary.
"""
    return prompt 