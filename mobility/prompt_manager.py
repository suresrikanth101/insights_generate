class PromptManager:
    def __init__(self):
        pass

    def generate_prompt(self, company_fields):
        """
        Generates a custom prompt for the LLM based on the company's data.
        """
        prompt = f"""
        Analyze the following data for a company and generate:
        1. Elaborated insights for improving mobility growth.
        2. Specific and actionable steps the company can take.

        Company Data:
        Smartphone Headroom: {company_fields.get('Smartphone Headroom')}
        Tablet Headroom: {company_fields.get('Tablet Headroom')}
        Out of Contract Lines: {company_fields.get('Out of Contract Lines')}
        CXI Score: {company_fields.get('CXI Score')}
        Churn Risk Indicators: {company_fields.get('Churn Risk Indicators')}
        Intent to Buy Mobility: {company_fields.get('Intent to Buy Mobility')}
        5G BI Eligibility: {company_fields.get('5G BI Eligibility')}
        Promotions Eligibility: {company_fields.get('Promotions Eligibility')}
        Contract Renewal Timeline: {company_fields.get('Contract Renewal Timeline')}
        Device Aging: {company_fields.get('Device Aging')}
        Usage Trends: {company_fields.get('Usage Trends')}
        Digital Engagement: {company_fields.get('Digital Engagement')}
        Revenue Per Customer: {company_fields.get('Revenue Per Customer')}
        Regional Trends: {company_fields.get('Regional Trends')}
        """
        return prompt.strip()
