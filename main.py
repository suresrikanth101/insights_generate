import pandas as pd
from mobility.data_loader import DataLoader
from mobility.field_processor import FieldProcessor
from mobility.llm_generator import LLMGenerator
from mobility.report_generator import ReportGenerator

def main():
    input_path = "data/company_data.xlsx"
    output_path = "data/output.xlsx"

    # Step 1: Load data
    loader = DataLoader(input_path)
    data = loader.load_data()

    # Step 2: Extract relevant fields
    processor = FieldProcessor(data)
    filtered_data = processor.extract_relevant_fields()

    # Step 3: Generate actions and insights for each company
    llm = LLMGenerator()
    results = []
    for _, row in filtered_data.iterrows():
        company_fields = row.to_dict()
        actions, insights = llm.generate_response(company_fields)
        company_fields["Actions"] = actions
        company_fields["Insights"] = insights
        results.append(company_fields)

    # Step 4: Save results to output file
    results_df = pd.DataFrame(results)
    reporter = ReportGenerator(output_path)
    reporter.save_report(results_df)

if __name__ == "__main__":
    main()
