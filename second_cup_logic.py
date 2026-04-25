import pandas as pd
from datetime import timedelta, time
import streamlit as st
from config import format_timedelta_to_hms

def fix_uniform_status(emp_df: pd.DataFrame) -> pd.DataFrame:
    """
    If an employee's punches are heavily skewed (e.g., almost all 'C/In' or 'C/Out'),
    alternate them chronologically: first In, next Out, etc.
    This handles machines that erroneously record the same status for every punch.
    """
    emp_df = emp_df.sort_values("Original_DateTime").reset_index(drop=True)
    if emp_df.empty:
        return emp_df

    statuses = emp_df["Status"].fillna("").astype(str).str.strip().str.upper().tolist()
    
    # Check for skewness (>80% same status or very low diversity)
    from collections import Counter
    counts = Counter(s for s in statuses if s in ["C/IN", "C/OUT"])
    total_valid = sum(counts.values())
    
    should_fix = False
    if total_valid > 1:
        for s, count in counts.items():
            if count / total_valid > 0.8:
                should_fix = True
                break
    elif len(set(statuses)) == 1 and total_valid > 0:
        should_fix = True

    if should_fix:
        # User requirement: First punch should be In, next Out...
        fixed_statuses = ["C/In" if i % 2 == 0 else "C/Out" for i in range(len(statuses))]
        emp_df["Status"] = fixed_statuses
        emp_df["Status_Autofixed"] = True
    else:
        emp_df["Status_Autofixed"] = False
    return emp_df


def calculate_24_hour_shifts(emp_group_full_sorted: pd.DataFrame, emp_no: str, selected_company_name: str) -> list:
    """
    Enhanced 24-hour shift calculation for Second Cup:
    - Automatically repairs skewed status markers (e.g., all C/In).
    - Pairs In-Out chronologically across dates.
    - Removes orphan C/Out ONLY if it is the absolute FIRST record for the employee.
    - Single punches are reported with 0 duration and marked "Single Punch (Present)".
    """
    daily_report_list_for_employee = []
    
    # 1. Apply robust status repair
    records_df = fix_uniform_status(emp_group_full_sorted)
    records = records_df.to_dict("records")

    # Configuration constants
    IGNORE_WINDOW_START = time(1, 0, 0)
    IGNORE_WINDOW_END = time(7, 0, 0)
    MAX_SHIFT_DURATION = timedelta(hours=20)

    i = 0
    total_punches = len(records)
    
    while i < total_punches:
        rec = records[i]
        status = str(rec.get("Status", "")).strip().lower()
        rec_time = rec["Original_DateTime"].time()

        # --- SPECIAL CASE: The very first record is an orphan orphan C/Out (01–07 AM) ---
        # Rule: Carry-over from previous day shift. We skip it as it's unpairable.
        if i == 0 and status == "c/out" and IGNORE_WINDOW_START <= rec_time <= IGNORE_WINDOW_END:
            i += 1
            continue

        if status == "c/in":
            found_out = False
            # Look for the next C/Out
            for j in range(i + 1, total_punches):
                nxt = records[j]
                nxt_status = str(nxt.get("Status", "")).strip().lower()
                
                if nxt_status == "c/in":
                    # Another In before an Out? Current In is a single punch for pairing purposes.
                    break
                
                if nxt_status == "c/out":
                    dur = nxt["Original_DateTime"] - rec["Original_DateTime"]
                    if dur <= MAX_SHIFT_DURATION:
                        found_out = True
                        end_record = nxt
                        
                        daily_report_list_for_employee.append({
                            "No.": emp_no,
                            "Name": rec["Name"],
                            "Date": rec["Original_DateTime"].date(),
                            "Source_Name": rec["Source_Name"],
                            "Original Number of Punches": 2,
                            "Number of Cleaned Punches": 2,
                            "First Punch Time": rec["Original_DateTime"].strftime("%I:%M:%S %p"),
                            "Last Punch Time": end_record["Original_DateTime"].strftime("%I:%M:%S %p"),
                            "Total Shift Duration": format_timedelta_to_hms(dur),
                            "Punch Status": "Paired C/In–C/Out Shift (24hr Logic)",
                            "Status_Autofixed": rec.get("Status_Autofixed", False),
                            "Daily_More_T_Hours": '00:00:00',
                            "Daily_Short_T_Hours": '00:00:00',
                            "is_more_t_day": False,
                            "is_short_t_day": False,
                            "More_T_postMID": '00:00:00',
                            "Total Break Duration": '00:00:00'
                        })
                        i = j # Consume both
                        break
                    else:
                        break
            
            if not found_out:
                # Single C/In punch
                daily_report_list_for_employee.append({
                    "No.": emp_no,
                    "Name": rec["Name"],
                    "Date": rec["Original_DateTime"].date(),
                    "Source_Name": rec["Source_Name"],
                    "Original Number of Punches": 1,
                    "Number of Cleaned Punches": 1,
                    "First Punch Time": rec["Original_DateTime"].strftime("%I:%M:%S %p"),
                    "Last Punch Time": rec["Original_DateTime"].strftime("%I:%M:%S %p"),
                    "Total Shift Duration": "00:00:00",
                    "Punch Status": "Single Punch (Present, 24hr Logic)",
                    "Status_Autofixed": rec.get("Status_Autofixed", False),
                    "Daily_More_T_Hours": '00:00:00',
                    "Daily_Short_T_Hours": '00:00:00',
                    "is_more_t_day": False,
                    "is_short_t_day": False,
                    "More_T_postMID": '00:00:00',
                    "Total Break Duration": '00:00:00'
                })
        
        elif status == "c/out":
            # Orphan C/Out
            daily_report_list_for_employee.append({
                "No.": emp_no,
                "Name": rec["Name"],
                "Date": rec["Original_DateTime"].date(),
                "Source_Name": rec["Source_Name"],
                "Original Number of Punches": 1,
                "Number of Cleaned Punches": 1,
                "First Punch Time": rec["Original_DateTime"].strftime("%I:%M:%S %p"),
                "Last Punch Time": rec["Original_DateTime"].strftime("%I:%M:%S %p"),
                "Total Shift Duration": "00:00:00",
                "Punch Status": "Single C/Out Punch (Present, 24hr Logic)",
                "Status_Autofixed": rec.get("Status_Autofixed", False),
                "Daily_More_T_Hours": '00:00:00',
                "Daily_Short_T_Hours": '00:00:00',
                "is_more_t_day": False,
                "is_short_t_day": False,
                "More_T_postMID": '00:00:00',
                "Total Break Duration": '00:00:00'
            })

        i += 1

    return daily_report_list_for_employee
