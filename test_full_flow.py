import pandas as pd
from store_ops_logic import fetch_store_ops_from_url, compare_criteria_with_actual
from report_generation import reconcile_hybrid_absences

url = "https://docs.google.com/spreadsheets/d/153tgWpTT65qOVL_KJpGOMP7xNYmG-Sc5JNNIhcsz490/export?format=csv&gid=2085306002"
raw_result = fetch_store_ops_from_url(url)

# create a mock detailed df for 2825
detailed_report_df = pd.DataFrame({
    "No.": ["2825", "2825", "2825", "2825"],
    "Date": ["2026-03-25", "2026-03-31", "2026-04-01", "2026-04-02"],
    "Total Shift Duration": ["08:00", "00:00", "00:00", "00:00"],
    "Punch Status": ["OK", "Miss", "Miss", "Miss"]
})
detailed_report_df["Total Shift Duration_td"] = pd.to_timedelta(detailed_report_df["Total Shift Duration"] + ":00")

res = compare_criteria_with_actual(raw_result, detailed_report_df)
overrides_map = res['overrides']

final_summary = pd.DataFrame({
    "No.": ["2825"],
    "Final_Absent_Dates": [["2026-03-31", "2026-04-01", "2026-04-02"]]
})

final_summary = reconcile_hybrid_absences(
    final_summary, 
    overrides_map, 
    detailed_report_df,
    pd.to_datetime("2026-03-25").date(),
    pd.to_datetime("2026-04-24").date()
)

print(final_summary)
