import pandas as pd
from datetime import date, timedelta

from config import (
    format_timedelta_to_hms,
    get_effective_rules_for_employee_day,
    get_expected_working_days_in_period,
    COMPANY_CONFIGS,
    normalize_employee_id,
)


class ReportGenerator:
    """
    Generates summary reports from detailed daily fingerprint data
    and exports multi-sheet Excel reports.

    This implementation is aligned with the new vacation / pending-off logic:

    - Baseline `Total_Absent_Days` is computed from expected working days and PRESENT days.
    - Final absences (after vacations and pending offs) are handled in `vacation_adjustment`
      and `pending_offs` and then exported through `export_to_excel`.
    """

    def __init__(self, selected_company_name: str):
        self.selected_company_name = selected_company_name

    # ------------------------------------------------------------------
    # 1) SUMMARY GENERATION
    # ------------------------------------------------------------------
    def generate_summary_report(
        self,
        detailed_df: pd.DataFrame,
        global_start_date,
        global_end_date,
        effective_dates_map: dict = None  # New Argument
    ) -> pd.DataFrame:
        """
        Build per-employee baseline summary for the given reporting window.

        Key points:
        - Employee identity is by ID ("No.") only; data from all locations/sources
          for the same ID are combined.
        - PRESENT day := (Total Shift Duration > 0) OR (any punches >= 1)
          so single-punch and open-shift days are treated as present.
        - Baseline Total_Absent_Days := Expected_Working - Present, clipped to [0].
        - Expected working days are computed by get_expected_working_days_in_period
          using rules from get_effective_rules_for_employee_day (config.py).
        """

        from vacation_adjustment import _enumerate_absent_dates  # <-- NEW: use existing helper

        if detailed_df is None or detailed_df.empty:
            return pd.DataFrame()

        df = detailed_df.copy()

        # --- normalize Date and clip to global window ---
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        start_dt = pd.to_datetime(global_start_date)
        end_dt = pd.to_datetime(global_end_date)

        mask_window = (df["Date"] >= start_dt) & (df["Date"] <= end_dt)
        window_df = df.loc[mask_window].copy()
        if window_df.empty:
            return pd.DataFrame()

        # --- ensure timedelta helper columns exist (defensive) ---
        td_cols = {
            "Total Shift Duration_td": "Total Shift Duration",
            "Daily_More_T_Hours_td": "Daily_More_T_Hours",
            "Daily_Short_T_Hours_td": "Daily_Short_T_Hours",
            "More_T_postMID_td": "More_T_postMID",
        }
        for td_col, src in td_cols.items():
            if td_col not in window_df.columns:
                if src in window_df.columns:
                    window_df[td_col] = pd.to_timedelta(
                        window_df[src], errors="coerce"
                    ).fillna(pd.Timedelta(seconds=0))
                else:
                    window_df[td_col] = pd.Timedelta(seconds=0)
            else:
                window_df[td_col] = pd.to_timedelta(
                    window_df[td_col], errors="coerce"
                ).fillna(pd.Timedelta(seconds=0))

        # --- ensure boolean flags exist ---
        for col in ["is_more_t_day", "is_short_t_day"]:
            if col not in window_df.columns:
                window_df[col] = False
            window_df[col] = window_df[col].astype(bool)

        # --- punch counts & PRESENT logic (single-punch = present) ---
        punch_col = None
        for cand in ["Original Number of Punches", "Total Punches", "Number of Punches"]:
            if cand in window_df.columns:
                punch_col = cand
                break

        if punch_col is not None:
            punches = pd.to_numeric(window_df[punch_col], errors="coerce").fillna(0)
        else:
            punches = pd.Series(0, index=window_df.index)

        window_df["__punches"] = punches
        window_df["__is_single_punch"] = window_df["__punches"].eq(1)

        # PRESENT if duration > 0 OR any punches
        window_df["__is_present"] = (
            window_df["Total Shift Duration_td"] > pd.Timedelta(seconds=0)
        ) | (window_df["__punches"] >= 1)

        # --- helper: choose a stable name per employee (longest non-empty) ---
        def _choose_name(name_series: pd.Series) -> str:
            vals = [str(v).strip() for v in name_series if isinstance(v, str) and str(v).strip()]
            if not vals:
                return ""
            vals = sorted(vals, key=len, reverse=True)
            return vals[0]

        # --- ensure Source_Name exists ---
        if "Source_Name" not in window_df.columns:
            window_df["Source_Name"] = ""

        # --- group by employee ID ONLY (ID = single source of truth) ---
        grouped = window_df.groupby("No.")

        summary = grouped.agg(
            Name=("Name", _choose_name),
            Source_Names=(
                "Source_Name",
                lambda x: ", ".join([str(v) for v in x.dropna().unique()]),
            ),
            # unique PRESENT dates across all locations for this ID
            Total_Present_Days=(
                "Date",
                lambda x: x[window_df.loc[x.index, "__is_present"]].dt.date.nunique(),
            ),
            Total_Shift_Durations_td=("Total Shift Duration_td", "sum"),
            Total_More_T_Hours_td=("Daily_More_T_Hours_td", "sum"),
            Total_Short_T_Hours_td=("Daily_Short_T_Hours_td", "sum"),
            Total_More_T_postMID_td=("More_T_postMID_td", "sum"),
            Total_Single_Punch_Days=("__is_single_punch", "sum"),
            Total_More_Than_10_Hours_Count=("is_more_t_day", "sum"),
            Total_Short_Shifts_Count=("is_short_t_day", "sum"),
            Min_Date=("Date", "min"),
            Max_Date=("Date", "max"),
        ).reset_index()

        # --- window metadata ---
        total_days_period = (end_dt - start_dt).days + 1
        summary["Overall Data Start Date"] = start_dt.strftime("%Y-%m-%d")
        summary["Overall Data End Date"] = end_dt.strftime("%Y-%m-%d")
        summary["Total Days in Overall Period"] = int(total_days_period)

        # --- expected working days & OFFs (using config rules) ---
        summary["Total_Expected_Working_Days_In_Period"] = 0.0
        summary["Total_Employee_Period_OFFs"] = 0.0
        summary["Expected_Weekends_In_Period"] = 0.0
        summary["Expected_Rotational_Offs"] = 0.0
        summary["Rotational_Off_Weeks"] = 0.0

        # Default map if none
        if effective_dates_map is None:
            effective_dates_map = {}

        for idx, row in summary.iterrows():
            emp_no = normalize_employee_id(row["No."])
            src_names = str(row["Source_Names"]) if row["Source_Names"] else ""
            primary_source = src_names.split(",")[0].strip() if src_names else ""

            # Determine Effective Window for this employee
            # Default to global window
            eff_start_ts, eff_end_ts = effective_dates_map.get(emp_no, (start_dt, end_dt))
            
            # Ensure we don't go strictly outside the global report boundary (already clipped in helper, but double check)
            # Actually helper clips to global.
            
            eff_start_date = eff_start_ts.date()
            eff_end_date = eff_end_ts.date()
            
            # Calculate Total Days in Employee's Effective Period
            # (Used for checking if they were employed at all)
            emp_total_days = (eff_end_date - eff_start_date).days + 1
            if emp_total_days <= 0:
                 # Should not happen if clipped correctly, but handle gracefully
                 emp_total_days = 0

            try:
                rules = get_effective_rules_for_employee_day(
                    self.selected_company_name,
                    emp_no,
                    primary_source,
                )
            except Exception:
                rules = COMPANY_CONFIGS.get(self.selected_company_name, {}).get(
                    "default_rules", {}
                )

            expected_work = get_expected_working_days_in_period(
                eff_start_date,  # Use Employee Effective Start
                eff_end_date,    # Use Employee Effective End
                rules,
            )

            # Total Offs calculation:
            # Should be based on employee's period total days, NOT global total days.
            # User: "we calculate the weekends for new hiring as per their specific period"
            total_offs = float(emp_total_days) - float(expected_work)

            summary.at[idx, "Total_Expected_Working_Days_In_Period"] = float(expected_work)
            summary.at[idx, "Total_Employee_Period_OFFs"] = max(total_offs, 0.0)

            if rules.get("is_rotational_off", False):
                summary.at[idx, "Expected_Rotational_Offs"] = max(total_offs, 0.0)
                rot_per_week = rules.get("rotational_days_off_per_week", 1) or 1
                summary.at[idx, "Rotational_Off_Weeks"] = (
                    max(total_offs, 0.0) / float(rot_per_week)
                )
            else:
                summary.at[idx, "Expected_Weekends_In_Period"] = max(total_offs, 0.0)

        # --- baseline Total_Absent_Days (float, then coerced to int if whole report) ---
        summary["Total_Absent_Days"] = (
            summary["Total_Expected_Working_Days_In_Period"]
            - summary["Total_Present_Days"]
        ).clip(lower=0.0)

        # --- convert count-like metrics to whole numbers ---
        int_cols = [
            "Total Days in Overall Period",
            "Total_Expected_Working_Days_In_Period",
            "Total_Employee_Period_OFFs",
            "Expected_Weekends_In_Period",
            "Expected_Rotational_Offs",
            "Total_Present_Days",
            "Total_Absent_Days",
            "Total_Single_Punch_Days",
            "Total_More_Than_10_Hours_Count",
            "Total_Short_Shifts_Count",
        ]
        for col in int_cols:
            if col in summary.columns:
                summary[col] = summary[col].round().astype(int)

        # --- human-friendly time formatting ---
        summary["Total_Shift_Duration_hours"] = (
            summary["Total_Shift_Durations_td"].dt.total_seconds() / 3600.0
        ).round(2)

        summary["Total_Shift_Duration"] = summary["Total_Shift_Durations_td"].apply(
            format_timedelta_to_hms
        )
        summary["Total_More_T_Hours"] = summary["Total_More_T_Hours_td"].apply(
            format_timedelta_to_hms
        )
        summary["Total_Short_T_Hours"] = summary["Total_Short_T_Hours_td"].apply(
            format_timedelta_to_hms
        )
        summary["Total_More_T_postMID"] = summary["Total_More_T_postMID_td"].apply(
            format_timedelta_to_hms
        )

        summary.drop(
            columns=[
                "Total_Shift_Durations_td",
                "Total_More_T_Hours_td",
                "Total_Short_T_Hours_td",
                "Total_More_T_postMID_td",
            ],
            inplace=True,
        )

        # ------------------------------------------------------------------
        # NEW BLOCK: Baseline Absent_Dates using _enumerate_absent_dates()
        # ------------------------------------------------------------------
        # Initialize column as list-of-lists
        summary["Absent_Dates"] = [[] for _ in range(len(summary))]

        for idx, row in summary.iterrows():
            emp_no = normalize_employee_id(row["No."])
            src_names = str(row["Source_Names"]) if row["Source_Names"] else ""
            primary_source = src_names.split(",")[0].strip() if src_names else ""

            # Get rules again (same as above) to read weekend_days
            try:
                rules = get_effective_rules_for_employee_day(
                    self.selected_company_name,
                    emp_no,
                    primary_source,
                )
            except Exception:
                rules = COMPANY_CONFIGS.get(self.selected_company_name, {}).get(
                    "default_rules", {}
                )

            weekend_days = rules.get("weekend_days", [])
            # Build employee-specific daily frame
            emp_df = window_df[window_df["No."].astype(str) == emp_no].copy()

            # Use the shared helper from vacation_adjustment.py
            # CRITICAL: We pass the EMPLOYEE's effective window, not global.
            # This ensures we don't count "absences" before they were hired or after they quit.
            
            eff_start_ts, eff_end_ts = effective_dates_map.get(emp_no, (start_dt, end_dt))
            
            absent_dates_list = _enumerate_absent_dates(
                emp_df=emp_df,
                start=eff_start_ts, # Use Effective Start
                end=eff_end_ts,     # Use Effective End
                vacation_ranges=[],
                weekend_days=weekend_days,
            )

            summary.at[idx, "Absent_Dates"] = absent_dates_list
            summary.at[idx, "Total_Absent_Days"] = len(absent_dates_list)

        return summary



    def export_to_excel(
        self,
        detailed_df: pd.DataFrame,
        summary_df: pd.DataFrame,
        adjusted_kpi_df: pd.DataFrame,
        filename: str,
        output_buffer,
    ):
        """
        Export the final Excel report with all sheets:

        Sheet order (MANDATORY):
        1) Detailed Daily Report
        2) Summary
        3) Adjusted Absences (Per Type)
        4) Pending OFF Credits
        5) Error Log
        6) Days_Flags

        Fully aligned with Option A:
        - Final_Absent_Dates   = before pending
        - Final_Absent_Dates_After_Pending = after pending
        - Pending_OFF_Dates    = authoritative source for pending-offs
        """

        import streamlit as st
        import ast
        import pandas as pd
        from config import COMPANY_CONFIGS, get_effective_rules_for_employee_day


        # ------------------------------------------------------------------
        # Defensive copies
        # ------------------------------------------------------------------
        summary_df = summary_df.copy() if isinstance(summary_df, pd.DataFrame) else pd.DataFrame()
        detailed_df = detailed_df.copy() if isinstance(detailed_df, pd.DataFrame) else pd.DataFrame()
        adjusted_kpi_df = adjusted_kpi_df.copy() if isinstance(adjusted_kpi_df, pd.DataFrame) else pd.DataFrame()

        # Pull pending OFFs + error log from session
        pending_offs_df = st.session_state.get("pending_offs_df_cache", pd.DataFrame())
        error_log_df = st.session_state.get("error_log_df_cache", pd.DataFrame())
        if not isinstance(error_log_df, pd.DataFrame) or error_log_df.empty:
            error_log_df = pd.DataFrame(
                [{"Filename": "N/A", "Error": "No errors recorded during file processing."}]
            )

        # ------------------------------------------------------------------
        # SAFETY NORMALIZATION ON SUMMARY
        # ------------------------------------------------------------------
        # Ensure Absent_Dates (baseline) = Final_Absent_Dates
        if "Absent_Dates" not in summary_df.columns:
            if "Final_Absent_Dates" in summary_df.columns:
                summary_df["Absent_Dates"] = summary_df["Final_Absent_Dates"]
            else:
                summary_df["Absent_Dates"] = [[] for _ in range(len(summary_df))]

        if "Final_Absent_Days" not in summary_df.columns:
            if "Total_Absent_Days" in summary_df.columns:
                summary_df["Final_Absent_Days"] = summary_df["Total_Absent_Days"]
            else:
                summary_df["Final_Absent_Days"] = 0

        if "Total_Pending_OFFs" not in summary_df.columns:
            summary_df["Total_Pending_OFFs"] = 0

        # Ensure Final_Absent_Dates exists
        if "Final_Absent_Dates" not in summary_df.columns:
            summary_df["Final_Absent_Dates"] = summary_df["Absent_Dates"]

        # Ensure Final_Absent_Dates_After_Pending exists
        if "Final_Absent_Dates_After_Pending" not in summary_df.columns:
            summary_df["Final_Absent_Dates_After_Pending"] = summary_df["Final_Absent_Dates"]

        # Ensure Pending_OFF_Dates exists
        if "Pending_OFF_Dates" not in summary_df.columns:
            summary_df["Pending_OFF_Dates"] = [[] for _ in range(len(summary_df))]

        # Numeric reconciliation: authoritative = lists
        summary_df["Total_Absent_After_Pending"] = summary_df["Final_Absent_Dates_After_Pending"].apply(
            lambda x: len(x) if isinstance(x, list) else 0
        ).astype(int)

        # ------------------------------------------------------------------
        # SUMMARY COLUMN ORDER
        # ------------------------------------------------------------------
        summary_col_order = [
            "No.", "Name",
            "Overall Data Start Date", "Overall Data End Date",
            "Total Days in Overall Period",
            "Total_Expected_Working_Days_In_Period",
            "Total_Employee_Period_OFFs",
            "Expected_Weekends_In_Period",
            "Expected_Rotational_Offs",
            "Rotational_Off_Weeks",
            "Total_Present_Days",
            "Total_Absent_Days",
            "Absent_Dates",
            "Excused_Total",
            "Final_Absent_Days",
            "Final_Absent_Dates",
            "Total_Pending_OFFs",
            "Pending_OFF_Dates",
            "Total_Absent_After_Pending",
            "Final_Absent_Dates_After_Pending",
            "Total_Shift_Duration_hours",
            "Total_Shift_Duration",
            "Total_More_T_Hours",
            "Total_Short_T_Hours",
            "Total_More_T_postMID",
            "Total_More_Than_10_Hours_Count",
            "Total_Short_Shifts_Count",
            "Total_Single_Punch_Days",
            "Min_Date", "Max_Date",
            "Source_Names",
        ]
        summary_df = summary_df[[c for c in summary_col_order if c in summary_df.columns]]


        # ------------------------------------------------------------------
        # NORMALIZE PENDING OFFS SHEET
        # ------------------------------------------------------------------
        pending = pending_offs_df.copy() if isinstance(pending_offs_df, pd.DataFrame) else pd.DataFrame()
        if pending.empty:
            pending = pd.DataFrame([{"No.": "", "Total_Pending_OFFs": ""}])
        else:
            if "No." not in pending.columns:
                first = pending.columns[0]
                pending.rename(columns={first: "No."}, inplace=True)
            pending["No."] = pending["No."].astype(str)
            if "Total_Pending_OFFs" not in pending.columns:
                for c in pending.columns:
                    if "day" in str(c).lower():
                        pending["Total_Pending_OFFs"] = pending[c]
                        break
                if "Total_Pending_OFFs" not in pending.columns:
                    pending["Total_Pending_OFFs"] = 0

        # ------------------------------------------------------------------
        # DAYS_FLAGS BUILDER — Option A
        # ------------------------------------------------------------------
        def _parse_list(val):
            if val is None: return []
            if isinstance(val, list): return val
            if isinstance(val, (tuple, set)): return list(val)
            if isinstance(val, float) and pd.isna(val): return []
            if isinstance(val, str):
                txt = val.strip()
                if not txt: return []
                if txt.startswith("[") and txt.endswith("]"):
                    try:
                        return list(ast.literal_eval(txt))
                    except Exception:
                        pass
                return [txt]
            return [str(val)]

        # presence days
        presence_map = {}
        if not detailed_df.empty and "Date" in detailed_df.columns:
            work = detailed_df.copy()
            work["Date"] = pd.to_datetime(work["Date"], errors="coerce")

            punch_col = None
            for col in ["Original Number of Punches", "Total Punches", "Number of Punches"]:
                if col in work.columns:
                    punch_col = col
                    break

            punches = pd.to_numeric(work[punch_col], errors="coerce").fillna(0) if punch_col else 0
            work["__p"] = punches

            for emp, grp in work.groupby("No."):
                presence_map[str(emp)] = set(grp.loc[grp["__p"] >= 1, "Date"].dt.date.tolist())

        days_rows = []

        for _, row in summary_df.iterrows():
            emp = str(row["No."])
            name = row.get("Name", "")

            try:
                start = pd.to_datetime(row["Overall Data Start Date"]).date()
                end   = pd.to_datetime(row["Overall Data End Date"]).date()
            except:
                continue

            all_days = [d.date() for d in pd.date_range(start, end, freq="D")]

            # weekend config
            src = str(row.get("Source_Names", ""))
            primary = src.split(",")[0].strip() if src else ""
            try:
                rules = get_effective_rules_for_employee_day(self.selected_company_name, emp, primary)
            except:
                rules = COMPANY_CONFIGS.get(self.selected_company_name, {}).get("default_rules", {})
            week_set = set(int(x) for x in rules.get("weekend_days", []) if x is not None)

            # parse authoritative lists
            absent_before = set(pd.to_datetime(d, errors="coerce").date()
                                for d in _parse_list(row["Final_Absent_Dates"]) if d)

            absent_after = set(pd.to_datetime(d, errors="coerce").date()
                            for d in _parse_list(row["Final_Absent_Dates_After_Pending"]) if d)

            pending_dates = set(pd.to_datetime(d, errors="coerce").date()
                            for d in _parse_list(row["Pending_OFF_Dates"]) if d)

            # vacation = absent_before - absent_after - pending (approx Option A)
            vacation_dates = absent_before - absent_after - pending_dates

            presence = presence_map.get(emp, set())

            # signals = presence.union(absent_before, absent_after, vacation_dates)
            
            # FIXED LOGIC: Do not infer "before hiring" or "after stop" just because of missing data at edges.
            # Rely on vacation_adjustment to have already filtered "absent" dates if they 
            # were truly out of window. If a day is in the global window but has no data,
            # it should be considered "working day" or "weekend" or "absent", NOT "before hiring".
            
            # However, if vacation_adjustment DID filter dates (e.g. absent_before starts late),
            # we might want to respect that. But vacation_adjustment doesn't pass the *reason* for filtering.
            
            # The Safest default for existing employees is the global window.
            earliest, latest = start, end

            for d in all_days:
                if d < earliest:
                    flag = "is_before_hiring"
                elif d > latest:
                    flag = "is_after_stopWORK"
                else:
                    if d.weekday() in week_set:
                        flag = "is_weekend"
                    elif d in vacation_dates:
                        flag = "is_vacation"
                    elif d in pending_dates:
                        flag = "is_pending_off"
                    elif d in absent_after:
                        flag = "is_absent"
                    else:
                        flag = "is_working_day"

                days_rows.append({
                    "No.": emp,
                    "Name": name,
                    "Date": d.strftime("%d/%m/%Y"),
                    "Day_Flag": flag,
                })

        days_df = pd.DataFrame(days_rows)

        # ------------------------------------------------------------------
        # WRITE EXCEL — Correct sheet order
        # ------------------------------------------------------------------
        with pd.ExcelWriter(output_buffer, engine="xlsxwriter") as writer:

            # 1) Detailed Daily Report
            if not detailed_df.empty:
                detailed_df.to_excel(writer, sheet_name="Detailed Daily Report", index=False)

            # 2) Summary
            summary_df.to_excel(writer, sheet_name="Summary", index=False)

            # 3) Adjusted absences
            if not adjusted_kpi_df.empty:
                adjusted_kpi_df.to_excel(writer, sheet_name="Adjusted Absences (Per Type)", index=False)

            # 4) Pending OFF Credits
            pending.to_excel(writer, sheet_name="Pending OFF Credits", index=False)

            # 5) Error Log
            error_log_df.to_excel(writer, sheet_name="Error Log", index=False)

            # 6) Days_Flags
            if not days_df.empty:
                days_df.to_excel(writer, sheet_name="Days_Flags", index=False)

        output_buffer.seek(0)




