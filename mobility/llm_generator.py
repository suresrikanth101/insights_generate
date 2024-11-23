from mobility.prompt_manager import PromptManager

class LLMGenerator:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.prompt_manager = PromptManager()  # Use PromptManager to create prompts

    def generate_response(self, company_fields):
        """
        Generate insights and actions using an LLM.
        """
        # Generate prompt using the PromptManager
        prompt = self.prompt_manager.generate_prompt(company_fields)

        # Mocking API call
        response = self.call_llm_api(prompt)
        return self.parse_response(response)

    def call_llm_api(self, prompt):
        """
        Call the LLM API (replace with actual implementation).
        """
        return f"Generated response for prompt: {prompt}"

    def parse_response(self, response):
        """
        Parse the LLM response into actions and insights.
        """
        actions = "Sell smartphones, upgrade devices, leverage 5G eligibility."
        insights = "Focus on CXI improvements and contract renewals."
        return actions, insights
