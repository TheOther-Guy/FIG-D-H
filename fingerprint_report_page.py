import streamlit as st
import pandas as pd
import io
import calendar
import os # Imported for os.path.splitext, though actual file paths are not used for uploads

# --- Helper Function: Formats a pandas Timedelta object into HH:MM:SS string. ---
def format_timedelta_to_hms(td):
    """
    Formats a pandas Timedelta object into HH:MM:SS string.
    Returns '00:00:00' for NaN values.
    """
    if pd.isna(td):
        return '00:00:00'
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

# --- Function to process a single uploaded fingerprint file ---
def process_single_fingerprint_file(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> pd.DataFrame:
    """
    Reads a single uploaded fingerprint file (CSV or Excel),
    adds a 'Source_Name' column, and converts the 'Date/Time' column to datetime objects.

    Args:
        uploaded_file (streamlit.runtime.uploaded_file_manager.UploadedFile):
            The uploaded file object from Streamlit.

    Returns:
        pd.DataFrame: A DataFrame with the processed data.
    """
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
    df = pd.DataFrame() # Initialize df to handle cases where read fails early

    try:
        if file_extension == '.csv':
            # For CSV, decode content as string and use StringIO
            df = pd.read_csv(io.StringIO(uploaded_file.getvalue().decode('utf-8')))
        elif file_extension in ['.xls', '.xlsx']:
            # For Excel, use BytesIO
            df = pd.read_excel(io.BytesIO(uploaded_file.getvalue()))
        else:
            raise ValueError(f"Unsupported file type for '{uploaded_file.name}'. Only .csv, .xls, and .xlsx are supported.")
    except Exception as e:
        raise ValueError(f"Could not read file '{uploaded_file.name}' (format error or corruption): {e}")

    # Extract source name from filename
    filename = uploaded_file.name
    source_name_parts = filename.split('.xlsx - ')
    # Handles cases like "Report.xlsx - DeviceName.xlsx" or just "Report.xlsx"
    source_name = source_name_parts[-1].replace(os.path.splitext(source_name_parts[-1])[1], '') if len(source_name_parts) > 1 else os.path.splitext(filename)[0]
    df['Source_Name'] = source_name.strip()

    required_cols_for_processing = ['No.', 'Name', 'Date/Time', 'Status']
    missing_cols = [col for col in required_cols_for_processing if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in '{uploaded_file.name}': {', '.join(missing_cols)}")

    try:
        # Attempt to parse Date/Time, coercing errors to NaT (Not a Time)
        df['Date/Time'] = pd.to_datetime(df['Date/Time'], format='%d/%m/%Y %I:%M:%S %p', errors='coerce')
        # Drop rows where Date/Time could not be parsed
        df.dropna(subset=['Date/Time'], inplace=True)
        if df.empty:
            raise ValueError(f"No valid 'Date/Time' entries in '{uploaded_file.name}' after parsing and cleaning.")
    except Exception as e:
        raise ValueError(f"Error parsing 'Date/Time' column in '{uploaded_file.name}': {e}. Check date format.")

    # Ensure 'Status' column is string type and handle NaNs
    if 'Status' in df.columns:
        df['Status'] = df['Status'].astype(str)
        df['Status'] = df['Status'].replace('nan', '').fillna('')

    return df

# --- Function to calculate shift durations from a list of uploaded files ---
def calculate_shift_durations_from_uploads(uploaded_files: list) -> tuple[pd.DataFrame, list]:
    """
    Reads fingerprint files from a list of uploaded Streamlit files, combines them,
    and calculates detailed shift and break durations based on new case-by-case logic,
    including original and cleaned punch counts, and handling the 1 AM day-end rule.

    Args:
        uploaded_files (list): A list of Streamlit UploadedFile objects.

    Returns:
        tuple[pd.DataFrame, list]: A tuple containing the detailed DataFrame and a list of error dictionaries.
    """
    list_of_dfs = []
    error_log = [] # Collect errors here

    if not uploaded_files:
        return pd.DataFrame(), [{'Filename': 'N/A', 'Error': 'No files uploaded to process.'}]

    for uploaded_file in uploaded_files:
        try:
            df = process_single_fingerprint_file(uploaded_file)
            list_of_dfs.append(df)
        except Exception as e:
            error_message = f"Error processing {uploaded_file.name}: {type(e).__name__}: {e}"
            error_log.append({'Filename': uploaded_file.name, 'Error': error_message})

    if not list_of_dfs:
        return pd.DataFrame(), error_log

    combined_df = pd.concat(list_of_dfs, ignore_index=True)

    final_required_cols = ['No.', 'Name', 'Date/Time', 'Status']
    if not all(col in combined_df.columns for col in final_required_cols):
        missing = [col for col in final_required_cols if col not in combined_df.columns]
        err_msg = f"After combining all files, missing crucial columns: {', '.join(missing)}. " \
                  "Please check column headers across all your input files."
        error_log.append({'Filename': 'Combined Data', 'Error': err_msg})
        return pd.DataFrame(), error_log

    # Identify and remove exact duplicate rows based on key columns, including 'Source_Name'
    initial_duplicates = combined_df.duplicated(subset=['No.', 'Name', 'Date/Time', 'Status', 'Source_Name'], keep='first').sum()
    if initial_duplicates > 0:
        combined_df.drop_duplicates(subset=['No.', 'Name', 'Date/Time', 'Status', 'Source_Name'], keep='first', inplace=True)
    
    combined_df = combined_df.sort_values(by=['No.', 'Date/Time']).reset_index(drop=True)
    
    # --- RULE: Adjust Date for punches between 12:00 AM and 1:00 AM ---
    # Punches in this window belong to the previous calendar day's shift.
    combined_df['Date'] = combined_df['Date/Time'].dt.date
    should_shift_date = (combined_df['Date/Time'].dt.hour == 0) & \
                        (combined_df['Date/Time'].dt.minute >= 0) & \
                        (combined_df['Date/Time'].dt.minute < 60) # 12:00 AM to 12:59 AM

    combined_df.loc[should_shift_date, 'Date'] = (
        pd.to_datetime(combined_df.loc[should_shift_date, 'Date']) - pd.Timedelta(days=1)
    ).dt.date
    # --- END Date Adjustment Rule ---

    def get_detailed_punch_info_for_group(group):
        """
        Custom aggregation function to determine detailed shift and break durations
        for each employee-day group based on the number of punches, and new cleaning rules.
        """
        group = group.sort_values(by='Date/Time').reset_index(drop=True)

        if group.empty:
            return {
                'No.': None, 'Name': None, 'Date': None, 'Source_Name': None,
                'Original Number of Punches': 0,
                'Number of Cleaned Punches': 0,
                'First Punch Time': 'N/A', 'Last Punch Time': 'N/A',
                'Total Shift Duration': '00:00:00',
                'Total Break Duration': '00:00:00',
                'Punch Status': 'No valid punches for day'
            }

        original_punch_count = len(group) # Keep original count before any cleaning

        # --- Universal Cleaning: Apply 10-minute consolidation for all punch counts ---
        consolidated_punches_list = []
        consolidated_punches_list.append(group.iloc[0]) # Always keep the first punch
        for i in range(1, original_punch_count):
            current_punch = group.iloc[i]
            last_kept_punch = consolidated_punches_list[-1]
            
            # Condition to keep the current punch:
            # 1. If it's more than 10 minutes after the last kept punch, OR
            # 2. If its status is different from the last kept punch (regardless of time)
            if (current_punch['Date/Time'] - last_kept_punch['Date/Time']) > pd.Timedelta(minutes=10) or \
               current_punch['Status'] != last_kept_punch['Status']:
                consolidated_punches_list.append(current_punch)
        cleaned_group = pd.DataFrame(consolidated_punches_list)
        cleaned_punch_count = len(cleaned_group) # Count after universal 10-min cleaning

        # --- Initialize all output variables ---
        total_shift_duration = pd.Timedelta(seconds=0)
        total_break_duration = pd.Timedelta(seconds=0)
        punch_status = "N/A"
        
        # Lists to store individual interval durations
        individual_interval_details = [] 

        # Punch Times (from original group, before any cleaning)
        first_punch_time_raw = group.iloc[0]['Date/Time']
        last_punch_time_raw = group.iloc[-1]['Date/Time']
        first_punch_time_formatted = first_punch_time_raw.strftime('%I:%M:%S %p')
        last_punch_time_formatted = last_punch_time_raw.strftime('%I:%M:%S %p')

        # --- Apply Case-by-Case Logic (based on cleaned_punch_count) ---
        if cleaned_punch_count == 0:
            punch_status = "No valid punches after cleaning"
            
        elif cleaned_punch_count == 1:
            total_shift_duration = pd.Timedelta(seconds=0)
            total_break_duration = pd.Timedelta(seconds=0)
            punch_status = "Single Punch (0 Shift Duration)"

        elif cleaned_punch_count == 2:
            interval = cleaned_group.iloc[1]['Date/Time'] - cleaned_group.iloc[0]['Date/Time']
            if interval > pd.Timedelta(minutes=10):
                total_shift_duration = interval
                punch_status = "Single Shift (2 Punches)"
                individual_interval_details.append({'type': 'Shift', 'duration': interval})
            else:
                total_shift_duration = pd.Timedelta(seconds=0)
                punch_status = "Short 2-Punch Interval (0 Shift Duration)"
                individual_interval_details.append({'type': 'Ignored Short', 'duration': interval}) 
            total_break_duration = pd.Timedelta(seconds=0)

        elif cleaned_punch_count == 3:
            total_shift_duration = cleaned_group.iloc[2]['Date/Time'] - cleaned_group.iloc[0]['Date/Time']
            total_break_duration = pd.Timedelta(seconds=0) # Status ignored for 3 punches
            punch_status = "Shift (3 Punches, First to Last)"
            # Record general intervals between punches
            individual_interval_details.append({'type': 'General', 'duration': cleaned_group.iloc[1]['Date/Time'] - cleaned_group.iloc[0]['Date/Time']})
            individual_interval_details.append({'type': 'General', 'duration': cleaned_group.iloc[2]['Date/Time'] - cleaned_group.iloc[1]['Date/Time']})

        elif cleaned_punch_count == 4:
            # Case 1: In, Out, In, Out pattern (status-aware)
            p1, p2, p3, p4 = cleaned_group.iloc[0], cleaned_group.iloc[1], cleaned_group.iloc[2], cleaned_group.iloc[3]

            if (p1['Status'] == 'C/In' and p2['Status'] == 'C/Out' and
                p3['Status'] == 'C/In' and p4['Status'] == 'C/Out'):
                
                shift1 = p2['Date/Time'] - p1['Date/Time']
                break1 = p3['Date/Time'] - p2['Date/Time']
                shift2 = p4['Date/Time'] - p3['Date/Time']

                total_shift_duration = shift1 + shift2
                total_break_duration = break1
                punch_status = "Two Shifts with One Break (4 Punches, Status Matched)"
                individual_interval_details.append({'type': 'Shift', 'duration': shift1})
                individual_interval_details.append({'type': 'Break', 'duration': break1})
                individual_interval_details.append({'type': 'Shift', 'duration': shift2})
            else:
                # Case 2: 4 punches, but not the clean In, Out, In, Out pattern (status ignored for total presence)
                total_shift_duration = last_punch_time_raw - first_punch_time_raw # Total presence duration
                total_break_duration = pd.Timedelta(seconds=0)
                punch_status = "Complex 4-Punch Pattern (Total Presence, Status Mismatch)"
                for i in range(len(cleaned_group) - 1):
                    interval = cleaned_group.iloc[i+1]['Date/Time'] - cleaned_group.iloc[i]['Date/Time']
                    individual_interval_details.append({'type': 'General', 'duration': interval})

        else: # cleaned_punch_count > 4
            total_shift_duration = last_punch_time_raw - first_punch_time_raw # Total presence duration
            total_break_duration = pd.Timedelta(seconds=0) # No explicit breaks in this complex scenario
            punch_status = f"Complex Pattern ({cleaned_punch_count} Cleaned Punches)"
            for i in range(len(cleaned_group) - 1):
                interval = cleaned_group.iloc[i+1]['Date/Time'] - cleaned_group.iloc[i]['Date/Time']
                individual_interval_details.append({'type': 'General', 'duration': interval})

        # Prepare intervals for output columns based on their type
        intervals_output_dict = {}
        shift_col_count = 0
        break_col_count = 0
        general_col_count = 0

        for item in individual_interval_details:
            if item['type'] == 'Shift':
                shift_col_count += 1
                intervals_output_dict[f'Shift {shift_col_count} Duration'] = format_timedelta_to_hms(item['duration'])
            elif item['type'] == 'Break':
                break_col_count += 1
                intervals_output_dict[f'Break {break_col_count} Duration'] = format_timedelta_to_hms(item['duration'])
            else: # 'General' or 'Ignored Short'
                general_col_count += 1
                intervals_output_dict[f'Interval {general_col_count} Duration'] = format_timedelta_to_hms(item['duration'])

        return_data = {
            'No.': group['No.'].iloc[0],
            'Name': group['Name'].iloc[0],
            'Date': group['Date'].iloc[0],
            'Source_Name': group['Source_Name'].iloc[0],
            'Original Number of Punches': original_punch_count,
            'Number of Cleaned Punches': cleaned_punch_count,
            'First Punch Time': first_punch_time_formatted,
            'Last Punch Time': last_punch_time_formatted,
            'Total Shift Duration': format_timedelta_to_hms(total_shift_duration),
            'Total Break Duration': format_timedelta_to_hms(total_break_duration),
            'Punch Status': punch_status,
        }
        return_data.update(intervals_output_dict)

        return return_data

    daily_report_list = []
    if combined_df.empty:
        return pd.DataFrame(), error_log

    grouping_cols = ['No.', 'Name', 'Date']
    if not all(col in combined_df.columns for col in grouping_cols):
        err_msg = f"Cannot group data: Missing one or more grouping columns ({', '.join(grouping_cols)})."
        error_log.append({'Filename': 'Combined Data', 'Error': err_msg})
        return pd.DataFrame(), error_log

    for (no, name, date), group in combined_df.groupby(grouping_cols):
        detailed_info = get_detailed_punch_info_for_group(group)
        daily_report_list.append(detailed_info)

    daily_report = pd.DataFrame(daily_report_list)

    # Fill NaN values for all dynamically generated duration columns
    for col in daily_report.columns:
        if 'Duration' in col: # Catches Shift X, Break X, Interval X
            daily_report[col] = daily_report[col].fillna('00:00:00')

    # Define the desired fixed column order
    fixed_cols = ['Source_Name', 'No.', 'Name', 'Date', 
                  'Original Number of Punches', 'Number of Cleaned Punches',
                  'First Punch Time', 'Last Punch Time',
                  'Total Shift Duration', 'Total Break Duration', 'Punch Status']

    # Dynamically find all 'Shift X Duration', 'Break X Duration', and 'Interval X Duration' columns and sort them
    all_columns = daily_report.columns.tolist()
    
    # Separate and sort by type and number
    dynamic_shift_cols = sorted([col for col in all_columns if 'Shift ' in col and 'Duration' in col and 'Total' not in col],
                                key=lambda x: int(x.split(' ')[1]))
    dynamic_break_cols = sorted([col for col in all_columns if 'Break ' in col and 'Duration' in col and 'Total' not in col],
                                key=lambda x: int(x.split(' ')[1]))
    dynamic_general_interval_cols = sorted([col for col in all_columns if 'Interval ' in col and 'Duration' in col and 'Total' not in col],
                                            key=lambda x: int(x.split(' ')[1]))

    # Combine all columns in the desired order
    final_column_order = fixed_cols + dynamic_shift_cols + dynamic_break_cols + dynamic_general_interval_cols
    # Ensure only columns that actually exist in the DataFrame are included in the final order
    final_column_order_existing = [col for col in final_column_order if col in daily_report.columns]

    final_output_df = daily_report[final_column_order_existing]

    return final_output_df, error_log

# --- Function to generate summary report from detailed DataFrame ---
def generate_summary_report(detailed_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generates a summary report from the detailed daily shift DataFrame.

    Args:
        detailed_df (pd.DataFrame): The detailed daily shift report DataFrame.

    Returns:
        pd.DataFrame: The summary report DataFrame.
    """
    if detailed_df.empty:
        return pd.DataFrame()

    # Convert 'Date' to datetime for month operations
    detailed_df['Date'] = pd.to_datetime(detailed_df['Date'])
    detailed_df['Month_Year'] = detailed_df['Date'].dt.strftime('%Y-%m') # Use YYYY-MM for proper sorting
    detailed_df['Month_Name'] = detailed_df['Date'].dt.strftime('%B')

    # Convert Total Shift Duration strings to Timedelta for summation
    def parse_hms_to_timedelta(hms_str):
        if hms_str == '00:00:00' or pd.isna(hms_str):
            return pd.Timedelta(seconds=0)
        # Handle cases where hms_str might not be a string (e.g., if already timedelta from previous step)
        if isinstance(hms_str, pd.Timedelta):
            return hms_str
        h, m, s = map(int, hms_str.split(':'))
        return pd.Timedelta(hours=h, minutes=m, seconds=s)

    detailed_df['Total Shift Duration_td'] = detailed_df['Total Shift Duration'].apply(parse_hms_to_timedelta)

    # Calculate expected working days for each month present in the data
    expected_working_days_map = {}
    for year_month_str in detailed_df['Month_Year'].unique():
        year_num, month_num = map(int, year_month_str.split('-')) # Parse YYYY-MM
        
        cal = calendar.Calendar()
        working_days_count = 0
        for week in cal.monthdayscalendar(year_num, month_num):
            for day_of_week, day_num in enumerate(week):
                # Working days are Sunday (6) to Thursday (3). Weekends are Friday (4) and Saturday (5)
                # calendar.MONDAY=0, TUESDAY=1, WEDNESDAY=2, THURSDAY=3, FRIDAY=4, SATURDAY=5, SUNDAY=6
                if day_num != 0 and day_of_week not in [calendar.FRIDAY, calendar.SATURDAY]: 
                    working_days_count += 1
        expected_working_days_map[year_month_str] = working_days_count

    # Group and aggregate for summary
    summary_grouped = detailed_df.groupby(['Source_Name', 'No.', 'Name', 'Month_Year', 'Month_Name']).agg(
        Total_Worked_Days=('Date', lambda x: x[detailed_df.loc[x.index, 'Total Shift Duration_td'] > pd.Timedelta(seconds=0)].nunique()),
        Total_Shift_Durations_td=('Total Shift Duration_td', 'sum'),
        Count_Single_Punch_Days=('Punch Status', lambda x: (x == "Single Punch (0 Shift Duration)").sum()),
        Count_More_Than_4_Punches_Days=('Original Number of Punches', lambda x: (x > 4).sum())
    ).reset_index()

    # Calculate Total Absent Days
    summary_grouped['Expected_Working_Days'] = summary_grouped['Month_Year'].map(expected_working_days_map)
    summary_grouped['Total_Absent_Days'] = summary_grouped['Expected_Working_Days'] - summary_grouped['Total_Worked_Days']
    summary_grouped['Total_Absent_Days'] = summary_grouped['Total_Absent_Days'].clip(lower=0) # Ensure absent days are not negative

    # Format final Total Shift Durations back to HH:MM:SS string
    summary_grouped['Total Shift Durations'] = summary_grouped['Total_Shift_Durations_td'].apply(format_timedelta_to_hms)

    # Select and reorder columns for the final summary report
    summary_report_cols = [
        'Source_Name', 'Name', 'No.', 'Month_Name',
        'Total_Worked_Days', 'Total_Absent_Days', 'Total Shift Durations', 
        'Count_Single_Punch_Days', 'Count_More_Than_4_Punches_Days'
    ]
    # Ensure Month_Year is sorted for consistent output
    summary_df = summary_grouped.sort_values(by=['No.', 'Month_Year'])[summary_report_cols]

    return summary_df


# --- Streamlit page function for the Fingerprint Report Generator ---
def fingerprint_report_page():
    """
    Displays the fingerprint report generator functionality in Streamlit.
    Allows users to upload multiple CSV/Excel files and download an Excel report.
    """
    st.title("📊 Employee Fingerprint Report Generator")
    st.info("⬆️ Upload one or more CSV or Excel files containing employee fingerprint data.")

    # File uploader to accept multiple CSV/Excel files
    uploaded_files = st.file_uploader(
        "Select fingerprint files (.csv, .xls, .xlsx)",
        type=["csv", "xls", "xlsx"],
        accept_multiple_files=True,
        key="fingerprint_file_uploader" # Unique key for this uploader
    )

    if uploaded_files:
        if st.button("🚀 Generate Reports", type="primary"):
            with st.spinner("Processing files and generating reports... This may take a moment."):
                detailed_report_df, error_log = calculate_shift_durations_from_uploads(uploaded_files)
                
                # Convert error_log list to DataFrame for the error sheet
                error_log_df = pd.DataFrame(error_log)
                if error_log_df.empty:
                    error_log_df = pd.DataFrame([{'Filename': 'N/A', 'Error': 'No errors recorded during file processing.'}])

                if not detailed_report_df.empty:
                    st.success(f"✅ Successfully processed data for {len(detailed_report_df)} daily records!")
                    summary_report_df = generate_summary_report(detailed_report_df.copy()) # Pass a copy

                    # Display previews
                    st.subheader("📋 Detailed Report Preview")
                    st.dataframe(detailed_report_df.head(), use_container_width=True) # Show only head for large reports

                    if not summary_report_df.empty:
                        st.subheader("📈 Summary Report Preview")
                        st.dataframe(summary_report_df.head(), use_container_width=True)
                    else:
                        st.warning("⚠️ Summary Report could not be generated (detailed report might be empty or issues during summary generation).")

                    if not error_log_df.empty:
                        st.subheader("❌ Error Log Preview")
                        st.dataframe(error_log_df, use_container_width=True) # Show full error log

                    # Prepare Excel file for download
                    output_buffer = io.BytesIO()
                    with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                        detailed_report_df.to_excel(writer, sheet_name='Detailed Report', index=False)
                        if not summary_report_df.empty:
                            summary_report_df.to_excel(writer, sheet_name='Summary Report', index=False)
                        error_log_df.to_excel(writer, sheet_name='Error Log', index=False)
                    
                    # Provide download button
                    st.download_button(
                        label="📥 Download All Reports (Excel)",
                        data=output_buffer.getvalue(),
                        file_name="Employee_Punch_Reports.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="secondary"
                    )
                else:
                    st.error("❌ No valid data could be processed from the uploaded files. Please check the file formats and column names.")
                    if not error_log_df.empty:
                        st.subheader("❌ Error Log")
                        st.dataframe(error_log_df, use_container_width=True)
                    st.download_button(
                        label="📥 Download Error Log (Excel)",
                        data=io.BytesIO(pd.DataFrame(error_log).to_excel(index=False).encode('utf-8')).getvalue(),
                        file_name="Error_Log.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="secondary"
                    )

    else:
        st.info("Please upload your fingerprint files to start the report generation.")

