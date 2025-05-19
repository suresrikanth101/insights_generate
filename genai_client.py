import os
import json
import logging
from typing import Dict, Any
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure OpenAI API
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

openai.api_key = OPENAI_API_KEY

def get_llm_response(prompt: str) -> str:
    """
    Get response from OpenAI's GPT model.
    
    Args:
        prompt: The prompt to send to the model
    
    Returns:
        The model's response as a string
    """
    try:
        # Generate response using OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-4",  # or "gpt-3.5-turbo" based on your needs
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides responses in valid JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent JSON responses
            max_tokens=1000
        )
        
        # Extract the text from the response
        response_text = response.choices[0].message.content
        
        # Clean the response to ensure it's valid JSON
        response_text = response_text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Validate that the response is valid JSON
        try:
            json.loads(response_text)
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON response from LLM: {str(e)}")
            raise ValueError("LLM response is not valid JSON")
        
        return response_text
        
    except Exception as e:
        logging.error(f"Error getting LLM response: {str(e)}")
        raise

def get_recommendations(prompt: str) -> str:
    """
    Get product recommendations from OpenAI's GPT model.
    
    Args:
        prompt: The prompt containing customer profile and product information
    
    Returns:
        JSON string containing product recommendations
    """
    try:
        # Generate response using OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-4",  # or "gpt-3.5-turbo" based on your needs
            messages=[
                {"role": "system", "content": "You are a product recommendation expert that provides responses in valid JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent JSON responses
            max_tokens=1000
        )
        
        # Extract the text from the response
        response_text = response.choices[0].message.content
        
        # Clean the response to ensure it's valid JSON
        response_text = response_text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Validate that the response is valid JSON
        try:
            json.loads(response_text)
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON response from LLM: {str(e)}")
            raise ValueError("LLM response is not valid JSON")
        
        return response_text
        
    except Exception as e:
        logging.error(f"Error getting recommendations: {str(e)}")
        raise 