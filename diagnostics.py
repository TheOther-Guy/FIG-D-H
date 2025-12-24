# diagnostics.py

import streamlit as st
import pandas as pd


def run_employee_diagnostics():
    """
    Renders an interactive diagnostics panel for investigating
    attendance logic per employee, including:

    - Raw daily punches (detailed_df)
    - Effective working window after New Hire / Stop Work
    - Vacation ranges from HR_Override
    - Pending OFF credits
    - Absent dates (final)
    - Weekend configuration
    """

    st.header("🔍 Employee Diagnostics Panel")

    # Fetch cached data from Streamlit
    detailed_df = st.session_state.get("detailed_report_df_cache", pd.DataFrame())
    summary_df = st.session_state.get("summary_report_df_cache", pd.DataFrame())
    adjusted_df = st.session_state.get("adjusted_kpi_df_cache", pd.DataFrame())
    pending_df = st.session_state.get("pending_offs_df_cache", pd.DataFrame())
    global_start = st.session_state.get("global_min_date_cache")
    global_end = st.session_state.get("global_max_date_cache")

    if summary_df.empty or detailed_df.empty:
        st.warning("No processed data available. Generate reports first.")
        return

    # Sidebar Employee selection
    emp_list = summary_df["No."].astype(str).unique()
    emp_id = st.selectbox("Select Employee No.", emp_list)

    # Filter data
    emp_summary = summary_df[summary_df["No."].astype(str) == emp_id].iloc[0]
    emp_detail = detailed_df[detailed_df["No."].astype(str) == emp_id]

    st.subheader(f"Employee: {emp_summary['Name']} (No. {emp_id})")

    # ---------------------------------------------------------------------
    # SECTION 1 — Effective Working Window (New Hire / Stop Work)
    # ---------------------------------------------------------------------

    st.markdown("### 📆 Effective Working Window")

    window_start = emp_summary.get("Overall Data Start Date", global_start)
    window_end = emp_summary.get("Overall Data End Date", global_end)

    st.write("**Window Start:**", window_start)
    st.write("**Window End:**", window_end)
    st.write("**Global Window:**", f"{global_start} → {global_end}")

    # ---------------------------------------------------------------------
    # SECTION 2 — Weekend Configuration
    # ---------------------------------------------------------------------

    st.markdown("### 🗓 Weekend Configuration")

    weekend = emp_summary.get("Expected_Weekends_In_Period", None)
    if weekend is not None:
        st.write("**Weekend Days:**", weekend)
    else:
        st.info("Weekend information not stored in summary.")

    # ---------------------------------------------------------------------
    # SECTION 3 — Raw Detailed Daily Punches
    # ---------------------------------------------------------------------

    st.markdown("### 🟦 Raw Daily Punches")
    st.dataframe(emp_detail)

    # ---------------------------------------------------------------------
    # SECTION 4 — HR Vacations (Adjusted Absences Per Type)
    # ---------------------------------------------------------------------

    st.markdown("### 🌴 HR Vacation Ranges (From HR_Override)")

    vac_rows = adjusted_df[adjusted_df["id"].astype(str) == emp_id] \
        if "id" in adjusted_df.columns else pd.DataFrame()

    if vac_rows.empty:
        st.info("No vacation/override entries for this employee.")
    else:
        st.dataframe(vac_rows)

    # ---------------------------------------------------------------------
    # SECTION 5 — Pending OFF credits
    # ---------------------------------------------------------------------

    st.markdown("### ⏳ Pending OFF Credits")

    if not pending_df.empty:
        emp_pending = pending_df[pending_df["No."].astype(str) == emp_id]
        st.dataframe(emp_pending)
    else:
        st.info("No pending OFF credits for this employee.")

    # ---------------------------------------------------------------------
    # SECTION 6 — Final Absences
    # ---------------------------------------------------------------------

    st.markdown("### 🚫 Final Absence Calculation")

    st.write("**Final Absent Days:**", emp_summary.get("Final_Absent_Days", "N/A"))
    st.write("**Final Absent Dates:**", emp_summary.get("Final_Absent_Dates", []))

    st.write("**Total Pending OFFs:**", emp_summary.get("Total_Pending_OFFs", 0))
    st.write("**Total Absent After Pending:**", emp_summary.get("Total_Absent_After_Pending", "N/A"))

    # ---------------------------------------------------------------------
    # SECTION 7 — Summary View
    # ---------------------------------------------------------------------

    st.markdown("### 📊 Summary Row")
    st.dataframe(summary_df[summary_df["No."].astype(str) == emp_id])
