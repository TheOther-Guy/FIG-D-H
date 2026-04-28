import pandas as pd
from data_processing import FingerprintProcessor

class MockFile:
    def __init__(self, path):
        self.name = path
        with open(path, "rb") as f:
            self.content = f.read()
    def getvalue(self):
        return self.content

f = MockFile("301.xls")

processor = FingerprintProcessor(selected_company_name="Second Cup")
raw_df = processor.process_uploaded_files([f])

detailed_df = processor.calculate_daily_reports(raw_df)

emp_data = detailed_df[detailed_df["No."].astype(str) == "2647"]
print("Detailed DF for 2647 rows:", len(emp_data))
print("Unique dates for 2647:", len(emp_data["Date"].unique()))

start_date, end_date = processor.get_global_dates()
print(f"Global dates: {start_date} to {end_date}")

dates_list = emp_data["Date"].dt.date.tolist()
print("Dates in detailed_df:")
for d in sorted(set(dates_list)):
    count = dates_list.count(d)
    if count > 1:
        print(f"Duplicate date! {d} appears {count} times")
        
from report_generation import generate_summary_report
# Let's generate the actual summary to see how it looks
summary_df, detailed_out = generate_summary_report(detailed_df, start_date, end_date, "Second Cup")
s_emp = summary_df[summary_df["No."].astype(str) == "2647"]
print("\n--- Summary DF for 2647 ---")
print("Total_Present_Days:", s_emp["Total_Present_Days"].iloc[0] if not s_emp.empty else "N/A")
print("Total_Absent_Days:", s_emp["Total_Absent_Days"].iloc[0] if not s_emp.empty else "N/A")
print("Absent_Dates length:", len(s_emp["Absent_Dates"].iloc[0]) if not s_emp.empty else "N/A")
print("Absent_Dates:", s_emp["Absent_Dates"].iloc[0] if not s_emp.empty else "N/A")

