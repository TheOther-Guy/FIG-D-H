import pandas as pd
import io
import requests

url = "https://docs.google.com/spreadsheets/d/153tgWpTT65qOVL_KJpGOMP7xNYmG-Sc5JNNIhcsz490/export?format=csv&gid=2085306002"
response = requests.get(url)
df_raw = pd.read_csv(io.StringIO(response.text), header=None)

# Find EMP # row
emp_row_idx = 0
for i, row in df_raw.iterrows():
    row_str = " ".join(row.astype(str).str.lower().fillna(""))
    if "emp #" in row_str or "name" in row_str:
        emp_row_idx = i
        break

# Find Date row
date_row_idx = 0
for i in range(emp_row_idx + 1): # Search up to emp_row_idx
    row_str = " ".join(row.astype(str).fillna(""))
    if any(month in row_str for month in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]):
        # Make sure it has multiple dates, not just one "Dec" somewhere
        date_count = sum(1 for cell in row.astype(str).fillna("") if any(m in str(cell) for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]))
        if date_count > 5: # likely the date row
            date_row_idx = i
            break

print(f"emp_row_idx: {emp_row_idx}, date_row_idx: {date_row_idx}")

new_headers = []
for col_idx in range(len(df_raw.columns)):
    emp_val = str(df_raw.iloc[emp_row_idx, col_idx]).strip()
    date_val = str(df_raw.iloc[date_row_idx, col_idx]).strip()
    
    if "EMP" in emp_val.upper() or "NO." in emp_val.upper():
        new_headers.append("EMP #")
    elif "NAME" in emp_val.upper():
        new_headers.append("NAME")
    elif any(m in date_val for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]):
        new_headers.append(date_val)
    else:
        new_headers.append(emp_val if emp_val and emp_val != 'nan' else f"Unnamed_{col_idx}")

df = df_raw.iloc[emp_row_idx+1:].copy()
df.columns = new_headers
# Filter out empty emp rows
df = df[df["EMP #"].astype(str).str.strip() != "nan"]
df = df[df["EMP #"].astype(str).str.strip() != ""]

print(df.head())
print("Columns:", list(df.columns))
