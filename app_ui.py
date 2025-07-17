import streamlit as st
import pandas as pd
import io
from datetime import date

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
            self._process_and_cache_reports(uploaded_files, selected_company_name, custom_filename)
            st.rerun()
        elif uploaded_files is None and not st.session_state.processed_data_present:
            st.info("Please upload your fingerprint files to start the report generation.")
        
        if st.session_state.processed_data_present:
            self._display_reports(selected_company_name)
            self._display_download_button()

    def _reset_app_state(self):
        """Resets all relevant session state variables to clear the app."""
        st.session_state.uploader_key_counter += 1
        st.session_state.processed_data_present = False
        st.session_state.detailed_report_df_cache = pd.DataFrame()
        st.session_state.summary_report_df_cache = pd.DataFrame()
        st.session_state.error_log_df_cache = pd.DataFrame()
        st.session_state.download_filename_cache = "Employee_Punch_Reports.xlsx"
        st.session_state.global_min_date_cache = None
        st.session_state.global_max_date_cache = None

    def _process_and_cache_reports(self, uploaded_files: list, selected_company_name: str, custom_filename: str):
        """
        Processes uploaded files, generates reports, and caches them in session state.
        """
        st.session_state.processed_data_present = True
        with st.spinner("Processing files and generating reports... This may take a moment."):
            processor = FingerprintProcessor(selected_company_name)
            combined_df = processor.process_uploaded_files(uploaded_files)
            
            detailed_report_df = processor.calculate_daily_reports(combined_df)
            error_log = processor.get_error_log()
            global_min_date, global_max_date = processor.get_global_dates()

            st.session_state.detailed_report_df_cache = detailed_report_df
            st.session_state.global_min_date_cache = global_min_date
            st.session_state.global_max_date_cache = global_max_date

            if global_min_date and global_max_date and not detailed_report_df.empty:
                report_generator = ReportGenerator(selected_company_name)
                st.session_state.summary_report_df_cache = report_generator.generate_summary_report(
                    detailed_report_df.copy(), 
                    global_min_date,      
                    global_max_date
                )
            else:
                st.session_state.summary_report_df_cache = pd.DataFrame()

            error_log_df_for_cache = pd.DataFrame(error_log)
            if error_log_df_for_cache.empty:
                error_log_df_for_cache = pd.DataFrame([{'Filename': 'N/A', 'Error': 'No errors recorded during file processing.'}])
            st.session_state.error_log_df_cache = error_log_df_for_cache
            
            st.session_state.download_filename_cache = f"{custom_filename.strip()}.xlsx" if custom_filename.strip() else "Employee_Punch_Reports.xlsx"

    def _display_reports(self, selected_company_name: str):
        """Displays the generated reports in tabs."""
        detailed_report_df = st.session_state.detailed_report_df_cache
        summary_report_df = st.session_state.summary_report_df_cache
        error_log_df = st.session_state.error_log_df_cache
        global_min_date = st.session_state.global_min_date_cache
        global_max_date = st.session_state.global_max_date_cache

        tab1, tab2, tab3 = st.tabs(["Detailed Report", "Summary Report", "Analysis & Insights"])

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
                    display_cols = [
                        'Source_Name', 'Total_Employees', 'Total_Location_Punch_Days', 'Total_Original_Punches',
                        'Absenteeism_Rate_Location',
                        'Total Shift Duration (Location)', 'Avg Shift Duration Per Employee (Location)',
                        'Total More_T Hours (Location)', 'Total Short_T Hours (Location)',
                        'Total_Single_Punch_Days_Location', 'Single_Punch_Rate_Per_100_Punches',
                        'Total_More_Than_4_Punches_Days_Location', 'Multi_Punch_Rate_Per_100_Punches'
                    ]
                    display_cols_existing = [col for col in display_cols if col in location_overview_for_display.columns]
                    st.dataframe(location_overview_for_display[display_cols_existing], use_container_width=True)
                else:
                    st.info("No location data available for aggregation.")
                
                st.markdown("---")
                st.markdown("#### 🥇 Top Locations by Metric")
                if not location_overview_for_display.empty:
                    col_t1, col_t2, col_t3 = st.columns(3)
                    with col_t1:
                        st.metric("Highest Absenteeism Rate", calculate_top_locations_by_metric(location_overview_for_display, 'Absenteeism_Rate_Location'))
                        st.metric("Highest Total More_T", calculate_top_locations_by_metric(location_overview_for_display, 'Total More_T Hours (Location)'))
                    with col_t2:
                        st.metric("Highest Short_T", calculate_top_locations_by_metric(location_overview_for_display, 'Total Short_T Hours (Location)'))
                        st.metric("Highest Single Punch Rate", calculate_top_locations_by_metric(location_overview_for_display, 'Single_Punch_Rate_Per_100_Punches'))
                    with col_t3:
                        st.metric("Highest Multiple Punch Rate", calculate_top_locations_by_metric(location_overview_for_display, 'Multi_Punch_Rate_Per_100_Punches'))
                        st.metric("Highest Headcount", calculate_top_locations_by_metric(location_overview_for_display, 'Total_Employees'))
                else:
                    st.info("Location data is needed to identify top locations.")


                st.markdown("---")
                st.markdown("#### 📊 Company-Wide Averages")
                if not summary_report_df.empty:
                    avg_total_present_days = summary_report_df['Total_Present_Days'].mean()
                    
                    avg_total_shift_durations_seconds = summary_report_df['Total Shift Durations'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else pd.NaT).dt.total_seconds().sum()
                    avg_total_shift_duration = avg_total_shift_durations_seconds / summary_report_df['Total_Present_Days'].sum() if summary_report_df['Total_Present_Days'].sum() > 0 else 0
                    
                    avg_total_more_t_hours_seconds = summary_report_df['Total More_T Hours'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else pd.NaT).dt.total_seconds().sum()
                    avg_total_more_t_hours = avg_total_more_t_hours_seconds / 3600
                    
                    avg_total_short_t_hours_seconds = summary_report_df['Total Short_T Hours'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else pd.NaT).dt.total_seconds().sum()
                    avg_total_short_t_hours = avg_total_short_t_hours_seconds / 3600

                    col_c1, col_c2, col_c3 = st.columns(3)
                    with col_c1:
                        st.metric("Avg Present Days per Employee", f"{avg_total_present_days:.1f}")
                    with col_c2:
                        st.metric("Avg Shift Duration per Day", format_timedelta_to_hms(pd.Timedelta(seconds=avg_total_shift_duration)))
                    with col_c3:
                        st.metric("Avg Total More_T Hours", f"{avg_total_more_t_hours:.1f} hrs")
                        st.metric("Avg Total Short_T Hours", f"{avg_total_short_t_hours:.1f} hrs")
                else:
                    st.info("Summary report data is needed to display company-wide averages.")


                st.markdown("---")
                st.markdown("#### 💡 Recommendations Per Location")
                if not location_overview_for_display.empty:
                    location_recommendations = generate_location_recommendations(location_overview_for_display.copy(), location_absenteeism_df.copy())
                    if location_recommendations:
                        for loc, recs in location_recommendations.items():
                            st.markdown(f"**{loc}:**")
                            for rec in recs:
                                st.markdown(rec)
                            st.markdown("")
                    else:
                        st.info("No specific recommendations generated based on current thresholds and data.")
                else:
                    st.info("Location data is needed to generate recommendations.")

                st.markdown("---")
                st.markdown("#### 📊 Employee Benchmarking (Comparison to Location Averages)")
                if not summary_report_df.empty and not location_summary_df.empty:
                    st.info("This section compares individual employee performance metrics against the average for their primary location, helping to highlight outliers.")
                    employee_vs_location_avg_df = analyze_employee_vs_location_averages(summary_report_df.copy(), location_summary_df.copy())
                    st.dataframe(employee_vs_location_avg_df, use_container_width=True)
                else:
                    st.info("Summary and/or location data is needed to perform benchmarking analysis.")

                st.markdown("---")
                st.markdown("#### 📅 Consecutive Absence Analysis")
                consecutive_absences_df = analyze_consecutive_absences(detailed_report_df.copy(), summary_report_df.copy(), global_min_date, global_max_date)
                if not consecutive_absences_df.empty:
                    st.info("This table highlights employees with the longest consecutive periods of absence within the data provided.")
                    st.dataframe(consecutive_absences_df, use_container_width=True)
                else:
                    st.info("No significant consecutive absences detected or no data to analyze.")

                st.markdown("---")
                st.markdown("#### ⏳ Unusual Shift Durations (Anomalies)")
                unusual_shifts_df = analyze_unusual_shift_durations(detailed_report_df.copy(), selected_company_name)
                if not unusual_shifts_df.empty:
                    st.info("This table flags individual shifts that are unusually long or short compared to the standard shift hours defined for their company/location.")
                    st.dataframe(unusual_shifts_df, use_container_width=True)
                else:
                    st.info("No unusual shift durations detected outside defined thresholds.")
                
            else:
                st.info("Upload and process files to see the analysis dashboard.")

        if not error_log_df.empty:
            st.markdown("---")
            st.subheader("❌ Error Log")
            st.dataframe(error_log_df, use_container_width=True)

    def _display_download_button(self):
        """Displays the download button for the generated Excel report."""
        detailed_report_df = st.session_state.detailed_report_df_cache
        summary_report_df = st.session_state.summary_report_df_cache
        error_log_df = st.session_state.error_log_df_cache
        download_filename = st.session_state.download_filename_cache
        selected_company_name = st.session_state.company_selection
        global_min_date = st.session_state.global_min_date_cache
        global_max_date = st.session_state.global_max_date_cache


        if not detailed_report_df.empty:
            output_buffer = io.BytesIO()
            with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                detailed_report_df.to_excel(writer, sheet_name='Detailed Report', index=False)
                if not summary_report_df.empty:
                    summary_report_df.to_excel(writer, sheet_name='Summary Report', index=False)
                
                # Re-generate DFs for saving to Excel to ensure they are up-to-date
                location_summary_df_for_excel = generate_location_summary(detailed_report_df.copy())
                location_absenteeism_df_for_excel = calculate_location_absenteeism_rates(summary_report_df.copy())
                location_overview_for_excel = location_summary_df_for_excel.merge(location_absenteeism_df_for_excel, on='Source_Name', how='left')
                location_overview_for_excel['Absenteeism_Rate_Location'] = location_overview_for_excel['Absenteeism_Rate_Location'].fillna(0).round(1)

                consecutive_absences_df = analyze_consecutive_absences(detailed_report_df.copy(), summary_report_df.copy(), global_min_date, global_max_date) 
                unusual_shifts_df = analyze_unusual_shift_durations(detailed_report_df.copy(), selected_company_name)
                # Define location_summary_df before using it
                location_summary_df = generate_location_summary(detailed_report_df.copy()) # Re-generate location_summary_df
                employee_vs_location_avg_df = analyze_employee_vs_location_averages(summary_report_df.copy(), location_summary_df.copy())


                if not location_overview_for_excel.empty:
                    location_overview_for_excel.to_excel(writer, sheet_name='Location Overview', index=False)
                if not consecutive_absences_df.empty:
                    consecutive_absences_df.to_excel(writer, sheet_name='Consecutive Absences', index=False)
                if not unusual_shifts_df.empty:
                    unusual_shifts_df.to_excel(writer, sheet_name='Unusual Shifts', index=False)
                if not employee_vs_location_avg_df.empty:
                    employee_vs_location_avg_df.to_excel(writer, sheet_name='Emp vs Location Averages', index=False)
                error_log_df.to_excel(writer, sheet_name='Error Log', index=False)
            
            st.download_button(
                label="📥 Download All Reports (Excel)",
                data=output_buffer.getvalue(),
                file_name=download_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="secondary"
            )
        else:
            if not error_log_df.empty and not error_log_df.iloc[0]['Error'] == 'No errors recorded during file processing.':
                 error_log_output_buffer = io.BytesIO()
                 with pd.ExcelWriter(error_log_output_buffer, engine='openpyxl') as writer:
                    error_log_df.to_excel(writer, sheet_name='Error Log', index=False)
                 
                 st.download_button(
                    label="📥 Download Error Log (Excel)",
                    data=error_log_output_buffer.getvalue(),
                    file_name=f"{st.session_state.report_filename_input.strip()}_Error_Log.xlsx" if st.session_state.report_filename_input.strip() else "Error_Log.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="secondary"
                )
