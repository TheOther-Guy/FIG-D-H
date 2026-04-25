import pandas as pd
from store_ops_logic import fetch_store_ops_from_url

url = "https://docs.google.com/spreadsheets/d/153tgWpTT65qOVL_KJpGOMP7xNYmG-Sc5JNNIhcsz490/export?format=csv&gid=2085306002"
df = fetch_store_ops_from_url(url)

print("Parsed Columns:", df.columns[:10].tolist(), "...")
emp_row = df[df["EMP #"].astype(str).str.strip() == "2825"]
if not emp_row.empty:
    print("\nData for 2825:")
    print(emp_row.iloc[:, 8:15])
else:
    print("Employee 2825 not found!")
