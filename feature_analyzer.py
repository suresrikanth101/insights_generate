import pandas as pd
import json
from typing import List, Dict
import logging
import os
from datetime import datetime
from .genai_client import get_llm_response

def analyze_customer_features(smb_df: pd.DataFrame, num_features: int = 30) -> Dict:
    """
    Analyze customer data to identify the most important features for product recommendations.
    
    Args:
        smb_df: DataFrame containing customer data
        num_features: Number of top features to identify (default: 30)
    
    Returns:
        Dictionary containing feature analysis results with scores and reasoning
    """
    # Prepare customer data summary
    customer_summary = {
        "total_customers": len(smb_df),
        "columns": list(smb_df.columns),
        "sample_data": smb_df.head(5).to_dict(orient='records')
    }
    
    # Build prompt for feature analysis
    prompt = f"""
    Analyze the following customer data and identify the top {num_features} most important features 
    that would be relevant for product recommendations. Consider factors like:
    - Business characteristics
    - Industry-specific needs
    - Size and scale of operations
    - Geographic location
    - Current services and products
    - Business goals and challenges
    
    Customer Data Summary:
    {json.dumps(customer_summary, indent=2)}
    
    Please provide a JSON response with the following structure:
    {{
        "important_features": [
            {{
                "feature_name": "feature name",
                "importance_score": score (1-10),
                "reasoning": "brief explanation"
            }}
        ]
    }}
    
    Focus on features that would be most relevant for matching customers with appropriate products.
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