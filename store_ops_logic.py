import pandas as pd
import requests
import io
import logging
from datetime import datetime
from config import normalize_employee_id

def fetch_store_ops_from_url(url: str) -> pd.DataFrame:
    """
    Fetches the Google Sheet data as CSV.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        # The sheet analysis showed the header is at a specific row (likely row 2 or 3)
        # We read the raw CSV first to find the date headers
        df_raw = pd.read_csv(io.StringIO(response.text), header=None)
        
        # Heuristic to find the header row: Look for "EMP #" or "NAME"
        header_row_idx = 0
        for i, row in df_raw.iterrows():
            row_str = " ".join(row.astype(str).str.lower().fillna(""))
            if "emp #" in row_str or "name" in row_str:
                header_row_idx = i
                break
        
        # Re-read with correct header
        df = pd.read_csv(io.StringIO(response.text), header=header_row_idx)
        
        # Basic cleaning
        df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
        df = df.dropna(subset=[df.columns[0]]) # Drop rows where EMP # is missing
        
        return df
    except Exception as e:
        logging.error(f"Error fetching store ops from URL: {e}")
        return pd.DataFrame()

def compare_criteria_with_actual(criteria_df: pd.DataFrame, detailed_df: pd.DataFrame) -> dict:
    """
    Compares the store operations criteria with actual fingerprint data.
    
    Returns a dict with:
      - 'discrepancies': DataFrame for the UI report.
      - 'overrides': Dict mapping { emp_id : { date : status } } for reconciliation.
    """
    if criteria_df.empty or detailed_df.empty:
        return {'discrepancies': pd.DataFrame(), 'overrides': {}}

    # 1. Normalize criteria_df to long format: (Employee ID, Date, Expected Status)
    id_col = None
    for col in criteria_df.columns:
        if "emp #" in col.lower() or "no." in col.lower():
            id_col = col
            break
    
    if not id_col:
        return {'discrepancies': pd.DataFrame(), 'overrides': {}}

    name_col = criteria_df.columns[1] if len(criteria_df.columns) > 1 else None
    
    # Identify date columns
    date_cols = []
    for col in criteria_df.columns:
        if any(month in col for month in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]):
            date_cols.append(col)

    # 2. Pivot criteria to long format
    long_criteria = criteria_df.melt(
        id_vars=[id_col, name_col] if name_col else [id_col],
        value_vars=date_cols,
        var_name="Date_Str",
        value_name="Expected_Status"
    )
    
    long_criteria["No."] = long_criteria[id_col].apply(normalize_employee_id)
    
    def parse_criteria_date(d_str):
        try:
            return pd.to_datetime(d_str, dayfirst=True).date()
        except:
            return None

    long_criteria["Date"] = long_criteria["Date_Str"].apply(parse_criteria_date)
    long_criteria = long_criteria.dropna(subset=["Date", "Expected_Status"])
    
    # 3. Build Override Map for Reconciliation
    # format: { emp_id: { date_obj: status_code } }
    overrides = {}
    for _, row in long_criteria.iterrows():
        eid = row["No."]
        dt = row["Date"]
        status = str(row["Expected_Status"]).strip().upper()
        if eid not in overrides:
            overrides[eid] = {}
        overrides[eid][dt] = status

    # 4. Merge with detailed_df (Actual presence)
    df_actual = detailed_df.copy()
    df_actual["No."] = df_actual["No."].apply(normalize_employee_id)
    df_actual["Date"] = pd.to_datetime(df_actual["Date"]).dt.date
    
    if 'Total Shift Duration_td' in df_actual.columns:
        df_actual["Is_Present_Actual"] = df_actual["Total Shift Duration_td"] > pd.Timedelta(0)
    else:
        df_actual["Is_Present_Actual"] = pd.to_timedelta(df_actual["Total Shift Duration"]).fillna(pd.Timedelta(0)) > pd.Timedelta(0)

    comparison = pd.merge(
        long_criteria,
        df_actual[["No.", "Date", "Is_Present_Actual", "Total Shift Duration", "Punch Status"]],
        on=["No.", "Date"],
        how="left"
    )
    comparison["Is_Present_Actual"] = comparison["Is_Present_Actual"].fillna(False)
    
    # 5. Identify Discrepancies
    # Mapping codes: PT, OFF, OH, VC, SL, AB, DP (Public Holiday), XO (Extra Off), HD/FD (Pending)
    
    def find_discrepancy(row):
        status = str(row["Expected_Status"]).strip().upper()
        present = row["Is_Present_Actual"]
        
        # User defined: take only [off, pending off, half day, public holiday, extra off] from GS
        # But we still flag PT for discrepancy report.
        if status == "PT" and not present:
            return "Missing Punch (Expected Present)"
        if status in ["OFF", "OH"] and present:
            return f"Unexpected Punch (Expected {status})"
        if status == "DP" and present:
            return f"Worked on Public Holiday (Extra Off Potential)"
        if status == "XO" and present:
            return f"Worked on Extra Off day"
        if status in ["HD", "FD"]:
            # If they had attendance on a pending day, it's a discrepancy or usage
            if present:
                return f"Punched on Pending day ({status})"
            
        return None

    comparison["Discrepancy"] = comparison.apply(find_discrepancy, axis=1)
    dis_df = comparison[comparison["Discrepancy"].notna()].copy()
    
    return {
        'discrepancies': dis_df[[id_col, "Date", "Expected_Status", "Total Shift Duration", "Discrepancy"]],
        'overrides': overrides
    }
