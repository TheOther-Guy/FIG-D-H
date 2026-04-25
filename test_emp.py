import pandas as pd

# Read Report
report_path = "Employee_Punch_Reports_D&H (1).xlsx"
print("=== GENERATED REPORT SUMMARY FOR 2825 ===")
try:
    df_summary = pd.read_excel(report_path, sheet_name="Summary")
    emp_summary = df_summary[df_summary['No.'].astype(str).str.strip() == '2825']
    print(emp_summary.to_dict('records'))
except Exception as e:
    print("Error reading summary:", e)

# Read Google Sheets
print("\n=== GOOGLE SHEETS DATA FOR 2825 ===")
url = "https://docs.google.com/spreadsheets/d/153tgWpTT65qOVL_KJpGOMP7xNYmG-Sc5JNNIhcsz490/export?format=csv&gid=2085306002"
try:
    df_gs = pd.read_csv(url)
    # The EMP # is in the first column, usually. Let's find the row.
    emp_col = df_gs.columns[0]
    emp_row = df_gs[df_gs[emp_col].astype(str).str.strip() == '2825']
    print("Columns:", list(df_gs.columns))
    if not emp_row.empty:
        print("Data:")
        for col in df_gs.columns:
            val = emp_row[col].values[0]
            if pd.notna(val):
                print(f"{col}: {val}")
    else:
        print("Emp 2825 not found in first column")
except Exception as e:
    print("Error reading Google Sheets:", e)
