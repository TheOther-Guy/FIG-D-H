import pandas as pd
import io
import os
from datetime import timedelta, datetime, date
import streamlit as st # Used for st.session_state.get('debug_mode', False)

# Import configurations and helper functions from config.py
from config import (
    COMPANY_CONFIGS,
    FILE_DATE_FORMATS,
    COLUMN_MAPPING,
    format_timedelta_to_hms,
    get_effective_rules_for_employee_day
)

# Import Second Cup specific logic functions
from second_cup_logic import calculate_24_hour_shifts # Removed calculate_second_cup_shifts

class FingerprintProcessor:
    """
    A dedicated class to process fingerprint data for all companies,
    applying common data cleaning, company-specific date adjustment rules,
    and dispatching to appropriate shift calculation logic.
    """

    def __init__(self, selected_company_name: str):
        """
        Initializes the FingerprintProcessor.

        Args:
            selected_company_name (str): The name of the company selected by the user.
        """
        self.selected_company_name = selected_company_name
        self.global_status_present = False # Track if any uploaded file has a Status column
        self.true_global_min_date = None # Earliest date across all RAW data
        self.true_global_max_date = None # Latest date across all RAW data
        self.error_log = [] # To store any processing errors

    def _process_single_file(self, uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> pd.DataFrame:
        """
        Reads a single uploaded fingerprint file (CSV or Excel),
        adds a 'Source_Name' column, and converts the 'Date/Time' column to datetime objects.
        Handles flexible column names and drops 'Unnamed' columns.

        Args:
            uploaded_file (streamlit.runtime.uploaded_file_manager.UploadedFile):
                The uploaded file object from Streamlit.

        Returns:
            pd.DataFrame: A DataFrame with the processed data.
        """
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        df = pd.DataFrame()

        try:
            if file_extension == '.csv':
                df = pd.read_csv(io.StringIO(uploaded_file.getvalue().decode('utf-8')))
            elif file_extension in ['.xls', '.xlsx']:
                df = pd.read_excel(io.BytesIO(uploaded_file.getvalue()))
            else:
                raise ValueError(f"Unsupported file type for '{uploaded_file.name}'. Only .csv, .xls, and .xlsx are supported.")
        except Exception as e:
            raise ValueError(f"Could not read file '{uploaded_file.name}' (format error or corruption): {e}")

        # Drop any columns that are unnamed (often generated from empty cells in Excel/CSV headers)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]

        # Normalize column names based on COLUMN_MAPPING
        df_columns = df.columns.tolist()
        status_found_for_file = False
        for standard_col, possible_names in COLUMN_MAPPING.items():
            found_match = False
            for name_variant in possible_names:
                if name_variant in df_columns:
                    if standard_col != name_variant:
                        df.rename(columns={name_variant: standard_col}, inplace=True)
                    found_match = True
                    if standard_col == 'Status':
                        status_found_for_file = True
                    break
            if not found_match and standard_col in ['No.', 'Name', 'Date/Time']:
                raise ValueError(f"Missing critical column '{standard_col}' (or its alternatives {possible_names}) in '{uploaded_file.name}'.")
        
        # Update global_status_present if this file has a status column
        if status_found_for_file:
            self.global_status_present = True

        # Extract source name from filename
        filename = uploaded_file.name
        source_name_parts = filename.split('.xlsx - ')
        source_name = source_name_parts[-1].replace(os.path.splitext(source_name_parts[-1])[1], '') if len(source_name_parts) > 1 else os.path.splitext(filename)[0]
        df['Source_Name'] = source_name.strip()

        required_cols_for_processing = ['No.', 'Name', 'Date/Time']
        missing_critical_cols = [col for col in required_cols_for_processing if col not in df.columns]
        if missing_critical_cols:
            raise ValueError(f"Missing critical columns after renaming in '{uploaded_file.name}': {', '.join(missing_critical_cols)}")

        try:
            general_date_formats_to_try = [
                '%d/%m/%Y %I:%M:%S %p', '%d/%m/%Y %I:%M %p',
                '%d-%b-%y %I:%M:%S %p', '%d-%b-%y %I:%M %p',
                '%m/%d/%Y %I:%M:%S %p', '%m/%d/%Y %I:%M %p',
                '%d/%m/%y %I:%M:%S %p', '%d/%m/%y %I:%M %p',
                '%H:%M:%S', '%H:%M',
            ]
            specific_format = FILE_DATE_FORMATS.get(source_name.strip())
            date_formats_for_this_file = []
            if specific_format:
                date_formats_for_this_file.append(specific_format)
            for fmt in general_date_formats_to_try:
                if fmt not in date_formats_for_this_file:
                    date_formats_for_this_file.append(fmt)

            parsed_series = pd.Series(pd.NaT, index=df.index)
            original_datetime_col = df['Date/Time'].copy()
            for fmt in date_formats_for_this_file:
                unparsed_mask = parsed_series.isnull()
                if unparsed_mask.any():
                    parsed_series[unparsed_mask] = pd.to_datetime(original_datetime_col[unparsed_mask], format=fmt, errors='coerce')
                else:
                    break

            df['Date/Time'] = parsed_series
            df.dropna(subset=['Date/Time'], inplace=True)
            if df.empty:
                raise ValueError(f"No valid 'Date/Time' entries in '{uploaded_file.name}' after parsing and cleaning with all formats.")
        except Exception as e:
            raise ValueError(f"Error parsing 'Date/Time' column in '{uploaded_file.name}': {e}. Check date format.")

        if 'Status' not in df.columns:
            df['Status'] = ''
        else:
            df['Status'] = df['Status'].astype(str)
            df['Status'] = df['Status'].replace('nan', '').fillna('')

        return df

    def process_uploaded_files(self, uploaded_files: list) -> pd.DataFrame:
        """
        Processes a list of uploaded Streamlit files, combines them,
        and then applies company-specific date adjustments.

        Args:
            uploaded_files (list): A list of Streamlit UploadedFile objects.

        Returns:
            pd.DataFrame: A combined and initially processed DataFrame with adjusted dates.
        """
        list_of_dfs = []
        self.error_log = [] # Reset error log for new processing run
        self.global_status_present = False # Reset global status flag

        if not uploaded_files:
            self.error_log.append({'Filename': 'N/A', 'Error': 'No files uploaded to process.'})
            return pd.DataFrame()

        for uploaded_file in uploaded_files:
            try:
                df = self._process_single_file(uploaded_file)
                list_of_dfs.append(df)
            except Exception as e:
                error_message = f"Error processing {uploaded_file.name}: {type(e).__name__}: {e}"
                self.error_log.append({'Filename': uploaded_file.name, 'Error': error_message})

        if not list_of_dfs:
            return pd.DataFrame()

        combined_df = pd.concat(list_of_dfs, ignore_index=True)
        # Sort by employee and then by Date/Time (original, unshifted)
        combined_df = combined_df.sort_values(by=['No.', 'Date/Time']).reset_index(drop=True)

        # Store the original Date/Time before any adjustments for reporting and calculations
        combined_df['Original_DateTime'] = combined_df['Date/Time'].copy()

        # Capture global min/max dates from the *ORIGINAL* Date/Time column for reporting
        self.true_global_min_date = combined_df['Original_DateTime'].dt.date.min()
        self.true_global_max_date = combined_df['Original_DateTime'].dt.date.max()

        # --- Company-specific 'Date' assignment (adjusted day for grouping) ---
        # Note: The 'Date' column here defines the logical day for reporting/grouping,
        # while 'Original_DateTime' is used for precise duration calculations.
        if self.selected_company_name == "Second Cup":
            # For Second Cup, the 'Date' column is simply the original calendar date of the punch.
            combined_df['Date'] = combined_df['Original_DateTime'].dt.date
        else:
            # For other companies, apply the existing 1 AM rule for date adjustment
            # This rule shifts punches between 00:00 and 01:00 to the previous calendar day's shift.
            # It should NOT apply to the true global minimum date, as there's no previous day.
            combined_df['Adjusted_Date'] = combined_df['Original_DateTime'].dt.date # Start with original date
            
            # Mask for punches occurring between 00:00 and 00:59:59 (based on ORIGINAL time)
            mask_early_morning_window = (combined_df['Original_DateTime'].dt.hour >= 0) & \
                                        (combined_df['Original_DateTime'].dt.hour < 1) & \
                                        (combined_df['Original_DateTime'].dt.date != self.true_global_min_date)

            # Apply 1 AM rule ONLY to 'C/Out' punches in the early morning
            mask_early_morning_out_punch = mask_early_morning_window & \
                                           (combined_df['Status'].str.contains('C/Out', na=False))
            combined_df.loc[mask_early_morning_out_punch, 'Adjusted_Date'] = combined_df.loc[mask_early_morning_out_punch, 'Adjusted_Date'] - timedelta(days=1)
            combined_df['Date'] = combined_df['Adjusted_Date']
            combined_df.drop(columns=['Adjusted_Date'], inplace=True)

        combined_df['No.'] = combined_df['No.'].astype(str) # Ensure 'No.' is string for consistent grouping

        return combined_df

    def _calculate_non_second_cup_shift_details(self, group: pd.DataFrame, status_column_was_present: bool) -> dict:
        """
        Calculates detailed shift and break durations for non-"Second Cup" companies
        and general Second Cup locations (not 24-hour specific)
        based on punch count, status, and consolidation rules.
        This function now uses 'Original_DateTime' for all time-based calculations.
        """
        group = group.sort_values(by='Original_DateTime').reset_index(drop=True) # Sort by Original_DateTime

        employee_no = str(group['No.'].iloc[0]) # Corrected: Changed 'No' to 'No.'
        employee_name = group['Name'].iloc[0]
        current_date = group['Date'].iloc[0] # This is the adjusted 'Date' for grouping
        source_name = group['Source_Name'].iloc[0]

        effective_rules = get_effective_rules_for_employee_day(self.selected_company_name, employee_no, source_name)

        standard_shift_hours = effective_rules.get("standard_shift_hours", 8)
        short_t_threshold_hours = effective_rules.get("short_t_threshold_hours", 7.5)
        more_t_start_hours = effective_rules.get("more_t_start_hours", 9)
        more_t_enabled = effective_rules.get("more_t_enabled", True) # Default to True if not specified
        fixed_break_deduction_minutes = effective_rules.get("fixed_break_deduction_minutes", 0) # New rule
        fixed_break_threshold_hours = effective_rules.get("fixed_break_threshold_hours", 0) # New rule

        if group.empty:
            return {
                'No.': employee_no, 'Name': employee_name, 'Date': current_date, 'Source_Name': source_name,
                'Original Number of Punches': 0, 'Number of Cleaned Punches': 0,
                'First Punch Time': 'N/A', 'Last Punch Time': 'N/A',
                'Total Shift Duration': '00:00:00', 'Total Break Duration': '00:00:00',
                'Daily_More_T_Hours': '00:00:00', 'Daily_Short_T_Hours': '00:00:00',
                'is_more_t_day': False, 'is_short_t_day': False,
                'Punch Status': 'No valid punches for day', 'More_T_postMID': '00:00:00'
            }

        original_punch_count = len(group)

        # --- Universal Cleaning: Always keep first and last punch, apply 10-min consolidation for others ---
        consolidated_punches_list = []
        if not group.empty:
            consolidated_punches_list.append(group.iloc[0])
            for i in range(1, original_punch_count - 1):
                current_punch = group.iloc[i]
                last_kept_punch = consolidated_punches_list[-1]
                # Use Original_DateTime for consolidation logic
                if (current_punch['Original_DateTime'] - last_kept_punch['Original_DateTime']) > pd.Timedelta(minutes=10) or \
                   (status_column_was_present and current_punch['Status'] != last_kept_punch['Status']):
                    consolidated_punches_list.append(current_punch)
            
            if original_punch_count > 1 and \
               (group.iloc[-1]['Original_DateTime'] != consolidated_punches_list[-1]['Original_DateTime'] or \
               (status_column_was_present and group.iloc[-1]['Status'] != consolidated_punches_list[-1]['Status'])):
                consolidated_punches_list.append(group.iloc[-1])
            if original_punch_count > 1 and len(consolidated_punches_list) == 1:
                consolidated_punches_list.append(group.iloc[-1])

        cleaned_group = pd.DataFrame(consolidated_punches_list)
        cleaned_punch_count = len(cleaned_group)

        total_shift_duration = pd.Timedelta(seconds=0)
        total_break_duration = pd.Timedelta(seconds=0)
        punch_status = "N/A"
        individual_interval_details = []
        has_inferred_shifts_breaks_pattern = False 

        first_punch_time_formatted = 'N/A'
        last_punch_time_formatted = 'N/A'

        if not group.empty:
            first_punch_time_formatted = group.iloc[0]['Original_DateTime'].strftime('%I:%M:%S %p')
            last_punch_time_formatted = group.iloc[-1]['Original_DateTime'].strftime('%I:%M:%S %p')

        if cleaned_punch_count == 0:
            punch_status = "No valid punches for day"
            
        elif cleaned_punch_count == 1:
            punch_status = "Single Punch (0 Shift Duration)"

        elif cleaned_punch_count >= 2:
            is_status_alternating_useful = False
            if status_column_was_present and cleaned_punch_count >= 2:
                if any(cleaned_group.iloc[i]['Status'] != cleaned_group.iloc[i+1]['Status'] for i in range(len(cleaned_group) - 1)):
                    is_status_alternating_useful = True
            
            if is_status_alternating_useful:
                if cleaned_punch_count == 4 and \
                   cleaned_group.iloc[0]['Status'] == 'C/In' and \
                   cleaned_group.iloc[1]['Status'] == 'C/Out' and \
                   cleaned_group.iloc[2]['Status'] == 'C/In' and \
                   cleaned_group.iloc[3]['Status'] == 'C/Out':
                    
                    shift1 = cleaned_group.iloc[1]['Original_DateTime'] - cleaned_group.iloc[0]['Original_DateTime'] # Use Original_DateTime
                    break1 = cleaned_group.iloc[2]['Original_DateTime'] - cleaned_group.iloc[1]['Original_DateTime'] # Use Original_DateTime
                    shift2 = cleaned_group.iloc[3]['Original_DateTime'] - cleaned_group.iloc[2]['Original_DateTime'] # Use Original_DateTime
                    
                    total_shift_duration = shift1 + shift2
                    total_break_duration = break1
                    punch_status = "Two Shifts with One Break (4 Punches, Status Matched)"
                    individual_interval_details.append({'type': 'Shift', 'duration': shift1})
                    individual_interval_details.append({'type': 'Break', 'duration': break1})
                    individual_interval_details.append({'type': 'Shift', 'duration': shift2})
                    has_inferred_shifts_breaks_pattern = True
                else:
                    for i in range(len(cleaned_group) - 1):
                        interval = cleaned_group.iloc[i+1]['Original_DateTime'] - cleaned_group.iloc[i]['Original_DateTime'] # Use Original_DateTime
                        current_status = cleaned_group.iloc[i]['Status']
                        next_status = cleaned_group.iloc[i+1]['Status']

                        if 'C/In' in current_status and 'C/Out' in next_status:
                            individual_interval_details.append({'type': 'Shift', 'duration': interval})
                        elif 'C/Out' in current_status and 'C/In' in next_status:
                            individual_interval_details.append({'type': 'Break', 'duration': interval})
                        else:
                            individual_interval_details.append({'type': 'General', 'duration': interval})
                    
                    for item in individual_interval_details:
                        if item['type'] == 'Shift':
                            total_shift_duration += item['duration']
                        elif item['type'] == 'Break':
                            total_break_duration += item['duration']
                    
                    if total_shift_duration > pd.Timedelta(seconds=0) or total_break_duration > pd.Timedelta(seconds=0):
                        punch_status = f"Complex Pattern ({cleaned_punch_count} Cleaned Punches with Status, Inferred Intervals)"
                        has_inferred_shifts_breaks_pattern = True
            
            if not has_inferred_shifts_breaks_pattern and cleaned_punch_count >= 4:
                inferred_shift1 = cleaned_group.iloc[1]['Original_DateTime'] - cleaned_group.iloc[0]['Original_DateTime'] # Use Original_DateTime
                inferred_break1 = cleaned_group.iloc[2]['Original_DateTime'] - cleaned_group.iloc[1]['Original_DateTime'] # Use Original_DateTime
                inferred_shift2 = cleaned_group.iloc[3]['Original_DateTime'] - cleaned_group.iloc[2]['Original_DateTime'] # Use Original_DateTime

                total_shift_duration = inferred_shift1 + inferred_shift2
                total_break_duration = inferred_break1
                punch_status = f"Inferred Two Shifts with One Break ({cleaned_punch_count} Cleaned Punches, Consistent Status/No Status Data)"
                
                individual_interval_details = []
                individual_interval_details.append({'type': 'Shift', 'duration': inferred_shift1})
                individual_interval_details.append({'type': 'Break', 'duration': inferred_break1})
                individual_interval_details.append({'type': 'Shift', 'duration': inferred_shift2})
                
                if cleaned_punch_count > 4:
                    punch_status += " (+ additional punches beyond 4th)"
                    for i in range(3, cleaned_punch_count - 1): 
                        interval = cleaned_group.iloc[i+1]['Original_DateTime'] - cleaned_group.iloc[i]['Original_DateTime'] # Use Original_DateTime
                        individual_interval_details.append({'type': 'General', 'duration': interval})
                
                has_inferred_shifts_breaks_pattern = True

            if not has_inferred_shifts_breaks_pattern:
                total_shift_duration = cleaned_group.iloc[-1]['Original_DateTime'] - cleaned_group.iloc[0]['Original_DateTime'] # Use Original_DateTime
                total_break_duration = pd.Timedelta(seconds=0)
                punch_status = f"Total Presence ({cleaned_punch_count} Cleaned Punches, No Inferred Breaks/Unclear Patterns)"
                individual_interval_details = []
                individual_interval_details.append({'type': 'Total Presence', 'duration': total_shift_duration})

        if fixed_break_deduction_minutes > 0 and \
           total_shift_duration.total_seconds() / 3600.0 >= fixed_break_threshold_hours and \
           total_break_duration == pd.Timedelta(seconds=0) and \
           cleaned_punch_count >= 2:
            
            deducted_break_td = pd.Timedelta(minutes=fixed_break_deduction_minutes)
            
            if total_shift_duration > deducted_break_td:
                total_shift_duration -= deducted_break_td
                total_break_duration += deducted_break_td
                punch_status += " (Fixed Break Deducted)"
            else:
                total_break_duration += total_shift_duration
                total_shift_duration = pd.Timedelta(seconds=0)
                punch_status += " (Fixed Break Deducted, Shift Zeroed)"

        daily_more_t_td = pd.Timedelta(seconds=0)
        daily_short_t_td = pd.Timedelta(seconds=0)
        is_more_t_day = False
        is_short_t_day = False

        total_shift_hours = total_shift_duration.total_seconds() / 3600.0

        if more_t_enabled:
            if total_shift_hours > more_t_start_hours:
                daily_more_t_td = pd.Timedelta(hours=total_shift_hours - more_t_start_hours)
                if daily_more_t_td > pd.Timedelta(seconds=0):
                    is_more_t_day = True
        
        if total_shift_hours < short_t_threshold_hours and total_shift_hours > 0:
            daily_short_t_td = pd.Timedelta(hours=short_t_threshold_hours - total_shift_hours)
            if daily_short_t_td > pd.Timedelta(seconds=0):
                is_short_t_day = True

        intervals_output_dict = {}
        shift_col_count = 0
        break_col_count = 0
        general_col_count = 0

        if individual_interval_details:
            for item in individual_interval_details:
                if item['type'] == 'Shift':
                    shift_col_count += 1
                    intervals_output_dict[f'Shift {shift_col_count} Duration'] = format_timedelta_to_hms(item['duration'])
                elif item['type'] == 'Break':
                    break_col_count += 1
                    intervals_output_dict[f'Break {break_col_count} Duration'] = format_timedelta_to_hms(item['duration'])
                else:
                    general_col_count += 1
                    intervals_output_dict[f'Interval {general_col_count} Duration'] = format_timedelta_to_hms(item['duration'])

        return_data = {
            'No.': employee_no, 'Name': employee_name, 'Date': current_date, 'Source_Name': source_name,
            'Original Number of Punches': original_punch_count,
            'Number of Cleaned Punches': cleaned_punch_count,
            'First Punch Time': first_punch_time_formatted, 'Last Punch Time': last_punch_time_formatted,
            'Total Shift Duration': format_timedelta_to_hms(total_shift_duration),
            'Total Break Duration': format_timedelta_to_hms(total_break_duration),
            'Daily_More_T_Hours': format_timedelta_to_hms(daily_more_t_td),
            'Daily_Short_T_Hours': format_timedelta_to_hms(daily_short_t_td),
            'is_more_t_day': is_more_t_day, 'is_short_t_day': is_short_t_day,
            'Punch Status': punch_status, 'More_T_postMID': '00:00:00'
        }
        return_data.update(intervals_output_dict)

        if st.session_state.get('debug_mode', False):
            st.write(f"DEBUG (Non-Second Cup Shift Details): Employee {employee_no}, Date {current_date}")
            st.write(f"  Original Punches: {original_punch_count}")
            st.write(f"  Cleaned Punches: {cleaned_punch_count}")
            if not cleaned_group.empty:
                st.write(f"  Cleaned Group Original_DateTime:\n{cleaned_group['Original_DateTime'].to_string()}")
            st.write(f"  Calculated Total Shift Duration: {total_shift_duration}")
            st.write(f"  Calculated Total Break Duration: {total_break_duration}")
            st.write(f"  Punch Status: {punch_status}")
        
        return return_data

    def calculate_daily_reports(self, combined_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates detailed daily reports from the combined and initially processed DataFrame
        using company-specific shift calculation logic.
        """
        daily_report_list = []
        if combined_df.empty:
            return pd.DataFrame()

        grouping_cols = ['No.', 'Name', 'Date']
        if not all(col in combined_df.columns for col in grouping_cols):
            missing = [col for col in grouping_cols if col not in combined_df.columns]
            self.error_log.append({'Filename': 'Combined Data', 'Error': f"Cannot group data: Missing one or more grouping columns ({', '.join(missing)})."})
            return pd.DataFrame()

        # Process employee by employee to handle chaining correctly
        for emp_no, emp_group_full in combined_df.groupby('No.'):
            # Ensure the full employee group is sorted by Original_DateTime for sequential processing
            emp_group_full_sorted = emp_group_full.sort_values(by='Original_DateTime').reset_index(drop=True)
            
            # Get effective rules for the current employee's primary location
            # Assuming the first Source_Name in the sorted group is representative for rules lookup
            # This might need refinement if an employee works across multiple locations with different rules daily.
            # For simplicity, we'll use the Source_Name of the first punch in the group.
            primary_source_name = emp_group_full_sorted['Source_Name'].iloc[0]
            effective_rules = get_effective_rules_for_employee_day(self.selected_company_name, emp_no, primary_source_name)

            is_24_hour_location = effective_rules.get("is_24_hour_location", False)

            # Apply the specific 24-hour Second Cup logic ONLY if all conditions are met
            if self.selected_company_name == "Second Cup" and is_24_hour_location:
                daily_report_list.extend(calculate_24_hour_shifts(emp_group_full_sorted, emp_no, self.selected_company_name))
            else:
                # For ALL other companies AND general Second Cup locations (non-24hr),
                # use the global shift calculation logic.
                unique_adjusted_dates = emp_group_full_sorted['Date'].unique()
                for current_adjusted_date in sorted(unique_adjusted_dates):
                    daily_group_for_current_date = emp_group_full_sorted[emp_group_full_sorted['Date'] == current_adjusted_date].copy()
                    detailed_info = self._calculate_non_second_cup_shift_details(
                        daily_group_for_current_date, 
                        self.global_status_present # Pass the global status flag
                    )
                    daily_report_list.append(detailed_info)

        daily_report = pd.DataFrame(daily_report_list)

        # Define all fixed columns that should always be present
        fixed_cols = ['Source_Name', 'No.', 'Name', 'Date', 
                      'Original Number of Punches', 'Number of Cleaned Punches',
                      'First Punch Time', 'Last Punch Time',
                      'Total Shift Duration', 'Total Break Duration',
                      'Daily_More_T_Hours', 'Daily_Short_T_Hours',
                      'is_more_t_day', 'is_short_t_day',
                      'More_T_postMID',
                      'Punch Status']
        
        # Reindex to ensure all fixed columns are present, filling missing with NaN
        daily_report = daily_report.reindex(columns=daily_report.columns.union(fixed_cols, sort=False))


        for col in daily_report.columns:
            if 'Duration' in col or 'Hours' in col or 'More_T_postMID' in col:
                daily_report[col] = daily_report[col].fillna('00:00:00')
            elif 'is_more_t_day' in col or 'is_short_t_day' in col:
                 daily_report[col] = daily_report[col].fillna(False)
            elif col in ['First Punch Time', 'Last Punch Time', 'Punch Status']:
                daily_report[col] = daily_report[col].fillna('N/A')
            elif col in ['Original Number of Punches', 'Number of Cleaned Punches']:
                daily_report[col] = daily_report[col].fillna(0).astype(int)

        # Calculate and attribute More_T_postMID
        # This calculation uses Original_DateTime for consistency
        daily_report['Last Punch Time_dt'] = daily_report.apply(
            lambda row: datetime.strptime(f"{row['Date'].strftime('%Y-%m-%d')} {row['Last Punch Time']}", '%Y-%m-%d %I:%M:%S %p')
            if row['Last Punch Time'] != 'N/A' else pd.NaT, axis=1
        )
        
        temp_next_day_first_punch = combined_df.copy()
        # Use Original_DateTime for grouping to find the next day's first punch
        temp_next_day_first_punch['Date_Original'] = temp_next_day_first_punch['Original_DateTime'].dt.date
        temp_next_day_first_punch = temp_next_day_first_punch.groupby(['No.', 'Date_Original'])['Original_DateTime'].min().reset_index()
        temp_next_day_first_punch.rename(columns={'Original_DateTime': 'Next_Day_First_Punch_Time'}, inplace=True)

        daily_report['Next_Day_Date'] = daily_report['Date'] + timedelta(days=1)
        daily_report['No.'] = daily_report['No.'].astype(str)

        daily_report = daily_report.merge(
            temp_next_day_first_punch,
            left_on=['No.', 'Next_Day_Date'],
            right_on=['No.', 'Date_Original'], # Join on the original date of the next day's first punch
            how='left',
            suffixes=('', '_next')
        )
        # Fix: Drop 'Date_Original' instead of 'Date_Original_next' as suffixes don't apply here
        daily_report.drop(columns=['Date_Original'], inplace=True, errors='ignore') 

        daily_report['More_T_postMID_td'] = pd.Timedelta(seconds=0)

        for index, row in daily_report.iterrows():
            last_punch_time = row['Last Punch Time_dt']
            next_day_first_punch_time = row['Next_Day_First_Punch_Time']
            current_report_date = row['Date'] # This is the adjusted report date

            if pd.isna(last_punch_time) or pd.isna(next_day_first_punch_time):
                continue

            # Check if the next day's first punch is indeed on the next calendar day and within the 00:00-01:00 window
            # This is based on the *original* calendar time of the punch.
            if next_day_first_punch_time.date() == (current_report_date + timedelta(days=1)) and \
               next_day_first_punch_time.hour >= 0 and next_day_first_punch_time.hour < 1:
                
                midnight_next_day = datetime.combine(current_report_date + timedelta(days=1), datetime.min.time())
                duration_post_midnight = next_day_first_punch_time - midnight_next_day
                daily_report.loc[index, 'More_T_postMID_td'] = duration_post_midnight

        daily_report.drop(columns=['Last Punch Time_dt', 'Next_Day_Date', 'Next_Day_First_Punch_Time'], inplace=True)
        daily_report['More_T_postMID'] = daily_report['More_T_postMID_td'].apply(format_timedelta_to_hms)

        final_output_df = daily_report.copy()
        final_output_df['Total Shift Duration_td'] = final_output_df['Total Shift Duration'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else x)
        final_output_df['Daily_More_T_Hours_td'] = final_output_df['Daily_More_T_Hours'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else x)
        final_output_df['Daily_Short_T_Hours_td'] = final_output_df['Daily_Short_T_Hours'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else x)
        final_output_df['More_T_postMID_td'] = final_output_df['More_T_postMID'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else x)

        # Use only fixed_cols for the final column order, ensuring no dynamic interval columns appear
        final_output_df = final_output_df[fixed_cols].copy()
        # Ensure Original_DateTime is dropped at the very end from the final output DataFrame
        final_output_df.drop(columns=['Original_DateTime'], inplace=True, errors='ignore') 

        return final_output_df

    def get_error_log(self) -> list:
        """Returns the accumulated error log."""
        return self.error_log

    def get_global_dates(self) -> tuple[date, date]:
        """Returns the true global min and max dates of the dataset."""
        return self.true_global_min_date, self.true_global_max_date
