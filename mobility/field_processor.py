class FieldProcessor:
    def __init__(self, data):
        self.data = data

    def extract_relevant_fields(self):
        """
        Extract only the most relevant fields for mobility insights.
        """
        required_fields = [
            'Smartphone Headroom', 'Tablet Headroom', 'Out of Contract Lines',
            'CXI Score', 'Churn Risk Indicators', 'Intent to Buy Mobility',
            '5G BI Eligibility', 'Promotions Eligibility', 
            'Contract Renewal Timeline', 'Device Aging', 'Usage Trends', 
            'Digital Engagement', 'Revenue Per Customer', 'Regional Trends'
        ]
        
        missing_fields = [field for field in required_fields if field not in self.data.columns]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return self.data[required_fields]
