import os
import json
import logging
import re
from typing import Dict, Any, Union
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure OpenAI API
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

openai.api_key = OPENAI_API_KEY

def clean_response(response_text: str) -> str:
    """
    Clean and normalize the LLM response to ensure it's valid JSON.
    
    Args:
        response_text: Raw response text from LLM
        
    Returns:
        Cleaned response text that should be valid JSON
    """
    # Remove any leading/trailing whitespace
    response_text = response_text.strip()
    
    # Remove markdown code blocks
    response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
    response_text = re.sub(r'\s*```$', '', response_text)
    
    # Find JSON content between curly braces
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        response_text = json_match.group(0)
    
    # Remove any non-JSON text before or after the JSON object
    response_text = response_text.strip()
    
    # Basic JSON validation
    try:
        # Try to parse and re-serialize to ensure valid JSON
        json_obj = json.loads(response_text)
        response_text = json.dumps(json_obj)
    except json.JSONDecodeError as e:
        logging.warning(f"Initial JSON cleaning failed: {str(e)}")
        # If initial cleaning fails, try more aggressive cleaning
        response_text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', response_text)  # Remove control characters
        response_text = re.sub(r'[^\x20-\x7E]', '', response_text)  # Keep only printable ASCII
        response_text = re.sub(r',\s*}', '}', response_text)  # Remove trailing commas
        response_text = re.sub(r',\s*]', ']', response_text)  # Remove trailing commas in arrays
    
    return response_text

def get_llm_response(prompt: str, response_type: str = "feature_analysis") -> Union[str, Dict]:
    """
    Get response from OpenAI's GPT model.
    
    Args:
        prompt: The prompt to send to the model
        response_type: Type of response expected ("feature_analysis" or "recommendations")
    
    Returns:
        The model's response as either a string or dictionary
    """
    try:
        # Configure system message based on response type
        system_messages = {
            "feature_analysis": "You are a helpful assistant that analyzes customer data and provides responses in valid JSON format. Always ensure your response is a valid JSON object.",
            "recommendations": "You are a product recommendation expert that provides responses in valid JSON format. Always ensure your response is a valid JSON object."
        }
        
        system_message = system_messages.get(response_type, system_messages["feature_analysis"])
        
        # Generate response using OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-4",  # or "gpt-3.5-turbo" based on your needs
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent JSON responses
            max_tokens=1000
        )
        
        # Extract the text from the response
        response_text = response.choices[0].message.content
        
        # Log the raw response for debugging
        logging.debug(f"Raw LLM response for {response_type}: {response_text}")
        
        # First check if response is already a dictionary
        if isinstance(response_text, dict):
            return response_text
            
        # If response is a string, process it
        if not isinstance(response_text, str):
            raise ValueError(f"Unexpected response type: {type(response_text)}")
        
        # Clean the response
        cleaned_response = clean_response(response_text)
        
        # Validate and parse the cleaned response
        try:
            json_obj = json.loads(cleaned_response)
            return json_obj
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON response from LLM. Error: {str(e)}")
            logging.error(f"Original response: {response_text}")
            logging.error(f"Cleaned response: {cleaned_response}")
            raise ValueError(f"LLM response is not valid JSON: {str(e)}")
        
    except Exception as e:
        logging.error(f"Error getting LLM response for {response_type}: {str(e)}")
        raise 