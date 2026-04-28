import pandas as pd
from data_processing import FingerprintProcessor
from report_generation import ReportGenerator

processor = FingerprintProcessor("Second Cup")

class MockFile:
    def __init__(self, path):
        self.name = path
        with open(path, "rb") as f:
            self.content = f.read()
    def getvalue(self):
        return self.content

raw_df = processor.process_uploaded_files([MockFile("301.xls")])
detailed_df = processor.calculate_daily_reports(raw_df)

rg = ReportGenerator("Second Cup")
start_dt = detailed_df["Date"].min()
end_dt = detailed_df["Date"].max()

eff_dates = {}
for emp in detailed_df["No."].unique():
    eff_dates[emp] = (start_dt, end_dt)

summary_df, _, _, _ = rg.generate_summary_report(detailed_df, start_dt, end_dt, eff_dates)

emp = summary_df[summary_df["No."].astype(str) == "2647"]
print("Summary columns:", emp[["Total_Present_Days", "Total_Absent_Days", "Total Days in Overall Period"]].to_dict('records'))
