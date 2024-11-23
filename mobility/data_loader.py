import pandas as pd

class DataLoader:
    def __init__(self, file_path):
        self.file_path = file_path

    def load_data(self):
        """
        Load data from the Excel file.
        """
        try:
            data = pd.read_excel(self.file_path)
            return data
        except Exception as e:
            raise ValueError(f"Error loading data: {e}")
