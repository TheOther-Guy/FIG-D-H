import streamlit as st
import pandas as pd
import io
from datetime import date
from pending_offs import load_pending_offs_from_vacation, apply_pending_offs


# Import classes and functions from other modules
from data_processing import FingerprintProcessor # Updated import to second_cup_processor
from report_generation import ReportGenerator
from analysis_functions import (
    analyze_consecutive_absences,
    analyze_unusual_shift_durations,
    generate_location_summary,
    calculate_location_absenteeism_rates,
    calculate_top_locations_by_metric,
    analyze_employee_vs_location_averages,
    generate_location_recommendations
)
from config import COMPANY_CONFIGS, format_timedelta_to_hms # Added format_timedelta_to_hms import

# >>> NEW: vacation adjustments
from vacation_adjustment import load_vacation_file, apply_vacation_adjustments

class AppUI:
    """
    Manages the Streamlit user interface for the Fingerprint Report Generator.
    Orchestrates calls to data processing, report generation, and analysis modules.
    """

    def __init__(self):
        """Initializes the AppUI and sets up Streamlit session state variables."""
        if 'uploader_key_counter' not in st.session_state:
            st.session_state.uploader_key_counter = 0
        if 'processed_data_present' not in st.session_state:
            st.session_state.processed_data_present = False
        if 'detailed_report_df_cache' not in st.session_state:
            st.session_state.detailed_report_df_cache = pd.DataFrame()
        if 'summary_report_df_cache' not in st.session_state:
            st.session_state.summary_report_df_cache = pd.DataFrame()
        if 'error_log_df_cache' not in st.session_state:
            st.session_state.error_log_df_cache = pd.DataFrame()
        if 'download_filename_cache' not in st.session_state:
            st.session_state.download_filename_cache = "Employee_Punch_Reports.xlsx"
        if 'global_min_date_cache' not in st.session_state:
            st.session_state.global_min_date_cache = None
        if 'global_max_date_cache' not in st.session_state:
            st.session_state.global_max_date_cache = None
        if 'debug_mode' not in st.session_state:
            st.session_state.debug_mode = False
        if 'adjusted_kpi_df_cache' not in st.session_state:
            st.session_state.adjusted_kpi_df_cache = pd.DataFrame()
        if 'blocking_error' not in st.session_state:
            st.session_state.blocking_error = None

    def display_main_page(self):
        """Displays the main Streamlit page for the fingerprint report generator."""
        st.title("📊 Employee Fingerprint Report Generator")
        st.info("⬆️ Upload one or more CSV or Excel files containing employee fingerprint data.")

        company_names = list(COMPANY_CONFIGS.keys())
        selected_company_name = st.selectbox(
            "Select Company:",
            options=company_names,
            key="company_selection"
        )

        uploaded_files = st.file_uploader(
            "Select fingerprint files (.csv, .xls, .xlsx)",
            type=["csv", "xls", "xlsx"],
            accept_multiple_files=True,
            key=f"fingerprint_file_uploader_{st.session_state.uploader_key_counter}"
        )

        # >>> NEW uploader appears just below the fingerprint uploader
        vacation_file = st.file_uploader(
            "Optional: Upload Vacation/Sick/Emergency Adjustments (single company)",
            type=["csv", "xls", "xlsx"],
            key="vacation_file_uploader"
        )

        default_filename = "Employee_Punch_Reports"
        custom_filename = st.text_input(
            "Enter desired filename for the report (without extension):",
            value=default_filename,
            key="report_filename_input"
        )

        col1, col2 = st.columns([1, 1])

        with col1:
            generate_button = st.button("🚀 Generate Reports", type="primary")

        with col2:
            if st.button("🔄 New Files (Clear and Reset)", key="new_files_button"):
                self._reset_app_state()
                st.rerun()
        
        st.session_state.debug_mode = st.checkbox("Enable Debug Mode (for diagnostics)", value=st.session_state.debug_mode)

        if generate_button and uploaded_files:
            self._process_and_cache_reports(uploaded_files, selected_company_name, custom_filename, vacation_file)
            st.rerun()
        elif uploaded_files is None and not st.session_state.processed_data_present:
            st.info("Please upload your fingerprint files to start the report generation.")
        
        # Display blocking errors if any (persistent across reruns)
        if st.session_state.get('blocking_error'):
            st.error(f"🛑 **Blocking Error: Date Range Exceeded**\n\n{st.session_state.blocking_error}")
            st.info(
                "**Action Required:**\n"
                "1. Check if the file format matches `config.py`.\n"
                "2. Update `config.py` with the correct date format for this location if needed.\n"
                "3. Or fix the date format in the file itself and re-upload."
            )

        if st.session_state.processed_data_present:
            self._display_reports(selected_company_name)
            self._display_download_button()

    def _reset_app_state(self):
        """Resets all relevant session state variables to clear the app."""
        st.session_state.uploader_key_counter += 1
        st.session_state.processed_data_present = False

        # Core data caches
        st.session_state.detailed_report_df_cache = pd.DataFrame()
        st.session_state.summary_report_df_cache = pd.DataFrame()
        st.session_state.adjusted_kpi_df_cache = pd.DataFrame()
        # NEW: cache for aggregated Pending OFF credits
        st.session_state.pending_offs_df_cache = pd.DataFrame()
        st.session_state.blocking_error = None # Clear blocking error on reset

        # Meta / helper caches
        st.session_state.error_log_df_cache = pd.DataFrame()
        st.session_state.download_filename_cache = "Employee_Punch_Reports.xlsx"
        st.session_state.global_min_date_cache = None
        st.session_state.global_max_date_cache = None


    def _process_and_cache_reports(
        self,
        uploaded_files: list,
        selected_company_name: str,
        custom_filename: str,
        vacation_file
    ):
        """
        Processes uploaded files, generates reports, and caches them in session state.

        This is the main orchestration layer:
        - Builds detailed daily report from fingerprint files
        - Builds baseline summary from detailed report
        - Optionally applies HR vacation overrides (HR_Override sheet)
        - Optionally applies Pending OFF credits (Pending Off sheet)
        - Caches everything in st.session_state for later display / export
        """
        import pandas as pd
        from io import BytesIO
        from data_processing import FingerprintProcessor
        from report_generation import ReportGenerator
        from vacation_adjustment import load_vacation_file, apply_vacation_adjustments

        # Mark that we have started processing
        st.session_state.processed_data_present = True
        st.session_state.blocking_error = None # Clear previous errors


        with st.spinner("Processing files and generating reports... This may take a moment."):
            # ------------------------------------------------------------------
            # 1) Process raw fingerprint files -> combined_df
            # ------------------------------------------------------------------
            processor = FingerprintProcessor(selected_company_name)
            try:
                combined_df = processor.process_uploaded_files(uploaded_files)
            except processor.DateRangeError as dre:
                # Store error in session state to survive rerun
                st.session_state.blocking_error = str(dre)
                
                # STOP PROCESSING: Clear state and return
                st.session_state.processed_data_present = False
                st.session_state.detailed_report_df_cache = pd.DataFrame()
                st.session_state.summary_report_df_cache = pd.DataFrame()
                return

            # ------------------------------------------------------------------
            # 2) Build the detailed (daily) report
            # ------------------------------------------------------------------
            detailed_report_df = processor.calculate_daily_reports(combined_df)
            error_log = processor.get_error_log()
            global_min_date, global_max_date = processor.get_global_dates()

            # Cache detailed + date window for use in UI
            st.session_state.detailed_report_df_cache = detailed_report_df
            st.session_state.global_min_date_cache = global_min_date
            st.session_state.global_max_date_cache = global_max_date

            # ------------------------------------------------------------------
            # 3) Build the base summary (no HR overrides / pending offs yet)
            # ------------------------------------------------------------------
            if global_min_date and global_max_date and not detailed_report_df.empty:
                report_generator = ReportGenerator(selected_company_name)
                base_summary = report_generator.generate_summary_report(
                    detailed_report_df.copy(),
                    global_min_date,
                    global_max_date
                )

                # Optional baseline debug
                if st.session_state.get("debug_mode", False):
                    st.info("DEBUG: Generated baseline summary (before vacations / pending offs).")
                    st.write("Baseline summary shape:", base_summary.shape)

                # ------------------------------------------------------------------
                # 4) Optional: apply HR overrides / vacations (HR_Override sheet)
                # ------------------------------------------------------------------
                final_summary = base_summary.copy()
                adjusted_detail = pd.DataFrame()
                pending_offs_detail = pd.DataFrame()

                if vacation_file is not None:
                    try:
                        overrides_df = load_vacation_file(vacation_file)

                        if st.session_state.get("debug_mode", False):
                            st.info("DEBUG: Loaded HR_Override sheet from vacation file.")
                            st.write("HR overrides rows:", len(overrides_df))

                        # apply_vacation_adjustments returns:
                        #   - summary with Final_Absent_Days / Final_Absent_Dates
                        #   - per-type detail (Adjusted Absences (Per Type))
                        adjusted_summary, adjusted_detail = apply_vacation_adjustments(
                            base_summary.copy(),
                            overrides_df,
                            selected_company_name,
                            global_min_date,
                            global_max_date,
                            detailed_df=detailed_report_df  # pass detailed DF so Absent_Dates can be recomputed
                        )

                        final_summary = adjusted_summary

                    except Exception as e:
                        # If vacation parsing fails, fall back gracefully to base summary
                        st.error(f"Error while applying vacation adjustments: {e}")
                        if st.session_state.get("debug_mode", False):
                            st.exception(e)
                        adjusted_detail = pd.DataFrame()
                        final_summary = base_summary.copy()

                    # ------------------------------------------------------------------
                    # 5) Optional: apply Pending OFF credits (Pending Off sheet)
                    # ------------------------------------------------------------------
                    try:
                        pending_offs_df = load_pending_offs_from_vacation(vacation_file)

                        if st.session_state.get("debug_mode", False):
                            st.info("DEBUG: Loaded Pending Off sheet from vacation file.")
                            st.write("Pending OFF rows:", len(pending_offs_df))

                        if pending_offs_df is not None and not pending_offs_df.empty:
                            # apply_pending_offs uses Final_Absent_Days if present,
                            # otherwise falls back to Total_Absent_Days.
                            final_summary, pending_offs_detail = apply_pending_offs(
                                final_summary,
                                pending_offs_df
                            )

                            if st.session_state.get("debug_mode", False):
                                st.info("DEBUG: Applied pending OFF credits.")
                                st.write("Final summary (after pending offs) shape:", final_summary.shape)
                        else:
                            # Ensure we still have the expected columns in summary
                            final_summary, pending_offs_detail = apply_pending_offs(final_summary, None)

                    except Exception as e:
                        # If Pending Off parsing fails, we still keep the vacation-adjusted summary
                        st.error(f"Error while applying pending OFF credits: {e}")
                        if st.session_state.get("debug_mode", False):
                            st.exception(e)
                        # Fallback: assume no pending offs, but ensure columns exist
                        final_summary, pending_offs_detail = apply_pending_offs(final_summary, None)

                # ------------------------------------------------------------------
                # 6) Cache final summary & adjustment detail
                # ------------------------------------------------------------------
                st.session_state.summary_report_df_cache = final_summary
                st.session_state.adjusted_kpi_df_cache = adjusted_detail
                st.session_state.pending_offs_df_cache = pending_offs_detail

            else:
                # If we cannot determine a valid date window or no detailed rows,
                # we still want the UI to render gracefully.
                st.session_state.summary_report_df_cache = pd.DataFrame()
                st.session_state.adjusted_kpi_df_cache = pd.DataFrame()
                st.session_state.pending_offs_df_cache = pd.DataFrame()

            # ----------------------------------------------------------------------
            # 7) Cache error log (always)
            # ----------------------------------------------------------------------
            error_log_df_for_cache = pd.DataFrame(error_log)
            if error_log_df_for_cache.empty:
                error_log_df_for_cache = pd.DataFrame(
                    [{'Filename': 'N/A', 'Error': 'No errors recorded during file processing.'}]
                )
            st.session_state.error_log_df_cache = error_log_df_for_cache

            # ----------------------------------------------------------------------
            # 8) Cache the desired export filename
            # ----------------------------------------------------------------------
            if isinstance(custom_filename, str) and custom_filename.strip():
                st.session_state.download_filename_cache = f"{custom_filename.strip()}.xlsx"
            else:
                st.session_state.download_filename_cache = "Employee_Punch_Reports.xlsx"



    def _display_reports(self, selected_company_name: str):
        """Displays the generated reports in tabs."""
        detailed_report_df = st.session_state.detailed_report_df_cache
        summary_report_df = st.session_state.summary_report_df_cache
        adjusted_kpi_df = st.session_state.adjusted_kpi_df_cache
        error_log_df = st.session_state.error_log_df_cache
        global_min_date = st.session_state.global_min_date_cache
        global_max_date = st.session_state.global_max_date_cache

        tab1, tab2, tab3, tab4 = st.tabs(["Detailed Report", "Summary Report", "Analysis & Insights", "Vacation Adjustments"])

        with tab1:
            if not detailed_report_df.empty:
                if global_min_date and global_max_date:
                    st.success(f"✅ Successfully processed data for {len(detailed_report_df)} daily records! Overall Reporting Period: {global_min_date.strftime('%Y-%m-%d')} to {global_max_date.strftime('%Y-%m-%d')}")
                else:
                    st.success(f"✅ Successfully processed data for {len(detailed_report_df)} daily records!")
                
                st.subheader("📋 Detailed Report Preview")
                st.dataframe(detailed_report_df.head(), use_container_width=True)
            else:
                st.error("❌ No valid data could be processed for the detailed report. Please check the file formats and column names.")

        with tab2:
            if not summary_report_df.empty:
                st.subheader("📈 Summary Report Preview")
                st.dataframe(summary_report_df, use_container_width=True)
            else:
                st.warning("⚠️ Summary Report could not be generated. Please ensure valid data and company configuration.")

        with tab3:
            st.subheader("🔍 Analysis & Insights Dashboard")

            if not detailed_report_df.empty:
                location_summary_df = generate_location_summary(detailed_report_df.copy())
                location_absenteeism_df = calculate_location_absenteeism_rates(summary_report_df.copy())
                
                location_overview_for_display = location_summary_df.merge(location_absenteeism_df, on='Source_Name', how='left')
                location_overview_for_display['Absenteeism_Rate_Location'] = location_overview_for_display['Absenteeism_Rate_Location'].fillna(0).round(1)

                st.markdown("---")
                st.markdown("#### 🏢 Location Overviews & Headcounts")
                if not location_overview_for_display.empty:
                    st.info("This table summarizes key metrics and headcounts for each location, including absenteeism rates and punch behaviors.")
                    st.dataframe(location_overview_for_display, use_container_width=True)
                else:
                    st.warning("No location data available for analysis.")

        with tab4:
            st.subheader("🧾 Vacation & Absence Adjustments")
            if not adjusted_kpi_df.empty:
                st.dataframe(adjusted_kpi_df, use_container_width=True)
            else:
                st.info("No vacation or adjustment file uploaded.")

    def _display_download_button(self):
        """Displays download button for Excel report."""
        if not st.session_state.summary_report_df_cache.empty:
            from io import BytesIO
            output = BytesIO()
            report_generator = ReportGenerator("Export")
            report_generator.export_to_excel(
                st.session_state.detailed_report_df_cache,
                st.session_state.summary_report_df_cache,
                st.session_state.adjusted_kpi_df_cache,
                st.session_state.download_filename_cache,
                output
            )
            st.download_button(
                label="💾 Download Full Report",
                data=output.getvalue(),
                file_name=st.session_state.download_filename_cache,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
