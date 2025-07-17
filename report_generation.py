import pandas as pd
from datetime import date, timedelta

# Import helper functions from config.py
from config import (
    format_timedelta_to_hms,
    get_effective_rules_for_employee_day,
    get_expected_working_days_in_period,
    COMPANY_CONFIGS # Needed to get default standard_shift_hours for rules lookup
)

class ReportGenerator:
    """
    A class to generate summary reports from detailed daily fingerprint data.
    """

    def __init__(self, selected_company_name: str):
        """
        Initializes the ReportGenerator with the selected company's name.

        Args:
            selected_company_name (str): The name of the company selected by the user.
        """
        self.selected_company_name = selected_company_name

    def generate_summary_report(self, detailed_df: pd.DataFrame, global_start_date: date, global_end_date: date) -> pd.DataFrame:
        """
        Generates a summary report from the detailed daily shift DataFrame,
        considering company-specific rules and calculating new KPIs for the GLOBAL reporting period.

        Args:
            detailed_df (pd.DataFrame): The DataFrame containing detailed daily shift data.
            global_start_date (date): The true global minimum date of the dataset.
            global_end_date (date): The true global maximum date of the dataset.

        Returns:
            pd.DataFrame: The generated summary report DataFrame.
        """
        if detailed_df.empty:
            return pd.DataFrame()

        # Ensure all necessary _td columns exist before aggregation
        required_td_cols_map = {
            'Total Shift Duration_td': 'Total Shift Duration',
            'Daily_More_T_Hours_td': 'Daily_More_T_Hours',
            'Daily_Short_T_Hours_td': 'Daily_Short_T_Hours',
            'More_T_postMID_td': 'More_T_postMID'
        }
        for td_col, str_col in required_td_cols_map.items():
            if td_col not in detailed_df.columns:
                if str_col in detailed_df.columns:
                    detailed_df[td_col] = pd.to_timedelta(detailed_df[str_col], errors='coerce').fillna(pd.Timedelta(seconds=0))
                else:
                    detailed_df[td_col] = pd.Timedelta(seconds=0)
            else:
                detailed_df[td_col] = pd.to_timedelta(detailed_df[td_col], errors='coerce').fillna(pd.Timedelta(seconds=0))

        # Ensure boolean flags exist and are boolean type
        required_bool_cols = ['is_more_t_day', 'is_short_t_day']
        for col in required_bool_cols:
            if col not in detailed_df.columns:
                detailed_df[col] = False
            detailed_df[col] = detailed_df[col].astype(bool)

        detailed_df['Date'] = pd.to_datetime(detailed_df['Date'])
        
        # Group by employee (No. and Name) for a single summary row per employee
        # Aggregate Source_Name to show all locations the employee punched at
        summary_grouped = detailed_df.groupby(['No.', 'Name']).agg(
            # Source_Names: aggregate all unique Source_Names for this employee
            Source_Names=('Source_Name', lambda x: ", ".join(x.astype(str).unique())),
            Total_Present_Days=('Date', lambda x: x[detailed_df.loc[x.index, 'Total Shift Duration_td'] > pd.Timedelta(seconds=0)].nunique()),
            Total_Shift_Durations_td=('Total Shift Duration_td', 'sum'),
            Total_More_T_Hours_td=('Daily_More_T_Hours_td', 'sum'),
            Total_Short_T_Hours_td=('Daily_Short_T_Hours_td', 'sum'),
            Total_More_T_postMID_td=('More_T_postMID_td', 'sum'), # Aggregate new column
            Count_Single_Punch_Days=('Punch Status', lambda x: (x == "Single Punch (0 Shift Duration)").sum()),
            Count_More_Than_4_Punches_Days=('Original Number of Punches', lambda x: (x > 4).sum()),
            # New: Count of days with More_T and Short_T
            Count_More_T_Days=('is_more_t_day', 'sum'),
            Count_Short_T_Days=('is_short_t_day', 'sum'),
            # Employee-specific punch date range
            Employee_Punch_Start_Date=('Date', 'min'),
            Employee_Punch_End_Date=('Date', 'max')
        ).reset_index()

        # Add global reporting period and expected days to each row
        summary_grouped['Overall Data Start Date'] = global_start_date.strftime('%Y-%m-%d') # Renamed for clarity
        summary_grouped['Overall Data End Date'] = global_end_date.strftime('%Y-%m-%d')   # Renamed for clarity
        
        # Calculate Total Days in Overall Period
        summary_grouped['Total Days in Overall Period'] = (global_end_date - global_start_date).days + 1 # New column
        
        summary_grouped['Total_Expected_Working_Days_In_Period'] = 0 # Initialize for calculation
        summary_grouped['Total_Absent_Days'] = 0
        summary_grouped['Total_Expected_Weekends_In_Period'] = 0.0 # New: Initialize for expected weekends (float)
        summary_grouped['Total_Employee_Period_OFFs'] = 0.0 # New: Initialize for employee's allowed offs
        summary_grouped['Average Shift Duration'] = '00:00:00' # New: Initialize for average shift duration

        total_days_in_global_period_float = (global_end_date - global_start_date).days + 1.0

        for index, row in summary_grouped.iterrows():
            employee_no = str(row['No.'])
            # Get effective rules for this employee (for is_rotational_off check)
            # We need a source_name for the lookup, so we'll use the first one from aggregated Source_Names
            primary_source_name = row['Source_Names'].split(', ')[0] if ', ' in row['Source_Names'] else row['Source_Names']
            effective_employee_rules = get_effective_rules_for_employee_day(self.selected_company_name, employee_no, primary_source_name)
            
            # Determine exact expected working days (float) based on employee's rules
            expected_working_days_exact = get_expected_working_days_in_period(
                global_start_date, global_end_date, effective_employee_rules
            )
            
            # Round for display in 'Total_Expected_Working_Days_In_Period'
            summary_grouped.loc[index, 'Total_Expected_Working_Days_In_Period'] = int(round(expected_working_days_exact))

            # Calculate Absent Days as total days in period minus present days
            summary_grouped.loc[index, 'Total_Absent_Days'] = summary_grouped.loc[index, 'Total Days in Overall Period'] - row['Total_Present_Days']

            # Calculate Expected Weekends (float) based on total days minus exact working days from rules
            expected_weekends_from_rules = total_days_in_global_period_float - expected_working_days_exact
            
            # Determine the universal minimum expected weekends based on 1 day off per week
            is_employee_rotational = effective_employee_rules.get("is_rotational_off", False)
            
            if is_employee_rotational:
                # For rotational employees, apply the universal minimum based on rotational_days_off_per_week
                universal_minimum_expected_weekends = (total_days_in_global_period_float / 7.0) * effective_employee_rules.get("rotational_days_off_per_week", 1.0)
                final_expected_weekends = max(expected_weekends_from_rules, universal_minimum_expected_weekends)
            else:
                # For non-rotational employees (fixed weekend days), use only the rules-based calculation
                final_expected_weekends = expected_weekends_from_rules

            # Round for display, keeping one decimal for accuracy
            summary_grouped.loc[index, 'Total_Expected_Weekends_In_Period'] = round(final_expected_weekends, 1)

            # Calculate Total_Employee_Period_OFFs
            employee_punch_start_date = row['Employee_Punch_Start_Date'].to_pydatetime().date()
            employee_punch_end_date = row['Employee_Punch_End_Date'].to_pydatetime().date()
            
            total_days_in_employee_punch_period_float = (employee_punch_end_date - employee_punch_start_date).days + 1.0

            expected_working_days_in_employee_period = get_expected_working_days_in_period(
                employee_punch_start_date, employee_punch_end_date, effective_employee_rules
            )
            allowed_offs_in_employee_period = total_days_in_employee_punch_period_float - expected_working_days_in_employee_period
            summary_grouped.loc[index, 'Total_Employee_Period_OFFs'] = round(allowed_offs_in_employee_period, 1)

            # Calculate Average Shift Duration
            if row['Total_Present_Days'] > 0:
                avg_shift_td = row['Total_Shift_Durations_td'] / row['Total_Present_Days']
                summary_grouped.loc[index, 'Average Shift Duration'] = format_timedelta_to_hms(avg_shift_td)
            else:
                summary_grouped.loc[index, 'Average Shift Duration'] = '00:00:00'


        # Format final Timedelta columns back to HH:MM:SS string
        summary_grouped['Total Shift Durations'] = summary_grouped['Total_Shift_Durations_td'].apply(format_timedelta_to_hms)
        summary_grouped['Total More_T Hours'] = summary_grouped['Total_More_T_Hours_td'].apply(format_timedelta_to_hms)
        summary_grouped['Total Short_T Hours'] = summary_grouped['Total_Short_T_Hours_td'].apply(format_timedelta_to_hms)
        summary_grouped['Total More_T_postMID Hours'] = summary_grouped['Total_More_T_postMID_td'].apply(format_timedelta_to_hms)

        # Format the new date columns
        summary_grouped['Employee Punch Start Date'] = summary_grouped['Employee_Punch_Start_Date'].dt.strftime('%Y-%m-%d')
        summary_grouped['Employee Punch End Date'] = summary_grouped['Employee_Punch_End_Date'].dt.strftime('%Y-%m-%d')


        # Select and reorder columns for the final summary report
        summary_report_cols = [
            'No.', 'Name', 'Source_Names',
            'Overall Data Start Date', 'Overall Data End Date',
            'Total Days in Overall Period',
            'Employee Punch Start Date', 'Employee Punch End Date',
            'Total_Expected_Working_Days_In_Period', 'Total_Expected_Weekends_In_Period',
            'Total_Employee_Period_OFFs',
            'Total_Present_Days', 'Total_Absent_Days',
            'Total Shift Durations', 'Average Shift Duration',
            'Total More_T Hours', 'Total Short_T Hours',
            'Total More_T_postMID Hours',
            'Count_More_T_Days', 'Count_Short_T_Days',
            'Count_Single_Punch_Days', 'Count_More_Than_4_Punches_Days'
        ]
        summary_df = summary_grouped[summary_report_cols]

        return summary_df
