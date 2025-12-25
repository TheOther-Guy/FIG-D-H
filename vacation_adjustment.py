import pandas as pd
import re
from typing import Optional, List, Dict
from config import COMPANY_CONFIGS  # weekend rules per company

# --------------------------- Helpers ---------------------------

def _norm(s: str) -> str:
    return re.sub(r'[\s_.]+', '', str(s).strip().lower())

def _canonicalize_type(s: str) -> str:
    """
    Canonical buckets:
      - 'vacation' and 'sick'   => excused absences
      - 'emergency' and 'unpaid'=> excused absences  (HR file labels no-punch reasons)
      - 'back_from_vacation'    => informational; ignore
      - 'stop_working'          => informational; ignore
    """
    s = str(s).strip().lower()
    if s in {'vac', 'vacation', 'annual', 'annual leave', 'annualleave', 'leave annual', 'paid leave'}:
        return 'vacation'
    if s in {'sick', 'sick leave', 'sickleave', 'sickness', 'sick leaves'}:
        return 'sick'
    if s in {
        'emergency', 'emergency leave', 'emergencyleave',
        'emergency leave & absence', 'emergency leave & absent',
        'emergency leave & absences', 'emergencyleave&absence'
    }:
        return 'emergency'
    if s in {'unpaid', 'no pay', 'nopay', 'leave without pay', 'lwp', 'unpaid leave', 'unpaidleave'}:
        return 'unpaid'
    # informational (no adjustment)
    if s in {
        'vacation return', 'return from vacation', 'back from vacation',
        'backfromvacation', 'returnfromvacation'
    }:
        return 'back_from_vacation'
    if s in {'stop working', 'stopworking'}:
        return 'stop_working'
    if s in {'new hirring', 'newhirring', 'new hiring', 'newhiring'}:
        return 'new_hire'
    return s

def _company_default_weekend_days(selected_company_name: str) -> List[int]:
    # Monday=0 .. Sunday=6
    return [int(x) for x in COMPANY_CONFIGS.get(selected_company_name, {}).get('default_rules', {}).get('weekend_days', [4])]

def _location_weekend_days(selected_company_name: str, source_name: str) -> Optional[List[int]]:
    comp = COMPANY_CONFIGS.get(selected_company_name, {})
    loc_rules = comp.get('location_rules', {})
    rules = loc_rules.get(source_name)
    if not rules:
        return None
    wd = rules.get('weekend_days')
    if wd is None:
        return None
    return [int(x) for x in wd]

def _clip_dates_to_period(start_dt: pd.Timestamp, end_dt: pd.Timestamp,
                          period_start: pd.Timestamp, period_end: pd.Timestamp) -> Optional[pd.DatetimeIndex]:
    """Clip [start_dt, end_dt] to [period_start, period_end]; None if no overlap."""
    if pd.isna(start_dt) and pd.isna(end_dt):
        return None
    if pd.isna(start_dt):
        start_dt = end_dt
    if pd.isna(end_dt):
        end_dt = start_dt
    start_dt = pd.to_datetime(start_dt).normalize()
    end_dt   = pd.to_datetime(end_dt).normalize()
    if end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt
    s = max(start_dt, pd.to_datetime(period_start).normalize())
    e = min(end_dt,   pd.to_datetime(period_end).normalize())
    if e < s:
        return None
    return pd.date_range(s, e, freq='D')

def _count_working_days(daterange: Optional[pd.DatetimeIndex], weekend_days: List[int]) -> int:
    if daterange is None or len(daterange) == 0:
        return 0
    return int((~daterange.weekday.isin(weekend_days)).sum())

def _unique_union_index(ranges: List[pd.DatetimeIndex]) -> pd.DatetimeIndex:
    """Robust union for a list of DTI (works across pandas versions)."""
    if not ranges:
        return pd.DatetimeIndex([])
    # flatten and unique
    all_vals = []
    for r in ranges:
        if r is not None and len(r):
            all_vals.extend(list(r))
    if not all_vals:
        return pd.DatetimeIndex([])
    return pd.DatetimeIndex(sorted(pd.unique(pd.to_datetime(all_vals))))

def _enumerate_absent_dates(
    emp_df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    vacation_ranges,
    weekend_days
) -> List[str]:
    """
    Return list of yyyy-mm-dd absent days with:
      - no punches (including: NOT single-punch),
      - not covered by vacation,
      - not weekend.

    A day is considered PRESENT if:
      - Total Shift Duration > 0 OR
      - It is a single-punch day.

    Enhancements:
      - Ensures proper date normalization
      - Ensures correct vacation union index
      - Handles empty weekend_days by leaving logic to caller (fallback applied upstream)
      - Output sorted consistently
    """

    # -------------------------------------------------------
    # 1. Build full day range
    # -------------------------------------------------------
    all_days = pd.date_range(start, end, freq="D")
    all_days_norm = all_days.normalize()

    # -------------------------------------------------------
    # 2. Duration Series
    # -------------------------------------------------------
    if 'Total Shift Duration_td' in emp_df.columns:
        dur_td = pd.to_timedelta(emp_df['Total Shift Duration_td'], errors='coerce')\
                    .fillna(pd.Timedelta(0))
    elif 'Total Shift Duration' in emp_df.columns:
        dur_td = pd.to_timedelta(emp_df['Total Shift Duration'], errors='coerce')\
                    .fillna(pd.Timedelta(0))
    else:
        dur_td = pd.to_timedelta(0)

    # -------------------------------------------------------
    # 3. Detect single-punch rows
    # -------------------------------------------------------
    punch_status = emp_df.get('Punch Status', '').astype(str).str.strip().str.lower()

    is_single = (
        punch_status.eq("single punch (0 shift duration)")
    ) | (
        (pd.to_numeric(emp_df.get('Original Number of Punches', 0),
                       errors='coerce').fillna(0).astype(int).eq(1))
        & (dur_td == pd.Timedelta(0))
    )

    # -------------------------------------------------------
    # 4. Determine presence
    # -------------------------------------------------------
    is_present_row = (dur_td > pd.Timedelta(0)) | is_single

    present_dates = (
        pd.to_datetime(emp_df.loc[is_present_row, 'Date'], errors='coerce')
        .dt.normalize()
        .dropna()
        .unique()
    )
    present_dates = pd.DatetimeIndex(present_dates)

    # -------------------------------------------------------
    # 5. Vacation union
    # -------------------------------------------------------
    if vacation_ranges:
        vac_days = _unique_union_index(vacation_ranges)
    else:
        vac_days = pd.DatetimeIndex([])

    # -------------------------------------------------------
    # 6. Build ABSENT list
    # -------------------------------------------------------
    weekend_days_set = set(weekend_days) if weekend_days else set()

    absent = []
    for idx, d in enumerate(all_days_norm):

        weekday = d.weekday()

        # Weekend?
        if weekday in weekend_days_set:
            continue

        # Vacation?
        if d in vac_days:
            continue

        # Present?
        if d in present_dates:
            continue

        absent.append(d)

    # -------------------------------------------------------
    # 7. Output formatting
    # -------------------------------------------------------
    return [d.strftime("%Y-%m-%d") for d in sorted(absent)]



# --------------------------- Public API ---------------------------


    """
    Parse HR overrides / adjustments file.
    Supports:
      - CSV files (single sheet)
      - Excel files with multiple sheets (Sick Leaves, Annual Leave, etc.)
    ...
    """

def get_employee_effective_windows(
    overrides_df: pd.DataFrame,
    global_start: pd.Timestamp,
    global_end: pd.Timestamp
) -> Dict[str, tuple]:
    """
    Calculate effective [start, end] window for each employee based on transactions.
    
    Rules:
      - 'new_hire'          -> Sets effective start (earliest wins or user defined?) -> Usually defining start of contract.
      - 'vacation_return'   -> Sets effective start (prior days ignored for absence).
                               If multiple, use earliest or latest?
                               "return from vacation" implies a start of active period.
                               We'll treat it as a "Start Date" marker.
      - 'stop_working'      -> Sets effective end.
      
    Returns:
        dict: { emp_id_str: (effective_start_ts, effective_end_ts) }
        If no override, returns (global_start, global_end).
    """
    if overrides_df is None or overrides_df.empty:
        return {}

    # Normalize columns first if not done (load_vacation_file does it, but defensive check good)
    v = overrides_df.copy()
    # Ensure canonical types
    if "type" in v.columns:
        # We assume load_vacation_file already ran _canonicalize_type
        # But we can re-map just in case simple strings were passed manualy
        pass 
    
    # 1. Maps
    new_hire_map = {}
    vac_return_map = {}
    stop_work_map = {}
    
    # Normalize ID
    if "id" in v.columns:
        v["id"] = v["id"].astype(str).str.strip()
    
    # Parse dates if strictly needed
    if "start_date" in v.columns:
        v["start_date"] = pd.to_datetime(v["start_date"], errors="coerce")
    if "end_date" in v.columns:
        v["end_date"] = pd.to_datetime(v["end_date"], errors="coerce")

    for _, row in v.iterrows():
        emp_id = row.get("id")
        if not emp_id: continue
        
        t = str(row.get("type", "")).lower()
        sdt = row.get("start_date", pd.NaT)
        edt = row.get("end_date", pd.NaT)
        
        # New Hire
        if t == "new_hire" and pd.notna(sdt):
            # If multiple new hire dates? Earliest logical start.
            curr = new_hire_map.get(emp_id, pd.Timestamp.max)
            new_hire_map[emp_id] = min(curr, sdt)
            
        # Vacation Return (treat as Start Date)
        if t == "back_from_vacation" and pd.notna(sdt):
            # User instruction: "prior days to this date doesn't count as absent"
            # This acts like a start date.
            curr = vac_return_map.get(emp_id, pd.Timestamp.max)
            vac_return_map[emp_id] = min(curr, sdt)
            
        # Stop Working
        if t == "stop_working":
            # Date usually provided in date/end_date column
            # If start_date is present, usage that.
            date_val = edt if pd.notna(edt) else sdt
            if pd.notna(date_val):
                curr = stop_work_map.get(emp_id, pd.Timestamp.min)
                stop_work_map[emp_id] = max(curr, date_val)

    # 2. Build Result
    # We iterate over all IDs found in overrides to ensure we capture them
    # But function is usually called with a target list in mind.
    # We will return a dict of *found* overrides. The caller defaults to global if missing.
    
    effective_map = {}
    
    all_ids = set(v["id"].unique())
    
    g_start = pd.to_datetime(global_start).normalize()
    g_end = pd.to_datetime(global_end).normalize()

    for emp_id in all_ids:
        eff_start = g_start
        eff_end = g_end
        
        # Apply Start Logic (New Hire OR Vacation Return)
        # If both exist, which one wins? 
        # Typically "Vacation Return" might be for an existing employee returning.
        # "New Hire" is new. 
        # We can take the LATEST of the starts if both exist? Or Earliest?
        # User: "vacation return ... prior days are not counted".
        # This implies the period STARTS at vacation return.
        
        starts = []
        if emp_id in new_hire_map:
            starts.append(new_hire_map[emp_id])
        if emp_id in vac_return_map:
            starts.append(vac_return_map[emp_id])
            
        if starts:
            # If we have start markers, the effective start is the defined date.
            # If multiple markers (e.g. New Hire Jan 1, Vacation Return Feb 1), 
            # and we are in Feb report, Effective Start likely specific to the transaction context.
            # For simplicity, if multiple "Start" directives exist, we arguably take the *latest* one 
            # effectively "resetting" the start? 
            # Or earliest?
            # "new hiring... prior days ... doesn't count"
            # "vacation return... prior days ... not counted"
            # Safest interpretation: The effective start is the MAX of these dates 
            # (limiting the active window as much as possible to strictly worked period).
            # BUT: If New Hire is Jan 1, and Vacation Return is Jan 15. Days 1-15:
            # If we say Start = Jan 15, then Jan 1-14 are excluded => Not Absent.
            # If they were on vacation Jan 1-15, that fits.
            # So MAX seems correct to shorten the window.
            eff_start = max(starts).normalize()
            
        # Apply End Logic
        if emp_id in stop_work_map:
            # Stop working at date X. Later days not counted.
            # So effective end is X.
            eff_end = stop_work_map[emp_id].normalize()
        
        # Clip to global
        # If eff_start < g_start, we just use g_start (already covered by caller logic usually, but robust here)
        # Actually user might want "start date is X", if X < Global Start, then Effective Start = Global Start.
        # If X > Global Start, Effective Start = X.
        # So we take MAX(eff_start, g_start)
        final_start = max(eff_start, g_start)
        
        # If eff_end > g_end, use g_end.
        # If eff_end < g_end, use eff_end.
        final_end = min(eff_end, g_end)
        
        effective_map[emp_id] = (final_start, final_end)
        
    return effective_map


def load_vacation_file(uploaded_file) -> pd.DataFrame:
    import logging
    
    if uploaded_file is None:
        return pd.DataFrame()

    all_data = []

    try:
        is_excel = uploaded_file.name.lower().endswith(('.xlsx', '.xls'))
        
        if is_excel:
            xls = pd.ExcelFile(uploaded_file)
            sheet_names = xls.sheet_names
        else:
            # For CSV, treat as single "sheet" with default name
            sheet_names = ["CSV_Data"]
    
    except Exception as e:
        raise ValueError(f"Failed to open vacation/override file: {e}")

    for sheet in sheet_names:
        # 1. Skip Pending Off (handled elsewhere)
        if _is_pending_off_sheet(sheet):
            continue

        try:
            # Read raw data to find header
            if is_excel:
                # Read first few rows to detect header
                raw = pd.read_excel(uploaded_file, sheet_name=sheet, header=None, nrows=15)
            else:
                uploaded_file.seek(0)
                raw = pd.read_csv(uploaded_file, header=None, nrows=15)

            # 2. Detect Header Row
            header_row_idx = None
            header_keywords = ["no.", "employee", "id", "name", "doc", "document"]
            
            for i, row in raw.iterrows():
                # Convert row to string, lower, and check for keywords
                row_str = " ".join(row.astype(str).str.lower().fillna(""))
                # Look for at least one strong keyword
                if any(k in row_str for k in header_keywords):
                     header_row_idx = i
                     break
            
            if header_row_idx is None:
                # If cannot find header, maybe it's row 0 or empty sheet
                # If sheet seems empty, skip
                if raw.empty:
                    continue
                header_row_idx = 0

            # 3. Read full data with detected header
            if is_excel:
                df = pd.read_excel(uploaded_file, sheet_name=sheet, header=header_row_idx)
            else:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, header=header_row_idx)

            if df.empty:
                continue

            # 4. Normalize Columns
            cols = list(df.columns)
            norm_map = {_norm(c): c for c in cols}
            
            # Helper to find column content
            def get_col(candidates):
                for c in candidates:
                    n = _norm(c)
                    if n in norm_map:
                        return norm_map[n]
                return None

            id_col = get_col(['no.', 'no', 'id', 'employee', 'employeeid', 'code', 'emp id'])
            name_col = get_col(['name', 'employee name', 'staff'])
            
            # Determine canonical type early to select mapping
            raw_type = sheet # Default to sheet name
            type_col = get_col(['type', 'leave type', 'reason', 'absence type'])
            if type_col:
                # If a type column exists, it might override sheet name, but usually sheet name implies the category
                # For safety, let's stick to sheet-based categorization for column mapping 
                # unless generic.
                pass
            
            canon_type = _canonicalize_type(raw_type)
            
            # --- Type-Specific Column Mapping ---
            # Define candidates for strict lookup based on user rules
            # Keys match the output of _canonicalize_type
            
            # Default candidates
            start_candidates = ['start date', 'from', 'date from', 'start']
            end_candidates = ['end date', 'to', 'date to', 'end']
            
            if canon_type == "sick":
                start_candidates = ['absence from date', 'absence date'] + start_candidates
                end_candidates = ['absence to date', 'absence to'] + end_candidates
            elif canon_type == "emergency":
                start_candidates = ['from', 'start']
                end_candidates = ['till', 'to', 'end']
            elif canon_type == "back_from_vacation":
                start_candidates = ['return date', 'date of return', 'return']
                end_candidates = [] # Single date
            elif canon_type == "vacation": # Annual
                start_candidates = ['from date', 'from']
                end_candidates = ['to date', 'to']
            elif canon_type == "new_hire":
                start_candidates = ['date of hire', 'hire date', 'joining date']
                end_candidates = [] # Single date
            elif canon_type == "stop_working":
                end_candidates = ['last day', 'leaving date'] # treated as "End Date" logic
                start_candidates = [] 
                
            # strict lookup
            start_col = get_col(start_candidates)
            end_col = get_col(end_candidates)
            days_col = get_col(['days', 'number of days', 'count', 'duration', 'total days'])
            
            # For back_from_vacation or new_hire, map single date to start_date
            # For stop_working, map single date to end_date
            
            if not id_col:
                # Skip sheets that don't look like data (e.g. cover sheets)
                continue

            # 5. Extract Data
            # Clean ID
            df[id_col] = df[id_col].astype(str).str.strip()
            # Remove total rows or empty IDs
            df = df[df[id_col].str.lower() != 'nan']
            df = df[~df[id_col].str.lower().str.contains('total', na=False)]

            extracted = pd.DataFrame()
            extracted['id'] = df[id_col]
            extracted['name'] = df[name_col] if name_col else ""
            extracted['type'] = canon_type

            # Determine Days/Range
            if start_col or end_col:
                extracted['start_date'] = pd.to_datetime(df[start_col], errors='coerce') if start_col else pd.NaT
                extracted['end_date'] = pd.to_datetime(df[end_col], errors='coerce') if end_col else pd.NaT
            elif days_col:
                extracted['days'] = pd.to_numeric(df[days_col], errors='coerce').fillna(0)
            else:
                # If neither range nor days, maybe it implies 1 day per row? 
                # Or check if there is a 'Date' column for single days
                date_col = get_col(['date', 'dates'])
                if date_col:
                     extracted['start_date'] = pd.to_datetime(df[date_col], errors='coerce')
                     extracted['end_date'] = extracted['start_date']
                else:
                    # Fallback: Assume manual review needed or 0 days
                    extracted['days'] = 0

            all_data.append(extracted)

        except Exception as e:
            logging.warning(f"Error processing sheet '{sheet}': {e}")
            continue

    if not all_data:
        return pd.DataFrame()

    final_df = pd.concat(all_data, ignore_index=True)
    return final_df


def _is_pending_off_sheet(sheet_name: str) -> bool:
    """Helper to detect Pending Off sheets to skip them in main loader."""
    norm = str(sheet_name).strip().lower().replace(" ", "_")
    return "pending" in norm and "off" in norm



def apply_vacation_adjustments(
    summary_df: pd.DataFrame,
    overrides_df: pd.DataFrame,
    selected_company_name: str,
    global_start_date: pd.Timestamp,
    global_end_date: pd.Timestamp,
    detailed_df: pd.DataFrame,
):
    """
    Apply HR vacation overrides on top of baseline absences.

    Orchestration (VERY IMPORTANT):

    1) Baseline (from ReportGenerator.generate_summary_report):
        - summary_df["Absent_Dates"]   → list of yyyy-mm-dd strings per employee
        - summary_df["Total_Absent_Days"] = len(Absent_Dates)

    2) This function:
        - Reads vacation / HR override file (overrides_df)
        - Interprets:
            * 'new hire' / 'New Hire'           → employee's effective start date
            * 'stop working' / 'Stop Working'   → employee's effective end date
            * 'vacation', 'sick', 'emergency',
              'unpaid', etc.                    → EXCUSED days (within the period)
        - Computes for each employee:
            * Excused_Total            = number of absent dates removed
            * Final_Absent_Dates       = Absent_Dates after removing excused / out-of-window
            * Final_Absent_Days        = len(Final_Absent_Dates)

    3) Later:
        - pending_offs.apply_pending_offs() uses Final_Absent_Dates and Final_Absent_Days
          to compute:
            * Total_Pending_OFFs
            * Total_Absent_After_Pending
            * Final_Absent_Dates_After_Pending

    NOTE:
    - We DO NOT recompute raw absence dates here.
      The only source of baseline absences is summary_df["Absent_Dates"].
    """

    import pandas as pd
    import numpy as np

    from config import get_effective_rules_for_employee_day

    # ------------------------------------------------------------------
    # 0. Defensive: normalize inputs
    # ------------------------------------------------------------------
    s = summary_df.copy()

    # Ensure Absent_Dates exists and is list-like
    if "Absent_Dates" not in s.columns:
        # If missing, we cannot correctly adjust by day → fall back to counts only
        s["Absent_Dates"] = [[] for _ in range(len(s))]
    else:
        s["Absent_Dates"] = s["Absent_Dates"].apply(
            lambda x: x if isinstance(x, list) else []
        )

    # Ensure Total_Absent_Days consistent with Absent_Dates length
    if "Total_Absent_Days" in s.columns:
        s["Total_Absent_Days"] = s["Absent_Dates"].apply(len).astype(int)
    else:
        s["Total_Absent_Days"] = s["Absent_Dates"].apply(len).astype(int)

    # If no overrides / vacation file provided → passthrough with explicit columns
    if overrides_df is None or overrides_df.empty:
        if "Excused_Total" not in s.columns:
            s["Excused_Total"] = 0
        if "Final_Absent_Days" not in s.columns:
            s["Final_Absent_Days"] = s["Total_Absent_Days"]
        if "Final_Absent_Dates" not in s.columns:
            s["Final_Absent_Dates"] = s["Absent_Dates"]
        empty_detail = pd.DataFrame(columns=["id", "type", "Window_Start", "Window_End",
                                             "Excused_Dates", "Excused_Days"])
        return s, empty_detail

    # ------------------------------------------------------------------
    # 1. Normalize overrides_df columns / types
    # ------------------------------------------------------------------
    v = overrides_df.copy()
    # bring to snake_case lower
    v.columns = [c.strip().lower().replace(" ", "_") for c in v.columns]

    # Expected columns from load_vacation_file:
    #   id, name, type, start_date, end_date   (range-based)
    # or:
    #   id, name, type, days                   (numeric-based)
    has_ranges = ("start_date" in v.columns) or ("end_date" in v.columns)
    has_days_col = "days" in v.columns

    # Canonical type bucket is already applied in load_vacation_file via _canonicalize_type,
    # but we still normalize here defensively.
    def _canon_type(t: str) -> str:
        t = str(t).strip().lower()
        # match existing canonicalization in this module
        if t in {"vac", "vacation", "annual", "annual leave", "annualleave",
                 "leave annual", "paid leave"}:
            return "vacation"
        if t in {"sick", "sick leave", "sickleave", "sickness", "sick leaves"}:
            return "sick"
        if t in {
            "emergency", "emergency leave", "emergencyleave",
            "emergency leave & absence", "emergency leave & absent",
            "emergency leave & absences", "emergencyleave&absence"
        }:
            return "emergency"
        if t in {"unpaid", "no pay", "nopay", "leave without pay", "lwp",
                 "unpaid leave", "unpaidleave"}:
            return "unpaid"
        if t in {
            "vacation return", "return from vacation", "back from vacation",
            "backfromvacation", "returnfromvacation"
        }:
            return "back_from_vacation"
        if t in {"stop working", "stopworking", "stop_working"}:
            return "stop_working"
        if t in {"new hire", "new_hire", "newhire", "new hirring", "newhirring"}:
            return "new_hire"
        return t

    if "type" in v.columns:
        v["type"] = v["type"].map(_canon_type)
    else:
        v["type"] = ""

    # ID string key
    if "id" not in v.columns:
        raise ValueError("Vacation overrides file missing required 'id' column after normalization.")

    v["id"] = v["id"].astype(str).str.strip()

    # Range-based dates if present
    if has_ranges:
        v["start_date"] = pd.to_datetime(v.get("start_date"), errors="coerce")
        v["end_date"] = pd.to_datetime(v.get("end_date"), errors="coerce")

    # ------------------------------------------------------------------
    # 2. Build New Hire / Stop Working maps
    # ------------------------------------------------------------------
    new_hire_map = {}      # emp_id -> start_date
    stop_work_map = {}     # emp_id -> end_date

    for _, row in v.iterrows():
        emp_id = row["id"]
        t = row["type"]
        sdt = row.get("start_date", pd.NaT)
        edt = row.get("end_date", pd.NaT)

        if t == "new_hire" and pd.notna(sdt):
            # earliest new hire date wins
            if emp_id not in new_hire_map:
                new_hire_map[emp_id] = sdt
            else:
                new_hire_map[emp_id] = min(new_hire_map[emp_id], sdt)

        if t == "stop_working" and pd.notna(edt):
            # latest stop_working date wins
            if emp_id not in stop_work_map:
                stop_work_map[emp_id] = edt
            else:
                stop_work_map[emp_id] = max(stop_work_map[emp_id], edt)

    # ------------------------------------------------------------------
    # 3. Baseline absent dates per employee (converted to Timestamps)
    # ------------------------------------------------------------------
    global_start = pd.to_datetime(global_start_date).normalize()
    global_end = pd.to_datetime(global_end_date).normalize()

    # map: emp_id -> list[pd.Timestamp]
    baseline_absent_map = {}
    for _, row in s.iterrows():
        emp_id = str(row["No."])
        dates = row["Absent_Dates"]
        if not isinstance(dates, list):
            dates = []
        ts_dates = []
        for d in dates:
            try:
                ts_dates.append(pd.to_datetime(d).normalize())
            except Exception:
                continue
        baseline_absent_map[emp_id] = sorted(ts_dates)

    # ------------------------------------------------------------------
    # 4. Compute excused dates per employee
    # ------------------------------------------------------------------
    excused_types = {"vacation", "sick", "emergency", "unpaid"}

    # Helper: clip a date range to [start,end]
    def _clip_range(sdt: pd.Timestamp, edt: pd.Timestamp,
                    win_start: pd.Timestamp, win_end: pd.Timestamp):
        if pd.isna(sdt) and pd.isna(edt):
            return None
        if pd.isna(sdt):
            sdt = edt
        if pd.isna(edt):
            edt = sdt
        sdt = pd.to_datetime(sdt).normalize()
        edt = pd.to_datetime(edt).normalize()
        if edt < sdt:
            sdt, edt = edt, sdt
        s = max(sdt, win_start)
        e = min(edt, win_end)
        if e < s:
            return None
        return pd.date_range(s, e, freq="D")

    # Pre-group overrides per employee for faster lookup
    overrides_by_emp = dict(tuple(v.groupby("id")))

    excused_total_map = {}      # emp_id -> int
    final_absent_dates_map = {} # emp_id -> list[str] (yyyy-mm-dd)
    detail_rows = []            # for per-type detail sheet

    for _, row in s.iterrows():
        emp_id = str(row["No."])
        baseline_dates = baseline_absent_map.get(emp_id, [])

        # 4.1 Effective employment window = global window adjusted by New Hire / Stop Working
        eff_start = global_start
        eff_end = global_end

        if emp_id in new_hire_map:
            eff_start = max(eff_start, new_hire_map[emp_id].normalize())
        if emp_id in stop_work_map:
            eff_end = min(eff_end, stop_work_map[emp_id].normalize())

        # If effective window is invalid: all baseline absences are auto-excused
        if eff_end < eff_start:
            excused_dates = set(baseline_dates)
            final_dates = []
            excused_total_map[emp_id] = len(excused_dates)
            final_absent_dates_map[emp_id] = []
            # still add detail row for debugging
            detail_rows.append({
                "id": emp_id,
                "type": "auto_window_exclude",
                "Window_Start": eff_start,
                "Window_End": eff_end,
                "Excused_Dates": [d.strftime("%Y-%m-%d") for d in sorted(excused_dates)],
                "Excused_Days": len(excused_dates),
            })
            continue

        # 4.2 Split baseline absences:
        #     - inside effective window
        #     - outside effective window (automatically excused)
        inside = [d for d in baseline_dates if eff_start <= d <= eff_end]
        outside = [d for d in baseline_dates if d < eff_start or d > eff_end]

        excused_dates = set(outside)  # automatically excused by New Hire / Stop Working

        # 4.3 Apply vacation / excused ranges / days
        if emp_id in overrides_by_emp:
            emp_overrides = overrides_by_emp[emp_id]

            if has_ranges:
                # range-based overrides: type + [start_date, end_date]
                for _, orow in emp_overrides.iterrows():
                    t = orow["type"]
                    if t not in excused_types:
                        continue
                    sdt = orow.get("start_date", pd.NaT)
                    edt = orow.get("end_date", pd.NaT)
                    dr = _clip_range(sdt, edt, eff_start, eff_end)
                    if dr is None:
                        continue
                    for d in dr:
                        if d in inside:  # only excuse days that were actually absent
                            excused_dates.add(d)
                # For detail sheet: store ranges per row
                for _, orow in emp_overrides.iterrows():
                    t = orow["type"]
                    if t not in excused_types:
                        continue
                    sdt = orow.get("start_date", pd.NaT)
                    edt = orow.get("end_date", pd.NaT)
                    dr = _clip_range(sdt, edt, eff_start, eff_end)
                    if dr is None:
                        dr_dates = []
                    else:
                        dr_dates = [d.strftime("%Y-%m-%d") for d in dr]
                    detail_rows.append({
                        "id": emp_id,
                        "type": t,
                        "Window_Start": eff_start,
                        "Window_End": eff_end,
                        "Excused_Dates": dr_dates,
                        "Excused_Days": len(dr_dates),
                    })

            elif has_days_col:
                # numeric-based overrides: total number of days, but no actual dates.
                # We remove N earliest inside-window absences.
                total_days = (
                    emp_overrides.loc[emp_overrides["type"].isin(excused_types), "days"]
                    .sum()
                )
                total_days = int(total_days) if pd.notna(total_days) else 0
                if total_days > 0 and inside:
                    removable = inside[:total_days]
                    for d in removable:
                        excused_dates.add(d)
                    detail_rows.append({
                        "id": emp_id,
                        "type": "numeric_excused",
                        "Window_Start": eff_start,
                        "Window_End": eff_end,
                        "Excused_Dates": [d.strftime("%Y-%m-%d") for d in removable],
                        "Excused_Days": len(removable),
                    })
            else:
                # Overrides exist but neither ranges nor days → we log but do nothing
                detail_rows.append({
                    "id": emp_id,
                    "type": "unknown_format",
                    "Window_Start": eff_start,
                    "Window_End": eff_end,
                    "Excused_Dates": [],
                    "Excused_Days": 0,
                })

        # 4.4 Final absences = baseline minus excused
        final_dates_ts = [d for d in baseline_dates if d not in excused_dates]
        final_dates_ts = sorted(final_dates_ts)
        final_dates_str = [d.strftime("%Y-%m-%d") for d in final_dates_ts]

        excused_total_map[emp_id] = len(excused_dates)
        final_absent_dates_map[emp_id] = final_dates_str

    # ------------------------------------------------------------------
    # 5. Push results back into summary_df
    # ------------------------------------------------------------------
    s["Excused_Total"] = s["No."].astype(str).map(excused_total_map).fillna(0).astype(int)
    s["Final_Absent_Dates"] = s["No."].astype(str).map(final_absent_dates_map)
    s["Final_Absent_Dates"] = s["Final_Absent_Dates"].apply(
        lambda x: x if isinstance(x, list) else []
    )
    s["Final_Absent_Days"] = s["Final_Absent_Dates"].apply(len).astype(int)

    # ------------------------------------------------------------------
    # 6. Build per-type detail dataframe
    # ------------------------------------------------------------------
    per_type_detail = pd.DataFrame(detail_rows)

    return s, per_type_detail




