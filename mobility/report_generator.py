import pandas as pd

class ReportGenerator:
    def __init__(self, output_path):
        self.output_path = output_path

    def save_report(self, data):
        """
        Save the processed data with actions and insights to an Excel file.
        """
        try:
            data.to_excel(self.output_path, index=False)
            print(f"Report saved successfully at {self.output_path}")
        except Exception as e:
            raise ValueError(f"Error saving report: {e}")
