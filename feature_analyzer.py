import pandas as pd
import json
from typing import List, Dict
import logging
import os
from datetime import datetime
from .genai_client import get_llm_response
from .data_dictionary import get_all_descriptions

def analyze_customer_features(smb_df: pd.DataFrame, products_df: pd.DataFrame, num_features: int = 30, data_dict_path: str = None) -> Dict:
    """
    Analyze customer data to identify the most important features for product recommendations.
    
    Args:
        smb_df: DataFrame containing customer data
        products_df: DataFrame containing product information
        num_features: Number of top features to identify (default: 30)
        data_dict_path: Optional path to Excel file containing data dictionary
    
    Returns:
        Dictionary containing feature analysis results with scores and reasoning
    """
    # Get column descriptions from data dictionary
    column_descriptions = get_all_descriptions(data_dict_path)
    
    # Prepare customer data summary with column descriptions
    customer_summary = {
        "total_customers": len(smb_df),
        "columns": [
            {
                "name": col,
                "description": column_descriptions.get(col, "No description available")
            }
            for col in smb_df.columns
        ],
        "sample_data": smb_df.head(5).to_dict(orient='records')
    }
    
    # Prepare product information
    product_summary = {
        "total_products": len(products_df),
        "product_categories": products_df['Category'].unique().tolist(),
        "products": [
            {
                "name": row['Product Name'],
                "category": row['Category'],
                "cost": row['Cost'],
                "description": row['Description'],
                "key_features": row['Key Features']
            }
            for _, row in products_df.iterrows()
        ]
    }
    
    # Build prompt for feature analysis
    prompt = f"""
    Analyze the following customer data and product information to identify the top {num_features} most important features 
    that would be relevant for product recommendations. Consider factors like:
    - Business characteristics
    - Industry-specific needs
    - Size and scale of operations
    - Geographic location
    - Current services and products
    - Business goals and challenges
    
    Each column in the customer data has a specific meaning and purpose. Use the column descriptions to better understand
    the data and make more informed decisions about feature importance.
    
    Consider the available products and their features when determining which customer attributes are most relevant
    for making accurate product recommendations.
    
    Customer Data Summary:
    {json.dumps(customer_summary, indent=2)}
    
    Product Information:
    {json.dumps(product_summary, indent=2)}
    
    Please provide a JSON response with the following structure:
    {{
        "important_features": [
            {{
                "feature_name": "feature name",
                "importance_score": score (1-10),
                "reasoning": "brief explanation of why this feature is important for product recommendations, considering both customer needs and product characteristics"
            }}
        ]
    }}
    
    Focus on features that would be most relevant for matching customers with appropriate products.
    Consider how each feature might influence product needs and which products would be most suitable
    based on those features.
    """
    
    try:
        # Get LLM response
        response = get_llm_response(prompt)
        
        # Parse response
        features_data = json.loads(response)
        
        # Store the complete feature analysis
        feature_analysis = {
            "features": features_data["important_features"],
            "summary": {
                "total_features_analyzed": len(features_data["important_features"]),
                "average_importance_score": sum(f["importance_score"] for f in features_data["important_features"]) / len(features_data["important_features"]),
                "analysis_timestamp": datetime.now().isoformat()
            }
        }
        
        # Create directory if it doesn't exist
        output_dir = "data/feature_analysis"
        os.makedirs(output_dir, exist_ok=True)
        
        # Save feature analysis to JSON file
        output_file = os.path.join(output_dir, "feature_analysis.json")
        with open(output_file, 'w') as f:
            json.dump(feature_analysis, f, indent=2)
        
        logging.info(f"Successfully identified {len(features_data['important_features'])} important features")
        logging.info(f"Feature analysis saved to {output_file}")
        return feature_analysis
        
    except Exception as e:
        logging.error(f"Error in feature analysis: {str(e)}")
        raise 