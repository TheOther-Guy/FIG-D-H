"""
pending_offs.py

Handles extraction and application of Pending OFF credits from a vacation workbook.
Adds robust sheet detection, flexible parsing, and safe aggregation.

Updated Logic:
- Detects sheets named “Pending Off”, “Pending OFF”, “Pending Offs”, “Pending OFF Credits”, etc.
- Parses flexible column names (ID, No., EmployeeID, etc.)
- Handles decimal days (e.g., 0.5)
- Aggregates per employee: No., Total_Pending_OFFs
- Adds detailed logging for debug mode
"""

import pandas as pd
import streamlit as st


# -----------------------------------------------------------
# 1. Sheet detection (robust fuzzy match)
# -----------------------------------------------------------

PENDING_OFF_PREFERRED_SHEETS = [
    "pending off",
    "pending_off",
    "pending offs",
    "pending offs credits",
    "pending off credits",
    "pending off credit",
    "pending",
    "pending off sheet",
]

def _aggregate_pending_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize and aggregate pending off data for all companies.

    Input:
        df → raw pending off DataFrame after header detection.

    Output:
        DataFrame with columns:
            ["No.", "Total_Pending_OFFs"]

    Behavior:
    - Auto-detects the employee ID column
    - Auto-detects pending off day column
    - Casts days to numeric
    - Aggregates by "No."
    """

    import numpy as np
    import logging

    if df is None or df.empty:
        return pd.DataFrame(columns=["No.", "Total_Pending_OFFs"])

    # Normalize columns to lowercase simple names
    norm_cols = {c: str(c).strip().lower() for c in df.columns}
    df = df.rename(columns=norm_cols)

    # Possible ID column names
    id_candidates = [
        "no.", "no", "id", "employee", "employee id", "emp id",
        "staff", "staff id", "code"
    ]

    id_col = None
    for col in df.columns:
        if col in id_candidates:
            id_col = col
            break

    if id_col is None:
        logging.error(f"_aggregate_pending_df: No ID column found. Columns={df.columns}")
        return pd.DataFrame(columns=["No.", "Total_Pending_OFFs"])

    # Possible pending-day columns
    pending_candidates = [
        "pending_days", "pending off", "pending off days",
        "number of days", "days", "pending", "off days"
    ]

    pending_col = None
    for col in df.columns:
        if col in pending_candidates:
            pending_col = col
            break

    if pending_col is None:
        logging.error(f"_aggregate_pending_df: No pending-day column found. Columns={df.columns}")
        return pd.DataFrame(columns=["No.", "Total_Pending_OFFs"])

    # Clean + numeric
    df[id_col] = df[id_col].astype(str).str.strip()
    df[pending_col] = (
        pd.to_numeric(df[pending_col], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    # Aggregate days per employee
    grouped = (
        df.groupby(id_col)[pending_col].sum()
        .reset_index()
        .rename(columns={id_col: "No.", pending_col: "Total_Pending_OFFs"})
    )

    return grouped


def _normalize(name: str) -> str:
    """Normalize sheet names for comparison."""
    return str(name).strip().lower().replace(" ", "_")


def _is_pending_off_sheet(sheet_name: str) -> bool:
    """Returns True if sheet name resembles Pending Off sheet."""
    norm = _normalize(sheet_name)

    # Preferred direct match
    for pref in PENDING_OFF_PREFERRED_SHEETS:
        if pref in norm:
            return True

    # heuristic: contains both "pending" and "off"
    if "pending" in norm and "off" in norm:
        return True

    return False


# -----------------------------------------------------------
# 2. Load Pending OFF sheet from vacation workbook
# -----------------------------------------------------------
def load_pending_offs_from_vacation(vacation_file):
    """
    Load Pending Off data from the vacation workbook.

    - Handles messy Excel formatting where the *real* header row
      (Trans, Date, ID, Name, from, till, Number of Days)
      is not in row 0 but inside the data.
    - Auto-detects the header row, re-reads the sheet with that row as header,
      then delegates normalization + aggregation to _aggregate_pending_df.

    Returns:
        DataFrame with columns ['No.', 'Total_Pending_OFFs'].
    """
    import logging
    import pandas as pd

    try:
        xls = pd.ExcelFile(vacation_file)
        
        # Fuzzy match to find the correct sheet name
        target_sheet_name = None
        for sheet_name in xls.sheet_names:
            if _is_pending_off_sheet(sheet_name):
                target_sheet_name = sheet_name
                break
        
        if target_sheet_name is None:
            logging.warning("Pending Off sheet not found in vacation file (checked variants).")
            return pd.DataFrame(columns=["No.", "Total_Pending_OFFs"])

        logging.info(f"Found Pending Off sheet as: '{target_sheet_name}'")

        # First read: raw, no header, so we can detect where the real header is.
        raw = pd.read_excel(vacation_file, sheet_name=target_sheet_name, header=None)

        header_row_index = None
        max_scan = min(10, len(raw))  # scan top 10 rows max

        for i in range(max_scan):
            row_vals = raw.iloc[i].astype(str).str.lower()
            if any(
                token in row_vals.values
                for token in ["id", "no.", "no", "employee", "emp id"]
            ):
                header_row_index = i
                break

        if header_row_index is None:
            logging.warning(
                f"Could not auto-detect header row in Pending Off sheet '{target_sheet_name}'. "
                "Falling back to header=0."
            )
            df = pd.read_excel(
                vacation_file,
                sheet_name=target_sheet_name,
                header=0,
            )
        else:
            df = pd.read_excel(
                vacation_file,
                sheet_name=target_sheet_name,
                header=header_row_index,
            )

        # Let the shared helper handle flexible header names and aggregation.
        agg = _aggregate_pending_df(df)
        logging.info(
            f"Loaded pending offs for {len(agg)} employees from vacation file."
        )
        return agg

    except Exception as e:
        logging.exception(f"Failed to load pending offs from vacation file: {e}")
        return pd.DataFrame(columns=["No.", "Total_Pending_OFFs"])




# -----------------------------------------------------------
# 3. Apply Pending OFF credits to summary
# -----------------------------------------------------------

def apply_pending_offs(summary_df, pending_df):
    """
    Deducts Pending OFF credits from:
      Final_Absent_Days → if present
      else fallback to Total_Absent_Days

    Also builds date-level mappings:
      - Final_Absent_Dates_After_Pending:
          Final_Absent_Dates with the most recent N days
          (N = Total_Pending_OFFs) removed.
      - Pending_OFF_Dates:
          The N most recent absent dates that were covered
          by pending OFF credits.

    Returns:
        updated_summary_df
        detail_df → aggregated pending OFFs (unchanged structure)
    """

    import ast
    import pandas as pd
    import streamlit as st

    s = summary_df.copy()

    # ---------------------------------------------
    # 1) Baseline absent days (before pending offs)
    # ---------------------------------------------
    if "Final_Absent_Days" in s.columns:
        baseline = s["Final_Absent_Days"].astype(float)
        base_days_col = "Final_Absent_Days"
    else:
        baseline = s.get("Total_Absent_Days", pd.Series([0] * len(s))).astype(float)
        base_days_col = "Total_Absent_Days"

    # ---------------------------------------------
    # 2) No pending offs → just ensure columns exist
    # ---------------------------------------------
    if pending_df is None or pending_df.empty:
        s["Total_Pending_OFFs"] = 0
        s["Total_Absent_After_Pending"] = baseline.astype(int)

        # If there is a list of absent dates, keep it as "after pending"
        if "Final_Absent_Dates_After_Pending" not in s.columns:
            if "Final_Absent_Dates" in s.columns:
                s["Final_Absent_Dates_After_Pending"] = s["Final_Absent_Dates"]
            elif "Absent_Dates" in s.columns:
                s["Final_Absent_Dates_After_Pending"] = s["Absent_Dates"]
            else:
                s["Final_Absent_Dates_After_Pending"] = [[] for _ in range(len(s))]

        # Ensure Pending_OFF_Dates exists (empty) for downstream flags
        if "Pending_OFF_Dates" not in s.columns:
            s["Pending_OFF_Dates"] = [[] for _ in range(len(s))]

        return s, pd.DataFrame(columns=["No.", "Total_Pending_OFFs"])

    # ---------------------------------------------
    # 3) Normalize IDs in pending_df
    # ---------------------------------------------
    pending_df = pending_df.copy()
    pending_df["No."] = pending_df["No."].astype(str).str.strip()

    # ---------------------------------------------
    # 4) Merge + numeric pending offs
    # ---------------------------------------------
    merged = s.merge(
        pending_df,
        on="No.",
        how="left"
    )

    merged["Total_Pending_OFFs"] = (
        pd.to_numeric(merged["Total_Pending_OFFs"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    # ---------------------------------------------
    # 5) Total_Absent_After_Pending (numeric, initial)
    #    (will be reconciled with date lists later)
    # ---------------------------------------------
    merged["Total_Absent_After_Pending"] = (
        baseline - merged["Total_Pending_OFFs"]
    ).clip(lower=0).astype(int)

    # ---------------------------------------------
    # 6) Date-level logic for pending OFFs
    #     - We take the *most recent* N days from the
    #       "Final_Absent_Dates" list (if present) as pending OFFs.
    # ---------------------------------------------
    def _parse_date_list(val):
        """Robustly parse stored date lists from summary (list/str/NaN)."""
        if val is None:
            return []
        if isinstance(val, list):
            return val
        if isinstance(val, (set, tuple)):
            return list(val)
        if isinstance(val, float) and pd.isna(val):
            return []
        if isinstance(val, str):
            text = val.strip()
            if not text:
                return []
            # Try to parse a python list literal first
            if text.startswith("[") and text.endswith("]"):
                try:
                    parsed = ast.literal_eval(text)
                    if isinstance(parsed, (list, tuple, set)):
                        return list(parsed)
                except Exception:
                    # fall through to single-date interpretation
                    pass
            # Fallback: treat as single date string
            return [text]
        # Unknown type → try to cast to string as single date
        return [str(val)]

    # Column that holds the pre-pending absent dates
    if "Final_Absent_Dates" in merged.columns:
        date_col_base = "Final_Absent_Dates"
    elif "Absent_Dates" in merged.columns:
        date_col_base = "Absent_Dates"
    else:
        date_col_base = None

    final_after_pending_col = []
    pending_off_dates_col = []

    if date_col_base is not None:
        cleaned_lists = []

        for _, row in merged.iterrows():
            raw_list = _parse_date_list(row[date_col_base])

            # Normalize to unique, sorted dates (as python date objects)
            dt_list = []
            for d in raw_list:
                try:
                    dt_list.append(pd.to_datetime(d).date())
                except Exception:
                    continue
            dt_list = sorted(set(dt_list))  # oldest -> newest

            pending_n = int(row.get("Total_Pending_OFFs", 0) or 0)

            if pending_n <= 0 or not dt_list:
                remaining_dt = dt_list
                pending_dt = []
            else:
                # most recent N dates → pending OFF
                if pending_n >= len(dt_list):
                    pending_dt = dt_list[:]          # all become pending
                    remaining_dt = []
                else:
                    pending_dt = dt_list[-pending_n:]  # newest N
                    remaining_dt = dt_list[:-pending_n]

            # Store canonical full list (ISO strings)
            cleaned_lists.append([d.isoformat() for d in dt_list])

            # Store remaining (after pending) also as ISO
            final_after_pending_col.append([d.isoformat() for d in remaining_dt])

            # Store pending OFF dates explicitly (ISO)
            pending_off_dates_col.append([d.isoformat() for d in sorted(pending_dt)])

        # Update base date column with cleaned ISO strings
        merged[date_col_base] = cleaned_lists
    else:
        # No date column at all → all empty
        final_after_pending_col = [[] for _ in range(len(merged))]
        pending_off_dates_col = [[] for _ in range(len(merged))]

    merged["Final_Absent_Dates_After_Pending"] = final_after_pending_col
    merged["Pending_OFF_Dates"] = pending_off_dates_col

    # Reconcile numeric Total_Absent_After_Pending with date lists (authoritative)
    merged["Total_Absent_After_Pending"] = merged["Final_Absent_Dates_After_Pending"].apply(
        lambda lst: len(lst) if isinstance(lst, list) else 0
    ).astype(int)

    # ---------------------------------------------
    # 7) Debug info (optional)
    # ---------------------------------------------
    if st.session_state.get("debug_mode", False):
        st.info("DEBUG: Pending OFF deduction applied (with date-level mapping).")
        debug_cols = [
            "No.",
            base_days_col,
            "Total_Pending_OFFs",
            "Total_Absent_After_Pending",
        ]
        if "Final_Absent_Dates" in merged.columns:
            debug_cols.append("Final_Absent_Dates")
        debug_cols.append("Final_Absent_Dates_After_Pending")
        debug_cols.append("Pending_OFF_Dates")
        st.write(merged[debug_cols])

    detail_df = pending_df.copy()

    return merged, detail_df



