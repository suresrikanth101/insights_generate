import streamlit as st
from utils.llm_utils import get_llm_response
import json
import re

# Load the base prompt from file
def load_base_prompt():
    with open("prompts/base_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

def clean_response(text: str) -> dict:
    # Remove code block markers and language labels
    text = re.sub(r"^```[a-zA-Z]*\\n?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    # Find the first and last curly braces
    start_index = text.find("{")
    end_index = text.rfind("}")
    if start_index == -1 or end_index == -1:
        return None
    json_str = text[start_index:end_index+1]
    try:
        return json.loads(json_str)
    except Exception as e:
        print(f"JSON decode error: {e}")
        return None

# Set page config to use full width
st.set_page_config(layout="wide")

st.title("Rep Nudges LLM Generator")

page_details = st.text_area("Enter page details (paste from your source):", height=300)

if st.button("Generate Rep Nudges"):
    if not page_details.strip():
        st.warning("Please enter the page details.")
    else:
        base_prompt = load_base_prompt()
        full_prompt = base_prompt + page_details.strip() + "\n\nResponse:"
        response = get_llm_response(full_prompt)
        cleaned_json_response = clean_response(response)
        
        if cleaned_json_response and isinstance(cleaned_json_response, dict):
            st.subheader("Top 3 Priorities:")
            st.json(cleaned_json_response)
        else:
            st.subheader("LLM Response:")
            st.error("Failed to generate recommendations in the expected format. Please try again.")
            st.text_area("Raw Response:", response, height=200, disabled=True)

st.markdown("---")
st.markdown("**Instructions:** Paste the rep's page details above and click 'Generate Rep Nudges'.") 