import pandas as pd
from datetime import date, timedelta, datetime

# Import configurations and helper functions from config.py
from config import (
    COMPANY_CONFIGS,
    format_timedelta_to_hms,
    get_effective_rules_for_employee_day
)

def analyze_consecutive_absences(detailed_df: pd.DataFrame, summary_df: pd.DataFrame, global_start_date: date, global_end_date: date) -> pd.DataFrame:
    """
    Analyzes detailed daily report to find consecutive absent days for each employee.
    Includes the total absent days from the summary report, and now, ALL absent dates.
    Now uses global_start_date and global_end_date for a consistent period.

    Args:
        detailed_df (pd.DataFrame): The DataFrame containing detailed daily shift data.
        summary_df (pd.DataFrame): The summary report DataFrame.
        global_start_date (date): The true global minimum date of the dataset.
        global_end_date (date): The true global maximum date of the dataset.

    Returns:
        pd.DataFrame: A DataFrame summarizing consecutive absences.
    """
    if detailed_df.empty or summary_df.empty or global_start_date is None or global_end_date is None:
        return pd.DataFrame(columns=['No.', 'Name', 'Source_Names', 
                                     'Longest Consecutive Absences (Days)', 'Absence Start Date', 'Absence End Date', 
                                     'Total Absent Days', 'All Absent Dates']) 

    df = detailed_df.copy()

    # Ensure all necessary _td columns exist and are of timedelta type
    required_td_cols_map = {
        'Total Shift Duration_td': 'Total Shift Duration',
    }
    for td_col, str_col in required_td_cols_map.items():
        if td_col not in df.columns:
            if str_col in df.columns:
                df[td_col] = pd.to_timedelta(df[str_col], errors='coerce').fillna(pd.Timedelta(seconds=0))
            else:
                df[td_col] = pd.Timedelta(seconds=0)
        else:
            df[td_col] = pd.to_timedelta(df[td_col], errors='coerce').fillna(pd.Timedelta(seconds=0))

    # Ensure 'Date' is datetime and sort
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values(by=['No.', 'Date'])

    absent_summary = []

    # Merge summary_df to get Total_Absent_Days
    summary_df['No.'] = summary_df['No.'].astype(str)
    summary_for_merge = summary_df[['No.', 'Total_Absent_Days']].copy()

    for (emp_no, emp_name), group in df.groupby(['No.', 'Name']):
        # Create a full date range for the employee based on the GLOBAL data period
        full_date_range = pd.date_range(start=global_start_date, end=global_end_date, freq='D')
        
        # Initialize attendance series for the global range
        attendance_series = pd.Series(False, index=full_date_range) # False means absent initially

        # Mark dates where employee was present in the detailed_df
        present_dates = group[group['Total Shift Duration_td'] > pd.Timedelta(seconds=0)]['Date'].dt.normalize().unique()
        
        # Ensure present_dates are within the full_date_range index before assigning
        present_dates_in_range = [d for d in present_dates if d in attendance_series.index]
        attendance_series.loc[present_dates_in_range] = True # True means present

        # Identify all absent dates within the global range
        all_absent_dates_list = [d.strftime('%Y-%m-%d') for d in attendance_series.index if not attendance_series.loc[d]]
        formatted_all_absent_dates = ", ".join(all_absent_dates_list)

        # Identify longest consecutive absent streak within the global range
        longest_streak = 0
        current_streak = 0
        streak_start_date = None
        longest_streak_start_date = None
        longest_streak_end_date = None
        
        for current_date in attendance_series.index:
            if not attendance_series.loc[current_date]: # If absent
                current_streak += 1
                if streak_start_date is None:
                    streak_start_date = current_date
            else: # If present, reset streak
                if current_streak > longest_streak:
                    longest_streak = current_streak
                    longest_streak_start_date = streak_start_date
                    longest_streak_end_date = current_date - timedelta(days=1)
                current_streak = 0
                streak_start_date = None
        
        # Check for streak at the very end of the global period
        if current_streak > longest_streak:
            longest_streak = current_streak
            longest_streak_start_date = streak_start_date
            longest_streak_end_date = global_end_date # Streak extends to end of global data

        # Only add to summary if there's any absence or presence record for the employee in the overall period
        if longest_streak > 0 or len(all_absent_dates_list) > 0: 
            total_absent_days_for_employee = summary_for_merge[summary_for_merge['No.'] == str(emp_no)]['Total_Absent_Days'].iloc[0] if not summary_for_merge[summary_for_merge['No.'] == str(emp_no)].empty else 0
            
            absent_summary.append({
                'No.': emp_no,
                'Name': emp_name,
                'Source_Names': ", ".join(group['Source_Name'].astype(str).unique()),
                'Longest Consecutive Absences (Days)': longest_streak,
                'Absence Start Date': longest_streak_start_date.strftime('%Y-%m-%d') if longest_streak_start_date else 'N/A',
                'Absence End Date': longest_streak_end_date.strftime('%Y-%m-%d') if longest_streak_end_date else 'N/A',
                'Total Absent Days': total_absent_days_for_employee,
                'All Absent Dates': formatted_all_absent_dates
            })
    return pd.DataFrame(absent_summary)


def analyze_unusual_shift_durations(detailed_df: pd.DataFrame, selected_company_name: str) -> pd.DataFrame:
    """
    Analyzes detailed daily report to find shifts significantly shorter or longer than standard.
    Flags shifts outside a configurable percentage deviation from standard.

    Args:
        detailed_df (pd.DataFrame): The DataFrame containing detailed daily shift data.
        selected_company_name (str): The name of the company selected by the user.

    Returns:
        pd.DataFrame: A DataFrame summarizing unusual shift durations.
    """
    if detailed_df.empty:
        return pd.DataFrame(columns=['No.', 'Name', 'Date', 'Source_Name', 'Shift Duration', 'Standard Hours', 'Deviation (%)', 'Anomaly Type'])

    df = detailed_df.copy()
    
    # Ensure all necessary _td columns exist and are of timedelta type
    required_td_cols_map = {
        'Total Shift Duration_td': 'Total Shift Duration',
    }
    for td_col, str_col in required_td_cols_map.items():
        if td_col not in df.columns:
            if str_col in df.columns:
                df[td_col] = pd.to_timedelta(df[str_col], errors='coerce').fillna(pd.Timedelta(seconds=0))
            else:
                df[td_col] = pd.Timedelta(seconds=0)
        else:
            df[td_col] = pd.to_timedelta(df[td_col], errors='coerce').fillna(pd.Timedelta(seconds=0))

    df['Date'] = pd.to_datetime(df['Date'])
    df['Shift_Duration_Hours'] = df['Total Shift Duration_td'].dt.total_seconds() / 3600.0

    anomalies = []
    
    default_standard_shift_hours = COMPANY_CONFIGS.get(selected_company_name, {}).get("default_rules", {}).get("standard_shift_hours", 8)

    for index, row in df.iterrows():
        employee_no = str(row['No.'])
        source_name = row['Source_Name']
        effective_rules = get_effective_rules_for_employee_day(selected_company_name, employee_no, source_name)
        standard_shift_hours = effective_rules.get("standard_shift_hours", default_standard_shift_hours)

        shift_duration_hours = row['Shift_Duration_Hours']
        
        if shift_duration_hours > 0:
            deviation = ((shift_duration_hours - standard_shift_hours) / standard_shift_hours) * 100
            
            long_shift_threshold_pct = 25
            short_shift_threshold_pct = -25

            anomaly_type = None
            if deviation > long_shift_threshold_pct:
                anomaly_type = "Unusually Long Shift"
            elif deviation < short_shift_threshold_pct:
                anomaly_type = "Unusually Short Shift"
            
            if anomaly_type:
                anomalies.append({
                    'No.': employee_no,
                    'Name': row['Name'],
                    'Date': row['Date'].strftime('%Y-%m-%d'),
                    'Source_Name': row['Source_Name'],
                    'Shift Duration (HH:MM:SS)': row['Total Shift Duration'],
                    'Standard Hours': standard_shift_hours,
                    'Deviation (%)': f"{deviation:.2f}%",
                    'Anomaly Type': anomaly_type
                })
    return pd.DataFrame(anomalies)


def generate_location_summary(detailed_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates key metrics by Source_Name (Location) directly from the detailed_df.

    Args:
        detailed_df (pd.DataFrame): The DataFrame containing detailed daily shift data.

    Returns:
        pd.DataFrame: A DataFrame summarizing metrics per location.
    """
    if detailed_df.empty:
        return pd.DataFrame()

    df = detailed_df.copy()
    # Ensure all necessary _td columns exist and are of timedelta type
    required_td_cols_map = {
        'Total Shift Duration_td': 'Total Shift Duration',
        'Daily_More_T_Hours_td': 'Daily_More_T_Hours',
        'Daily_Short_T_Hours_td': 'Daily_Short_T_Hours'
    }
    for td_col, str_col in required_td_cols_map.items():
        if td_col not in df.columns:
            if str_col in df.columns:
                df[td_col] = pd.to_timedelta(df[str_col], errors='coerce').fillna(pd.Timedelta(seconds=0))
            else:
                df[td_col] = pd.Timedelta(seconds=0)
        else:
            df[td_col] = pd.to_timedelta(df[td_col], errors='coerce').fillna(pd.Timedelta(seconds=0))

    location_summary = df.groupby('Source_Name').agg(
        Total_Employees=('No.', 'nunique'),
        Total_Location_Punch_Days=('Date', 'nunique'),
        Total_Original_Punches=('Original Number of Punches', 'sum'),
        Total_Shift_Duration_Location_TD=('Total Shift Duration_td', 'sum'),
        Total_More_T_Location_TD=('Daily_More_T_Hours_td', 'sum'),
        Total_Short_T_Location_TD=('Daily_Short_T_Hours_td', 'sum'),
        Total_Single_Punch_Days_Location=('Punch Status', lambda x: (x == "Single Punch (0 Shift Duration)").sum()),
        Total_More_Than_4_Punches_Days_Location=('Original Number of Punches', lambda x: (x > 4).sum()),
    ).reset_index()

    location_summary['Single_Punch_Rate_Per_100_Punches'] = location_summary.apply(
        lambda row: (row['Total_Single_Punch_Days_Location'] / row['Total_Original_Punches']) * 100 if row['Total_Original_Punches'] > 0 else 0,
        axis=1
    )
    location_summary['Multi_Punch_Rate_Per_100_Punches'] = location_summary.apply(
        lambda row: (row['Total_More_Than_4_Punches_Days_Location'] / row['Total_Original_Punches']) * 100 if row['Total_Original_Punches'] > 0 else 0,
        axis=1
    )

    location_summary['Total Shift Duration (Location)'] = location_summary['Total_Shift_Duration_Location_TD'].apply(format_timedelta_to_hms)
    location_summary['Total More_T Hours (Location)'] = location_summary['Total_More_T_Location_TD'].apply(format_timedelta_to_hms)
    location_summary['Total Short_T Hours (Location)'] = location_summary['Total_Short_T_Location_TD'].apply(format_timedelta_to_hms)

    location_summary['Avg Shift Duration Per Employee (Location)'] = location_summary.apply(
        lambda row: format_timedelta_to_hms(row['Total_Shift_Duration_Location_TD'] / row['Total_Location_Punch_Days']) if row['Total_Location_Punch_Days'] > 0 else '00:00:00',
        axis=1
    )

    location_summary = location_summary[[
        'Source_Name', 'Total_Employees', 'Total_Location_Punch_Days', 'Total_Original_Punches',
        'Total Shift Duration (Location)', 'Avg Shift Duration Per Employee (Location)',
        'Total More_T Hours (Location)', 'Total Short_T Hours (Location)',
        'Total_Single_Punch_Days_Location', 'Single_Punch_Rate_Per_100_Punches',
        'Total_More_Than_4_Punches_Days_Location', 'Multi_Punch_Rate_Per_100_Punches'
    ]]
    return location_summary

def calculate_location_absenteeism_rates(summary_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates absenteeism rate per location based on employee summaries.
    Assumes each employee's 'Source_Names' first entry is their primary location.
    The rate is now based on 'Total Days in Overall Period' (all days in the period),
    not just expected working days, as 'Absent Days' is now defined as days without punches.

    Args:
        summary_df (pd.DataFrame): The summary report DataFrame.

    Returns:
        pd.DataFrame: A DataFrame with absenteeism rates per location.
    """
    if summary_df.empty:
        return pd.DataFrame(columns=['Source_Name', 'Total_Period_Days_Location_Agg', 'Total_Absent_Days_Location_Agg', 'Absenteeism_Rate_Location'])

    emp_location_data = summary_df.copy()
    emp_location_data['Primary_Location'] = emp_location_data['Source_Names'].apply(lambda x: x.split(', ')[0] if x else 'N/A')

    location_absenteeism = emp_location_data.groupby('Primary_Location').agg(
        Total_Period_Days_Location_Agg=('Total Days in Overall Period', 'sum'),
        Total_Absent_Days_Location_Agg=('Total_Absent_Days', 'sum')
    ).reset_index().rename(columns={'Primary_Location': 'Source_Name'})

    location_absenteeism['Absenteeism_Rate_Location'] = location_absenteeism.apply(
        lambda row: (row['Total_Absent_Days_Location_Agg'] / row['Total_Period_Days_Location_Agg']) * 100 if row['Total_Period_Days_Location_Agg'] > 0 else 0,
        axis=1
    )
    return location_absenteeism[['Source_Name', 'Absenteeism_Rate_Location']]


def calculate_top_locations_by_metric(location_overview_df: pd.DataFrame, metric_col: str, higher_is_worse: bool = True) -> str:
    """
    Identifies the top location for a given metric.

    Args:
        location_overview_df (pd.DataFrame): The location overview DataFrame.
        metric_col (str): The column name of the metric to analyze.
        higher_is_worse (bool): True if a higher value for the metric is worse, False otherwise.

    Returns:
        str: A formatted string indicating the top location and its value for the metric.
    """
    if location_overview_df.empty or metric_col not in location_overview_df.columns:
        return "N/A"

    if 'Rate' in metric_col:
        if higher_is_worse:
            top_location_row = location_overview_df.loc[location_overview_df[metric_col].idxmax()]
        else:
            top_location_row = location_overview_df.loc[location_overview_df[metric_col].idxmin()]
        
        value = top_location_row[metric_col]
        return f"{top_location_row['Source_Name']} ({value:.2f}%)"
    
    elif 'Hours' in metric_col:
        temp_td_series = location_overview_df[metric_col].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else pd.NaT)
        
        if higher_is_worse:
            top_location_row = location_overview_df.loc[temp_td_series.dt.total_seconds().idxmax()]
        else:
            top_location_row = location_overview_df.loc[temp_td_series.dt.total_seconds().idxmin()]
            
        value_hours = pd.to_timedelta(top_location_row[metric_col]).total_seconds() / 3600
        return f"{top_location_row['Source_Name']} ({value_hours:.1f} hours)"
    
    elif metric_col == 'Total_Employees':
        top_location_row = location_overview_df.loc[location_overview_df[metric_col].idxmax()]
        return f"{top_location_row['Source_Name']} ({int(top_location_row[metric_col])} employees)"

    return "N/A"

def analyze_employee_vs_location_averages(summary_df: pd.DataFrame, location_summary_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compares individual employee metrics against their primary location's averages.

    Args:
        summary_df (pd.DataFrame): The summary report DataFrame.
        location_summary_df (pd.DataFrame): The location summary DataFrame.

    Returns:
        pd.DataFrame: A DataFrame comparing employee metrics to location averages.
    """
    if summary_df.empty or location_summary_df.empty:
        return pd.DataFrame(columns=['No.', 'Name', 'Primary Location', 
                                     'Employee Present Days', 'Location Avg Present Days', 'Present Days Deviation',
                                     'Employee Avg Shift Duration', 'Location Avg Shift Duration', 'Avg Shift Deviation',
                                     'Employee Total More_T Hours (H)', 'Location Avg More_T Hours (H)', 'More_T Hours Deviation',
                                     'Employee Total Short_T Hours (H)', 'Location Avg Short_T Hours (H)', 'Short_T Hours Deviation'])

    comparison_data = []

    location_avg_map = {}
    for _, loc_row in location_summary_df.iterrows():
        avg_shift_td = pd.to_timedelta(loc_row['Avg Shift Duration Per Employee (Location)'])
        total_more_t_td = pd.to_timedelta(loc_row['Total More_T Hours (Location)'])
        total_short_t_td = pd.to_timedelta(loc_row['Total Short_T Hours (Location)'])

        loc_total_employees = loc_row['Total_Employees']
        loc_total_present_days = loc_row['Total_Location_Punch_Days']
        avg_present_days_loc = loc_total_present_days / loc_total_employees if loc_total_employees > 0 else 0


        location_avg_map[loc_row['Source_Name']] = {
            'Avg_Present_Days': avg_present_days_loc,
            'Avg_Shift_Duration_td': avg_shift_td,
            'Total_More_T_Hours_td': total_more_t_td,
            'Total_Short_T_Hours_td': total_short_t_td
        }

    for _, emp_row in summary_df.iterrows():
        employee_no = emp_row['No.']
        employee_name = emp_row['Name']
        
        primary_location = emp_row['Source_Names'].split(', ')[0] if emp_row['Source_Names'] else 'N/A'

        if primary_location in location_avg_map:
            loc_avg = location_avg_map[primary_location]

            emp_present_days = emp_row['Total_Present_Days']
            emp_avg_shift_td = pd.to_timedelta(emp_row['Average Shift Duration'])
            emp_total_more_t_td = pd.to_timedelta(emp_row['Total More_T Hours'])
            emp_total_short_t_td = pd.to_timedelta(emp_row['Total Short_T Hours'])

            present_days_dev = emp_present_days - loc_avg['Avg_Present_Days']
            avg_shift_dev_td = emp_avg_shift_td - loc_avg['Avg_Shift_Duration_td']
            more_t_hours_dev_td = emp_total_more_t_td - loc_avg['Total_More_T_Hours_td']
            short_t_hours_dev_td = emp_total_short_t_td - loc_avg['Total_Short_T_Hours_td']
            
            comparison_data.append({
                'No.': employee_no,
                'Name': employee_name,
                'Primary Location': primary_location,
                'Employee Present Days': emp_present_days,
                'Location Avg Present Days': f"{loc_avg['Avg_Present_Days']:.1f}",
                'Present Days Deviation': f"{present_days_dev:.1f}",
                'Employee Avg Shift Duration': format_timedelta_to_hms(emp_avg_shift_td),
                'Location Avg Shift Duration': format_timedelta_to_hms(loc_avg['Avg_Shift_Duration_td']),
                'Avg Shift Deviation': format_timedelta_to_hms(avg_shift_dev_td),
                'Employee Total More_T Hours (H)': round(emp_total_more_t_td.total_seconds() / 3600, 1),
                'Location Avg More_T Hours (H)': round(loc_avg['Total_More_T_Hours_td'].total_seconds() / 3600, 1),
                'More_T Hours Deviation': round(more_t_hours_dev_td.total_seconds() / 3600, 1),
                'Employee Total Short_T Hours (H)': round(emp_total_short_t_td.total_seconds() / 3600, 1),
                'Location Avg Short_T Hours (H)': round(loc_avg['Total_Short_T_Hours_td'].total_seconds() / 3600, 1),
                'Short_T Hours Deviation': round(short_t_hours_dev_td.total_seconds() / 3600, 1)
            })
        else:
            comparison_data.append({
                'No.': employee_no,
                'Name': employee_name,
                'Primary Location': primary_location,
                'Employee Present Days': emp_row['Total_Present_Days'],
                'Location Avg Present Days': 'N/A', 'Present Days Deviation': 'N/A',
                'Employee Avg Shift Duration': emp_row['Average Shift Duration'],
                'Location Avg Shift Duration': 'N/A', 'Avg Shift Deviation': 'N/A',
                'Employee Total More_T Hours (H)': round(pd.to_timedelta(emp_row['Total More_T Hours']).total_seconds() / 3600, 1),
                'Location Avg More_T Hours (H)': 'N/A', 'More_T Hours Deviation': 'N/A',
                'Employee Total Short_T Hours (H)': round(pd.to_timedelta(emp_row['Total Short_T Hours']).total_seconds() / 3600, 1),
                'Location Avg Short_T Hours (H)': 'N/A', 'Short_T Hours Deviation': 'N/A'
            })

    return pd.DataFrame(comparison_data)


def generate_location_recommendations(location_overview_df: pd.DataFrame, absenteeism_df: pd.DataFrame) -> dict:
    """
    Generates text-based recommendations for each location based on aggregated metrics.

    Args:
        location_overview_df (pd.DataFrame): The location overview DataFrame.
        absenteeism_df (pd.DataFrame): The absenteeism DataFrame.

    Returns:
        dict: A dictionary of recommendations for each location.
    """
    recommendations = {}
    if location_overview_df.empty:
        return recommendations

    merged_df = location_overview_df.merge(absenteeism_df, on='Source_Name', how='left')
    if 'Absenteeism_Rate_Location' not in merged_df.columns:
        merged_df['Absenteeism_Rate_Location'] = 0.0
    merged_df['Absenteeism_Rate_Location'] = merged_df['Absenteeism_Rate_Location'].fillna(0)

    ABSENTEEISM_THRESHOLD = 10
    MORE_T_HOURS_THRESHOLD_PER_EMPLOYEE = 20
    SHORT_T_HOURS_THRESHOLD_PER_EMPLOYEE = 15
    SINGLE_PUNCH_RATE_THRESHOLD = 5
    MULTI_PUNCH_RATE_THRESHOLD = 5

    for _, row in merged_df.iterrows():
        location_name = row['Source_Name']
        loc_recs = []

        total_more_t_hours_loc = pd.to_timedelta(row['Total More_T Hours (Location)']).total_seconds() / 3600
        total_short_t_hours_loc = pd.to_timedelta(row['Total Short_T Hours (Location)']).total_seconds() / 3600
        
        num_employees = row['Total_Employees'] if row['Total_Employees'] > 0 else 1
        avg_more_t_per_employee = total_more_t_hours_loc / num_employees
        avg_short_t_per_employee = total_short_t_hours_loc / num_employees

        if row['Absenteeism_Rate_Location'] > ABSENTEEISM_THRESHOLD:
            loc_recs.append(f"- High absenteeism rate ({row['Absenteeism_Rate_Location']:.1f}%). Consider reviewing attendance policies or reasons for frequent absences.")
        
        if avg_more_t_per_employee > MORE_T_HOURS_THRESHOLD_PER_EMPLOYEE:
            loc_recs.append(f"- Significant More_T recorded ({avg_more_t_per_employee:.1f} hrs/employee). Investigate workload distribution or staffing needs.")

        if avg_short_t_per_employee > SHORT_T_HOURS_THRESHOLD_PER_EMPLOYEE:
            loc_recs.append(f"- Notable Short_T hours ({avg_short_t_per_employee:.1f} hrs/employee). Look into reasons for short shifts or early departures.")

        if row['Single_Punch_Rate_Per_100_Punches'] > SINGLE_PUNCH_RATE_THRESHOLD:
            loc_recs.append(f"- High single punch rate ({row['Single_Punch_Rate_Per_100_Punches']:.1f}% of punches). This may indicate missed punches; review punch-in/out procedures or device reliability.")
        
        if row['Multi_Punch_Rate_Per_100_Punches'] > MULTI_PUNCH_RATE_THRESHOLD:
            loc_recs.append(f"- High multiple punch rate ({row['Multi_Punch_Rate_Per_100_Punches']:.1f}% of punches). Investigate reasons for frequent entries/exits (e.g., breaks, specific tasks, system issues).")

        if loc_recs:
            recommendations[location_name] = loc_recs
    
    return recommendations
