import openai
from nbx_recom.config import OPENAI_API_KEY
import logging

openai.api_key = OPENAI_API_KEY

def get_recommendations(prompt):
    logging.info("Calling GenAI API for recommendations.")
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.3
        )
        logging.info("GenAI API call successful.")
        return response['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"GenAI API call failed: {e}")
        raise 