import pandas as pd
import io
import requests
import re
from datetime import datetime

url = "https://docs.google.com/spreadsheets/d/153tgWpTT65qOVL_KJpGOMP7xNYmG-Sc5JNNIhcsz490/export?format=csv&gid=2085306002"
response = requests.get(url)
df_raw = pd.read_csv(io.StringIO(response.text), header=None)

year_str = ""
for cell in df_raw.iloc[0].astype(str).fillna(""):
    if "202" in cell:
        match = re.search(r'(202\d)', cell)
        if match:
            year_str = match.group(1)
            break
if not year_str:
    year_str = str(datetime.now().year)

print(f"Extracted year: {year_str}")

# Find EMP # row dynamically
emp_row_idx = 0
for i, row in df_raw.iterrows():
    row_str = " ".join(row.astype(str).str.lower().fillna(""))
    if "emp #" in row_str or "name" in row_str:
        emp_row_idx = i
        break

# Find Date row (search above emp_row_idx)
date_row_idx = 0
for i in range(emp_row_idx + 1):
    row = df_raw.iloc[i]
    row_str = " ".join(row.astype(str).fillna(""))
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    date_count = sum(1 for cell in row.astype(str).fillna("") if any(m in str(cell) for m in months))
    if date_count > 5:
        date_row_idx = i
        break

new_headers = []
for col_idx in range(len(df_raw.columns)):
    emp_val = str(df_raw.iloc[emp_row_idx, col_idx]).strip()
    date_val = str(df_raw.iloc[date_row_idx, col_idx]).strip()
    
    if "EMP" in emp_val.upper() or "NO." in emp_val.upper():
        new_headers.append("EMP #")
    elif "NAME" in emp_val.upper():
        new_headers.append("NAME")
    elif any(m in date_val for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]):
        clean_date = re.sub(r'-[a-zA-Z]{3}-', '-', date_val)
        if year_str not in clean_date:
            clean_date = f"{clean_date}-{year_str}"
        new_headers.append(clean_date)
    else:
        new_headers.append(emp_val if emp_val and emp_val.lower() != 'nan' else f"Unnamed_{col_idx}")

print("Headers:", new_headers[:10])

# Parse a date
for header in new_headers:
    if any(m in header for m in ["Jan", "Feb", "Mar"]):
        try:
            print(header, "->", pd.to_datetime(header).date())
        except Exception as e:
            print("Failed to parse:", header, e)
        break

