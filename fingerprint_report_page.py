import streamlit as st
import pandas as pd
import io
import calendar
import os
from datetime import timedelta, date

# --- COMPANY-SPECIFIC CONFIGURATIONS ---
# Define rules for each company.
# Each company can have default rules, location-specific overrides, and employee-specific overrides.
# calendar module constants (0=Monday, 6=Sunday)
COMPANY_CONFIGS = {
    "Al-hadabah times": {
        "default_rules": {
            "standard_shift_hours": 8,
            "under_time_threshold_hours": 7.5, # Employee is "missing" if total shift < this
            "overtime_start_hours": 9,        # Overtime is calculated for hours > this
            "over_time_enabled": True,        # Global flag for overtime calculation for this company/location/employee
            "is_rotational_off": False,       # Default for fixed shifts
            "weekend_days": [calendar.FRIDAY] # Default for Al-hadabah if no specific location rule, assuming 1 Friday
        },
        "location_rules": { # Rules specific to `Source_Name` (derived from filename/device)
            "HO": {
                "weekend_days": [calendar.FRIDAY, calendar.SATURDAY], # These are potential weekend days for alternating rule
                "weekend_rule_type": "alternating_f_fs", # Specific rule for alternating weekends (F then F+S)
                "over_time_enabled": False,
                "is_rotational_off": False
            },
            "Warehouse": {"weekend_days": [calendar.FRIDAY], "is_rotational_off": False},
            "lighting plus": {"weekend_days": [calendar.FRIDAY], "over_time_enabled": False, "is_rotational_off": False},
            "S16": {"weekend_days": [calendar.FRIDAY], "over_time_enabled": False, "is_rotational_off": False},
            "S17": {"weekend_days": [calendar.FRIDAY], "over_time_enabled": False, "is_rotational_off": False},
            "S20": {"weekend_days": [calendar.FRIDAY], "over_time_enabled": False, "is_rotational_off": False},
            "S33": {"weekend_days": [calendar.FRIDAY], "over_time_enabled": False, "is_rotational_off": False},
            "S14": {"weekend_days": [], "overtime_start_hours": 9, "over_time_enabled": True, "is_rotational_off": False}, # Work all week
            "S21": {"weekend_days": [], "overtime_start_hours": 9, "over_time_enabled": True, "is_rotational_off": False}, # Work all week
            "S39": {"weekend_days": [], "overtime_start_hours": 9, "over_time_enabled": True, "is_rotational_off": False}, # Work all week
            "S40": {"weekend_days": [], "overtime_start_hours": 9, "over_time_enabled": True, "is_rotational_off": False}, # Work all week
            "S41": {"weekend_days": [], "overtime_start_hours": 9, "over_time_enabled": True, "is_rotational_off": False}, # Work all week
            "S42": {"weekend_days": [], "overtime_start_hours": 9, "over_time_enabled": True, "is_rotational_off": False}, # Work all week
        }
    },
    "D&H": {
        "default_rules": {
            "standard_shift_hours": 8,
            "under_time_threshold_hours": 7.5,
            "overtime_start_hours": 9,
            "over_time_enabled": True,
            "weekend_days": [calendar.FRIDAY], # Default for D&H
            "is_rotational_off": False
        },
        "employee_overrides": { # Rules specific to employee 'No.' (for Brand Managers)
            # These are Brand Managers who can have rotational offs and no overtime
            "1031": {"over_time_enabled": False, "is_rotational_off": True, "weekend_days": [], "rotational_days_off_per_week": 1}, # Ali Dagher (D&H)
            "12299": {"over_time_enabled": False, "is_rotational_off": True, "weekend_days": [], "rotational_days_off_per_week": 1}, # Fata (D&H)
            "2579": {"over_time_enabled": False, "is_rotational_off": True, "weekend_days": [], "rotational_days_off_per_week": 1},  # Aline Armani (D&H)
            "1494": {"over_time_enabled": False, "is_rotational_off": True, "weekend_days": [], "rotational_days_off_per_week": 1}, # Raeda (D&H)
            "1483": {"over_time_enabled": False, "is_rotational_off": True, "weekend_days": [], "rotational_days_off_per_week": 1}  # Mayada Abou (D&H)
        },
        "location_rules": {
            "HO": {"weekend_days": [calendar.FRIDAY], "is_rotational_off": False},
            "Warehouse": {"weekend_days": [calendar.FRIDAY], "is_rotational_off": False}
        }
    },
    "D&co": {
        "default_rules": {
            "standard_shift_hours": 8,
            "under_time_threshold_hours": 7.5,
            "overtime_start_hours": 9,
            "over_time_enabled": True,
            "weekend_days": [calendar.FRIDAY], # Default for D&co
            "is_rotational_off": False
        },
        "employee_overrides": {
            # No specific employee overrides for D&co now as BMs moved to D&H
        },
        "location_rules": {
            "HO": {"weekend_days": [calendar.FRIDAY], "is_rotational_off": False},
            "Warehouse": {"weekend_days": [calendar.FRIDAY], "is_rotational_off": False},
            "Fashion SHW": {"weekend_days": [calendar.FRIDAY], "is_rotational_off": True, "rotational_days_off_per_week": 1},
            "Dar Al shifa": {"weekend_days": [], "is_rotational_off": True, "rotational_days_off_per_week": 1},
            "Bustan": {"weekend_days": [], "is_rotational_off": True, "rotational_days_off_per_week": 1},
            "Farwaniya Hospital": {"weekend_days": [], "is_rotational_off": True, "rotational_days_off_per_week": 1},
            "Jahra Hospital": {"weekend_days": [], "is_rotational_off": True, "rotational_days_off_per_week": 1},
            "mekki jumma": {"weekend_days": [], "is_rotational_off": True, "rotational_days_off_per_week": 1},
        }
    },
    "Second Cup": { # Added as a top-level company based on provided data
        "default_rules": {
            "standard_shift_hours": 8,
            "under_time_threshold_hours": 7.5,
            "overtime_start_hours": 9,
            "over_time_enabled": True,
            "weekend_days": [calendar.FRIDAY], # Based on "Only Fridays"
            "is_rotational_off": False,
            "opening_hours_count" : 24 # Added for stores working 24 hours, but not directly used in attendance logic yet.
        },
        "location_rules": {
            "Warehouse": {"weekend_days": [calendar.FRIDAY], "is_rotational_off": False}
        }
    }
}
# --- END COMPANY-SPECIFIC CONFIGURATIONS ---

# --- FILE-SPECIFIC DATE FORMATS ---
# Maps Source_Name (derived from filename) to its specific datetime format string.
# These formats are tried first for matching files.
FILE_DATE_FORMATS = {
    "Benetone Mohalab BM": '%d-%b-%y %I:%M:%S %p',
    "Benetone Mohalab Vm": '%d-%b-%y %I:%M:%S %p',
    "Benetone Mohalab": '%d-%b-%y %I:%M:%S %p',
    "BM D&H Dagher": '%d/%m/%Y %I:%M:%S %p',
    "Celio Marina BM": '%m/%d/%Y %I:%M:%S %p',
    "Celio Marina VM": '%m/%d/%Y %I:%M:%S %p',
    "Celio Marina": '%m/%d/%Y %I:%M:%S %p',
    "Celio Warehouse": '%d/%m/%Y %I:%M:%S %p',
    "D&H Daghr Vm": '%d/%m/%Y %I:%M:%S %p',
    "D&H HO": '%d/%m/%Y %I:%M %p',
    "D&H Warehouse": '%d/%m/%Y %I:%M:%S %p',
    "Designer Avenue": '%m/%d/%Y %I:%M:%S %p',
    "Etam 360": '%d/%m/%Y %I:%M:%S %p',
    "Etam Avenue": '%d/%m/%Y %I:%M:%S %p',
    "Etam Gatemall": '%d/%m/%Y %I:%M:%S %p',
    "Etam Marina": '%m/%d/%Y %I:%M:%S %p',
    "Etam Warehouse": '%d/%m/%Y %I:%M:%S %p',
    "FD Al Bahar BM": '%m/%d/%Y %I:%M:%S %p',
    "FD Al Bahar Vm": '%m/%d/%Y %I:%M:%S %p',
    "FD Boulevard BM": '%d/%m/%y %I:%M:%S %p',
    "FD Boulevard Vm": '%d/%m/%y %I:%M:%S %p',
    "Head OFfice VM": '%d/%m/%Y %I:%M:%S %p',
    "Lipsy Mohalab": '%d-%b-%y %I:%M:%S %p',
    "Spring Field": '%d/%m/%Y %I:%M:%S %p',
    "TT Mohalab": '%d-%b-%y %I:%M:%S %p',
    "Ws Koutmall": '%d/%m/%Y %I:%M:%S %p',
    "Ws 360 Vm": '%d-%b-%y %I:%M:%S %p',
    "Ws 360": '%d-%b-%y %I:%M:%S %p',
    "Ws Avenue": '%d/%m/%Y %I:%M:%S %p',
    "Ws Gatemall": '%d/%m/%Y %I:%M:%S %p',
    "Ws Mohalab": '%d-%b-%y %I:%M:%S %p',
    "Ws Olympia": '%d/%m/%Y %I:%M:%S %p',
    "Ws Sharq Vm": '%m/%d/%Y %I:%M:%S %p',
    "Ws Sharq": '%m/%d/%Y %I:%M:%S %p',
    "Yammay Avenue": '%d/%m/%Y %I:%M:%S %p',

    # alhadaba
    "Doha Store Warehouse": '%d/%m/%Y %I:%M:%S %p',
    "Hadaba HO": '%d/%m/%Y %I:%M %p',
    "Lighting Plus": '%d/%m/%Y %I:%M %p',
    "S14": '%d/%m/%Y %I:%M:%S %p',
    "S16": '%d/%m/%Y %I:%M:%S %p',
    "S17": '%d/%m/%Y %I:%M:%S %p',
    "S20": '%d/%m/%Y %I:%M:%S %p',
    "S21": '%d/%m/%Y %I:%M:%S %p',
    "S33": '%d/%m/%Y %I:%M:%S %p',
    "S39": '%d/%m/%Y %I:%M:%S %p',
    "S40": '%d/%m/%Y %I:%M:%S %p',
    "S41": '%d/%m/%Y %I:%M:%S %p',
    "S42": '%d/%m/%Y %I:%M:%S %p',

    # 2nd cup
    "2nd cup Warehouse": '%d/%m/%Y %I:%M:%S %p',
    "Admin Science": '%d/%m/%Y %I:%M:%S %p',
    "Badriya Hospital": '%d/%m/%Y %I:%M:%S %p',
    "Boys PAAET": '%d/%m/%Y %I:%M:%S %p',
    "Bustan": '%d/%m/%Y %I:%M:%S %p',
    "College of Science": '%d/%m/%Y %I:%M:%S %p',
    "Dar al Shifa Clinic": '%d/%m/%Y %I:%M:%S %p',
    "Dar al Shifa": '%d/%m/%Y %I:%M:%S %p',
    "Edu Boys": '%d/%m/%Y %I:%M:%S %p',
    "Edu Girls 2": '%d/%m/%Y %I:%M:%S %p',
    "Edu Girls": '%d/%m/%Y %I:%M:%S %p',
    "Farwaniya Hospital": '%d/%m/%Y %I:%M:%S %p',
    "Homz mall": '%d/%m/%Y %I:%M:%S %p',
    "IC Salmiya": '%d/%m/%Y %I:%M:%S %p',
    "International Hospital": '%d/%m/%Y %I:%M:%S %p',
    "Jaber Hospital": '%d/%m/%Y %I:%M:%S %p',
    "Jahar Hospital": '%d/%m/%Y %I:%M:%S %p',
    "Life Science": '%d/%m/%Y %I:%M:%S %p',
    "Makki Juma": '%d/%m/%Y %I:%M:%S %p',
    "Marina mall": '%d/%m/%Y %I:%M:%S %p',
    "Mohalab": '%d/%m/%Y %I:%M:%S %p',
    "MOI": '%d/%m/%Y %I:%M:%S %p',
    "Nursing Boys": '%d/%m/%Y %I:%M:%S %p',
    "Nursing Girls": '%d/%m/%Y %I:%M:%S %p',
    "PAAET Admin": '%d/%m/%Y %I:%M:%S %p',
    "Scup Vm": '%d/%m/%Y %I:%M:%S %p',

    # D&Co
    "BEBE Olympia": '%d/%m/%Y %I:%M:%S %p',
    "BYL Mohalab": '%d-%b-%y %I:%M:%S %p',
    "BYL 360": '%d/%m/%Y %I:%M:%S %p',
    "BYL Avenue": '%d/%m/%Y %I:%M:%S %p',
    "BYL Koutmall": '%d/%m/%Y %I:%M:%S %p',
    "FD Al Bahar": '%m/%d/%Y %I:%M:%S %p',
    "FD Boulevard": '%d/%m/%y %I:%M:%S %p',
    "FD Olympia": '%d/%m/%Y %I:%M:%S %p',
    "Hunkemoller": '%d/%m/%Y %I:%M:%S %p',
    "LVER 360": '%d/%m/%Y %I:%M:%S %p',
    "LVER Avenue": '%d/%m/%Y %I:%M:%S %p',
    "LVER Koutmall": '%d/%m/%Y %I:%M:%S %p',
    "LVER Gatemall": '%d/%m/%Y %I:%M:%S %p',
    "LVER Olympia": '%d/%m/%Y %I:%M:%S %p',
    "Menbur Avenue": '%d/%m/%Y %I:%M:%S %p',
}
# --- END FILE-SPECIFIC DATE FORMATS ---


# --- Column Name Mapping ---
# Maps standard internal column names to potential external column names found in uploaded files.
# The order of the list matters: it will try to find columns in this order.
COLUMN_MAPPING = {
    'No.': ['No.', 'AC-No.'],
    'Name': ['Name'],
    'Date/Time': ['Date/Time', 'Time'], # 'Time' is already here
    'Status': ['Status', 'State']
}
# --- END Column Mapping ---


# Function to safely merge dictionaries, with later dicts overriding earlier ones
def merge_configs(base, override):
    """
    Recursively merges two dictionaries. Values from 'override' overwrite 'base' values.
    If a key exists in both and its value is a dictionary, the dictionaries are merged.
    """
    merged = base.copy()
    if override:
        for k, v in override.items():
            if isinstance(merged.get(k), dict) and isinstance(v, dict):
                merged[k] = merge_configs(merged[k], v)
            else:
                merged[k] = v
    return merged

def _get_effective_rules_for_employee_day(company_name: str, employee_no: str, source_name: str) -> dict:
    """
    Determines the effective rules for a given employee on a specific day,
    applying hierarchy: Default -> Location -> Employee Override.
    Also handles implicit rotational status if a location has no fixed weekend days.
    """
    company_config = COMPANY_CONFIGS.get(company_name, {})
    
    # Start with default rules for the company
    effective_rules = company_config.get("default_rules", {}).copy()

    # Apply location-specific overrides
    location_rules = company_config.get("location_rules", {}).get(source_name, {})
    effective_rules = merge_configs(effective_rules, location_rules)

    # --- New Logic: If location has no explicit weekend days and is not already rotational, imply rotational_off ---
    # This ensures a universal "1 day off per week" rule unless explicitly overridden by employee-specific config
    # or if the location rule itself explicitly sets is_rotational_off to False with defined weekend_days.
    if (effective_rules.get("weekend_days") == [] or effective_rules.get("weekend_days") is None) and \
       not effective_rules.get("is_rotational_off", False):
        effective_rules["is_rotational_off"] = True
        # If rotational_days_off_per_week wasn't already set, default it to 1 for this implicit rotational type
        if "rotational_days_off_per_week" not in effective_rules:
            effective_rules["rotational_days_off_per_week"] = 1
    # --- End New Logic ---

    # Apply employee-specific overrides (highest precedence)
    employee_rules = company_config.get("employee_overrides", {}).get(employee_no, {})
    effective_rules = merge_configs(effective_rules, employee_rules)
    
    return effective_rules


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
def process_single_fingerprint_file(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> tuple[pd.DataFrame, bool]:
    """
    Reads a single uploaded fingerprint file (CSV or Excel),
    adds a 'Source_Name' column, and converts the 'Date/Time' column to datetime objects.
    Handles flexible column names and returns a flag indicating if the Status column was found.

    Args:
        uploaded_file (streamlit.runtime.uploaded_file_manager.UploadedFile):
            Lhe uploaded file object from Streamlit.

    Returns:
        tuple[pd.DataFrame, bool]: A DataFrame with the processed data and a boolean
        indicating if a 'Status' column (or its alternative 'State') was successfully found.
    """
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
    df = pd.DataFrame() # Initialize df to handle cases where read fails early
    status_column_found = False # Flag to track if 'Status' column was successfully found

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

    # Normalize column names based on COLUMN_MAPPING
    df_columns = df.columns.tolist()
    for standard_col, possible_names in COLUMN_MAPPING.items():
        found_match = False
        for name_variant in possible_names:
            if name_variant in df_columns:
                if standard_col != name_variant: # Rename only if different
                    df.rename(columns={name_variant: standard_col}, inplace=True)
                found_match = True
                if standard_col == 'Status': # Set flag if Status column is found
                    status_column_found = True
                break # Move to next standard_col once a match is found
        # If a critical column (not Status) is not found after checking all variations, raise an error
        if not found_match and standard_col in ['No.', 'Name', 'Date/Time']:
            raise ValueError(f"Missing critical column '{standard_col}' (or its alternatives {possible_names}) in '{uploaded_file.name}'.")
    
    # Extract source name from filename
    filename = uploaded_file.name
    source_name_parts = filename.split('.xlsx - ')
    # Handles cases like "Report.xlsx - DeviceName.xlsx" or just "Report.xlsx"
    source_name = source_name_parts[-1].replace(os.path.splitext(source_name_parts[-1])[1], '') if len(source_name_parts) > 1 else os.path.splitext(filename)[0]
    df['Source_Name'] = source_name.strip()

    # Required columns for further processing after renaming
    required_cols_for_processing = ['No.', 'Name', 'Date/Time'] # Status is optional now

    # Check for critical columns
    missing_critical_cols = [col for col in required_cols_for_processing if col not in df.columns]
    if missing_critical_cols:
        raise ValueError(f"Missing critical columns after renaming in '{uploaded_file.name}': {', '.join(missing_critical_cols)}")

    try:
        # Define a list of general date formats to try
        general_date_formats_to_try = [
            '%d/%m/%Y %I:%M:%S %p', # e.g., 24/05/2025 8:34:00 AM
            '%d/%m/%Y %I:%M %p',    # e.g., 24/05/2025 8:34 AM
            '%d-%b-%y %I:%M:%S %p', # e.g., 24-May-25 10:13:37 AM
            '%d-%b-%y %I:%M %p',    # e.g., 24-May-25 10:13 AM
            '%m/%d/%Y %I:%M:%S %p', # e.g., 6/16/2025 10:13:37 AM
            '%m/%d/%Y %I:%M %p',    # e.g., 6/16/2025 10:13 AM
            '%d/%m/%y %I:%M:%S %p', # e.g., 24/05/25 10:13:37 AM
            '%d/%m/%y %I:%M %p',    # e.g., 24/05/25 10:13 AM
            '%H:%M:%S',             # Time only (might be relevant if date is in another column, or inferred)
            '%H:%M',                # Time only (without seconds)
        ]

        # Get specific format for this source, if available
        specific_format = FILE_DATE_FORMATS.get(source_name.strip())
        
        # Create the prioritized list of formats for this file
        date_formats_for_this_file = []
        if specific_format:
            date_formats_for_this_file.append(specific_format)
            
        # Append general formats, ensuring no duplicates.
        for fmt in general_date_formats_to_try:
            if fmt not in date_formats_for_this_file:
                date_formats_for_this_file.append(fmt)

        parsed_series = pd.Series(pd.NaT, index=df.index)
        # Store original 'Date/Time' column to re-attempt parsing if first format fails
        original_datetime_col = df['Date/Time'].copy() 
        for fmt in date_formats_for_this_file:
            unparsed_mask = parsed_series.isnull()
            if unparsed_mask.any():
                # Only try to parse the still unparsed values from the original column
                parsed_series[unparsed_mask] = pd.to_datetime(original_datetime_col[unparsed_mask], format=fmt, errors='coerce')
            else:
                break # All values successfully parsed, no need to try more formats

        df['Date/Time'] = parsed_series

        # Drop rows where Date/Time could not be parsed after all attempts
        df.dropna(subset=['Date/Time'], inplace=True)
        if df.empty:
            raise ValueError(f"No valid 'Date/Time' entries in '{uploaded_file.name}' after parsing and cleaning with all formats.")
    except Exception as e:
        raise ValueError(f"Error parsing 'Date/Time' column in '{uploaded_file.name}': {e}. Check date format.")

    # Ensure 'Status' column exists, even if empty, if it wasn't found
    if 'Status' not in df.columns:
        df['Status'] = '' # Create an empty string column if not found
    else:
        # Ensure 'Status' column is string type and handle NaNs if it was found
        df['Status'] = df['Status'].astype(str)
        df['Status'] = df['Status'].replace('nan', '').fillna('')

    return df, status_column_found

# --- Function to calculate shift durations from a list of uploaded files ---
def calculate_shift_durations_from_uploads(uploaded_files: list, selected_company_name: str) -> tuple[pd.DataFrame, list, date, date]:
    """
    Reads fingerprint files from a list of uploaded Streamlit files, combines them,
    and calculates detailed shift and break durations based on new case-by-case logic,
    including original and cleaned punch counts, and handling the 1 AM day-end rule.
    Returns the detailed DataFrame, error log, and global min/max dates.

    Args:
        uploaded_files (list): A list of Streamlit UploadedFile objects.
        selected_company_name (str): The name of the company selected by the user.

    Returns:
        tuple[pd.DataFrame, list, date, date]: A tuple containing the detailed DataFrame,
        a list of error dictionaries, global min date, and global max date.
    """
    list_of_dfs = []
    error_log = [] # Collect errors here
    # Track if ANY file had a status column. If no file has it, then global_status_present will be False
    global_status_present = False 

    if not uploaded_files:
        return pd.DataFrame(), [{'Filename': 'N/A', 'Error': 'No files uploaded to process.'}], None, None

    for uploaded_file in uploaded_files:
        try:
            df, status_found_for_file = process_single_fingerprint_file(uploaded_file)
            list_of_dfs.append(df)
            if status_found_for_file:
                global_status_present = True # Set to True if at least one file has a status column
        except Exception as e:
            error_message = f"Error processing {uploaded_file.name}: {type(e).__name__}: {e}"
            error_log.append({'Filename': uploaded_file.name, 'Error': error_message})

    if not list_of_dfs:
        return pd.DataFrame(), error_log, None, None

    combined_df = pd.concat(list_of_dfs, ignore_index=True)

    final_required_cols = ['No.', 'Name', 'Date/Time'] # Status is not critical for this check anymore
    if not all(col in combined_df.columns for col in final_required_cols):
        missing = [col for col in final_required_cols if col not in combined_df.columns]
        err_msg = f"After combining all files, missing crucial columns: {', '.join(missing)}. " \
                  "Please check column headers across all your input files."
        error_log.append({'Filename': 'Combined Data', 'Error': err_msg})
        return pd.DataFrame(), error_log, None, None

    # --- DEBUGGING AID: Display min/max dates of the raw combined data ---
    temp_min_date_raw = combined_df['Date/Time'].dt.date.min() if not combined_df.empty else 'N/A'
    temp_max_date_raw = combined_df['Date/Time'].dt.date.max() if not combined_df.empty else 'N/A'
    st.write(f"DEBUG: Raw combined data date range (before 1 AM rule): {temp_min_date_raw} to {temp_max_date_raw}")
    # --- END DEBUGGING AID ---

    # Capture the original global min date before any adjustments for the 1 AM rule exception
    global_min_date_original = combined_df['Date/Time'].dt.date.min()


    # Identify and remove exact duplicate rows based on key columns, including 'Source_Name'
    # Only include 'Status' in drop_duplicates if it was actually present in any file
    subset_for_duplicates = ['No.', 'Name', 'Date/Time', 'Source_Name']
    if global_status_present:
        subset_for_duplicates.append('Status')

    initial_duplicates = combined_df.duplicated(subset=subset_for_duplicates, keep='first').sum()
    if initial_duplicates > 0:
        combined_df.drop_duplicates(subset=subset_for_duplicates, keep='first', inplace=True)
    
    combined_df = combined_df.sort_values(by=['No.', 'Date/Time']).reset_index(drop=True)
    
    # --- RULE: Adjust Date for punches between 12:00 AM and 1:00 AM ---
    # Punches in this window belong to the previous calendar day's shift.
    # EXCEPTION: Do NOT apply this rule to punches on the very first day of the data.
    # This also considers "Second Cup" locations where 24-hour shifts might genuinely start after midnight.
    combined_df['Date'] = combined_df['Date/Time'].dt.date
    
    # Determine which rows should have their date shifted
    # A punch should be shifted if it's between 00:00 and 00:59 AND its original date is NOT the global minimum date
    # AND it's NOT from a "Second Cup" location (where 24hr operations imply shifts can legitimately start after midnight).
    # Retrieve rules for each punch's source_name to check for 'opening_hours_count'
    
    # Create a Series to store the decision for each row
    should_shift_date_series = pd.Series(False, index=combined_df.index)

    # Iterate through rows or apply more vectorized approach if performance critical for very large DFs
    # For now, iterating to apply rules based on source_name dynamically
    for idx, row in combined_df.iterrows():
        # Get effective rules for the specific punch's source_name
        employee_no_str = str(row['No.'])
        source_name_str = row['Source_Name']
        rules_for_punch_location = _get_effective_rules_for_employee_day(selected_company_name, employee_no_str, source_name_str)
        
        # Check if the location has 24-hour opening hours (e.g., Second Cup)
        is_24_hour_location = rules_for_punch_location.get("opening_hours_count") == 24

        # Apply shift logic only if NOT a 24-hour location, and not the global min date
        if not is_24_hour_location and \
           row['Date/Time'].hour == 0 and \
           row['Date/Time'].minute >= 0 and \
           row['Date/Time'].minute < 60 and \
           row['Date/Time'].date() != global_min_date_original:
            should_shift_date_series.loc[idx] = True

    combined_df.loc[should_shift_date_series, 'Date'] = (
        pd.to_datetime(combined_df.loc[should_shift_date_series, 'Date']) - pd.Timedelta(days=1)
    ).dt.date
    # --- END Date Adjustment Rule ---

    global_min_date = combined_df['Date'].min()
    global_max_date = combined_df['Date'].max()

    # Further debug: Display min/max dates after date adjustment
    st.write(f"DEBUG: Data date range after 1 AM rule adjustment: {global_min_date} to {global_max_date}")


    def get_detailed_punch_info_for_group(group, selected_company_name: str, status_column_was_present: bool):
        """
        Custom aggregation function to determine detailed shift and break durations
        for each employee-day group based on the number of punches, and new cleaning rules,
        including overtime and under-time based on dynamic rules.
        """
        group = group.sort_values(by='Date/Time').reset_index(drop=True)

        employee_no = str(group['No.'].iloc[0])
        source_name = group['Source_Name'].iloc[0] 
        effective_rules = _get_effective_rules_for_employee_day(selected_company_name, employee_no, source_name)

        standard_shift_hours = effective_rules.get("standard_shift_hours", 8)
        under_time_threshold_hours = effective_rules.get("under_time_threshold_hours", 7.5)
        overtime_start_hours = effective_rules.get("overtime_start_hours", 9)
        over_time_enabled = effective_rules.get("over_time_enabled", True)

        if group.empty:
            return {
                'No.': employee_no,
                'Name': group['Name'].iloc[0] if not group.empty else None,
                'Date': group['Date'].iloc[0] if not group.empty else None,
                'Source_Name': source_name,
                'Original Number of Punches': 0,
                'Number of Cleaned Punches': 0,
                'First Punch Time': 'N/A', 'Last Punch Time': 'N/A',
                'Total Shift Duration': '00:00:00',
                'Total Break Duration': '00:00:00',
                'Daily_Overtime_Hours': '00:00:00',
                'Daily_Under_Time_Hours': '00:00:00',
                'is_overtime_day': False,
                'is_under_time_day': False,
                'Punch Status': 'No valid punches for day'
            }

        original_punch_count = len(group)

        # --- Universal Cleaning: Always keep first and last punch, apply 10-min consolidation for others ---
        consolidated_punches_list = []
        if not group.empty:
            # Always add the very first punch
            consolidated_punches_list.append(group.iloc[0])

            # Process intermediate punches (from second to second-to-last)
            # Apply consolidation based on 10-minute rule AND (if status is available) status change
            for i in range(1, original_punch_count - 1):
                current_punch = group.iloc[i]
                last_kept_punch = consolidated_punches_list[-1]

                if (current_punch['Date/Time'] - last_kept_punch['Date/Time']) > pd.Timedelta(minutes=10) or \
                   (status_column_was_present and current_punch['Status'] != last_kept_punch['Status']):
                    consolidated_punches_list.append(current_punch)
            
            # Always add the very last punch if there's more than one original punch
            # and it's not already the last kept punch (due to previous additions)
            if original_punch_count > 1 and \
               (group.iloc[-1]['Date/Time'] != consolidated_punches_list[-1]['Date/Time'] or \
               (status_column_was_present and group.iloc[-1]['Status'] != consolidated_punches_list[-1]['Status'])):
                consolidated_punches_list.append(group.iloc[-1])
            # Edge case: If original_punch_count is > 1 but only the first punch was kept by the loop
            # (i.e., all intermediate punches were within 10 minutes AND had same status),
            # ensure the last punch is also present to calculate total duration.
            if original_punch_count > 1 and len(consolidated_punches_list) == 1:
                consolidated_punches_list.append(group.iloc[-1]) # Force add the last punch

        cleaned_group = pd.DataFrame(consolidated_punches_list)
        cleaned_punch_count = len(cleaned_group)

        total_shift_duration = pd.Timedelta(seconds=0)
        total_break_duration = pd.Timedelta(seconds=0)
        punch_status = "N/A"
        individual_interval_details = []

        first_punch_time_formatted = 'N/A'
        last_punch_time_formatted = 'N/A'

        if not group.empty: # Use original group for raw first/last punch times for display
            first_punch_time_formatted = group.iloc[0]['Date/Time'].strftime('%I:%M:%S %p')
            last_punch_time_formatted = group.iloc[-1]['Date/Time'].strftime('%I:%M:%S %p')

        if cleaned_punch_count == 0:
            punch_status = "No valid punches after cleaning"
            
        elif cleaned_punch_count == 1:
            punch_status = "Single Punch (0 Shift Duration)" # If only one punch, no duration

        elif cleaned_punch_count >= 2: # At least two punches, can calculate total presence
            total_shift_duration = cleaned_group.iloc[-1]['Date/Time'] - cleaned_group.iloc[0]['Date/Time']
            
            if status_column_was_present:
                # Attempt to find shift/break patterns if status is available
                # This logic assumes C/In, C/Out, C/In, C/Out for 2 shifts 1 break
                if cleaned_punch_count == 4 and \
                   cleaned_group.iloc[0]['Status'] == 'C/In' and \
                   cleaned_group.iloc[1]['Status'] == 'C/Out' and \
                   cleaned_group.iloc[2]['Status'] == 'C/In' and \
                   cleaned_group.iloc[3]['Status'] == 'C/Out':
                    
                    shift1 = cleaned_group.iloc[1]['Date/Time'] - cleaned_group.iloc[0]['Date/Time']
                    break1 = cleaned_group.iloc[2]['Date/Time'] - cleaned_group.iloc[1]['Date/Time']
                    shift2 = cleaned_group.iloc[3]['Date/Time'] - cleaned_group.iloc[2]['Date/Time']
                    total_shift_duration = shift1 + shift2 # Recalculate based on actual shifts
                    total_break_duration = break1
                    punch_status = "Two Shifts with One Break (4 Punches, Status Matched)"
                    individual_interval_details.append({'type': 'Shift', 'duration': shift1})
                    individual_interval_details.append({'type': 'Break', 'duration': break1})
                    individual_interval_details.append({'type': 'Shift', 'duration': shift2})
                else:
                    # Generic handling for other multi-punch scenarios with status, showing total presence
                    punch_status = f"Complex Pattern ({cleaned_punch_count} Cleaned Punches with Status)"
                    # Iterate through cleaned punches to log intervals
                    for i in range(len(cleaned_group) - 1):
                        interval = cleaned_group.iloc[i+1]['Date/Time'] - cleaned_group.iloc[i]['Date/Time']
                        interval_type = "General" # Default
                        # Simple attempt to infer based on status sequence (can be more complex if needed)
                        if cleaned_group.iloc[i]['Status'].endswith('/In') and cleaned_group.iloc[i+1]['Status'].endswith('/Out'):
                            interval_type = "Shift"
                        elif cleaned_group.iloc[i]['Status'].endswith('/Out') and cleaned_group.iloc[i+1]['Status'].endswith('/In'):
                            interval_type = "Break"
                        individual_interval_details.append({'type': interval_type, 'duration': interval})
                    
            else: # Status column was NOT present
                punch_status = f"Total Presence ({cleaned_punch_count} Punches, No Status Data)"
                # Total shift duration is already (last - first)
                total_break_duration = pd.Timedelta(seconds=0) # Cannot determine breaks without status
                # Log only the overall interval
                if cleaned_punch_count > 1:
                    individual_interval_details.append({'type': 'Total Presence', 'duration': total_shift_duration})

        # Calculate Daily Overtime and Under-time and set flags
        daily_overtime_td = pd.Timedelta(seconds=0)
        daily_under_time_td = pd.Timedelta(seconds=0)
        is_overtime_day = False
        is_under_time_day = False

        total_shift_hours = total_shift_duration.total_seconds() / 3600.0

        if over_time_enabled:
            # Overtime is when actual hours exceed the overtime_start_hours
            if total_shift_hours > overtime_start_hours:
                daily_overtime_td = pd.Timedelta(hours=total_shift_hours - overtime_start_hours)
                # Mark as overtime day if there's any calculated overtime duration > 0
                if daily_overtime_td > pd.Timedelta(seconds=0): # Ensures flag is true only if actual overtime exists
                    is_overtime_day = True
        
        # Under-time is when actual hours are less than under_time_threshold_hours, but greater than 0
        if total_shift_hours < under_time_threshold_hours and total_shift_hours > 0:
            daily_under_time_td = pd.Timedelta(hours=under_time_threshold_hours - total_shift_hours)
            # Mark as under-time day if there's any calculated under-time duration > 0
            if daily_under_time_td > pd.Timedelta(seconds=0): # Ensures flag is true only if actual under-time exists
                is_under_time_day = True

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
            else: # 'General' or 'Total Presence' or 'Ignored Short'
                general_col_count += 1
                intervals_output_dict[f'Interval {general_col_count} Duration'] = format_timedelta_to_hms(item['duration'])

        return_data = {
            'No.': employee_no,
            'Name': group['Name'].iloc[0],
            'Date': group['Date'].iloc[0],
            'Source_Name': source_name, # Keep individual source name for detailed report
            'Original Number of Punches': original_punch_count,
            'Number of Cleaned Punches': cleaned_punch_count,
            'First Punch Time': 'N/A', 'Last Punch Time': 'N/A',
            'Total Shift Duration': format_timedelta_to_hms(total_shift_duration),
            'Total Break Duration': '00:00:00', # Ensure breaks are zero if not calculable
            'Daily_Overtime_Hours': format_timedelta_to_hms(daily_overtime_td),
            'Daily_Under_Time_Hours': format_timedelta_to_hms(daily_under_time_td),
            'is_overtime_day': is_overtime_day, # Use the calculated variable
            'is_under_time_day': is_under_time_day, # Use the calculated variable
            'Punch Status': punch_status,
        }
        return_data.update(intervals_output_dict)

        return return_data

    daily_report_list = []
    if combined_df.empty:
        return pd.DataFrame(), error_log, None, None

    grouping_cols = ['No.', 'Name', 'Date']
    if not all(col in combined_df.columns for col in grouping_cols):
        missing = [col for col in grouping_cols if col not in combined_df.columns]
        err_msg = f"Cannot group data: Missing one or more grouping columns ({', '.join(missing)})."
        error_log.append({'Filename': 'Combined Data', 'Error': err_msg})
        return pd.DataFrame(), error_log, None, None

    # Pass selected_company_name and global_status_present to get_detailed_punch_info_for_group
    for (no, name, date), group in combined_df.groupby(grouping_cols):
        detailed_info = get_detailed_punch_info_for_group(group, selected_company_name, global_status_present)
        daily_report_list.append(detailed_info)

    daily_report = pd.DataFrame(daily_report_list)

    # Fill NaN values for all dynamically generated duration/hours columns
    for col in daily_report.columns:
        if 'Duration' in col or 'Hours' in col:
            daily_report[col] = daily_report[col].fillna('00:00:00')
        elif 'is_overtime_day' in col or 'is_under_time_day' in col: # Fill boolean NaNs with False
             daily_report[col] = daily_report[col].fillna(False)

    # Define the desired fixed column order
    fixed_cols = ['Source_Name', 'No.', 'Name', 'Date', 
                  'Original Number of Punches', 'Number of Cleaned Punches',
                  'First Punch Time', 'Last Punch Time',
                  'Total Shift Duration', 'Total Break Duration',
                  'Daily_Overtime_Hours', 'Daily_Under_Time_Hours',
                  'is_overtime_day', 'is_under_time_day', # Add new daily flags here
                  'Punch Status']

    all_columns = daily_report.columns.tolist()
    
    dynamic_shift_cols = sorted([col for col in all_columns if 'Shift ' in col and 'Duration' in col and 'Total' not in col],
                                key=lambda x: int(x.split(' ')[1]))
    dynamic_break_cols = sorted([col for col in all_columns if 'Break ' in col and 'Duration' in col and 'Total' not in col],
                                key=lambda x: int(x.split(' ')[1]))
    dynamic_general_interval_cols = sorted([col for col in all_columns if 'Interval ' in col and 'Duration' in col and 'Total' not in col],
                                            key=lambda x: int(x.split(' ')[1]))

    final_column_order = fixed_cols + dynamic_shift_cols + dynamic_break_cols + dynamic_general_interval_cols
    final_column_order_existing = [col for col in final_column_order if col in daily_report.columns]

    final_output_df = daily_report[final_column_order_existing].copy() # Ensure this is a copy to prevent SettingWithCopyWarning

    # Convert duration/hours string columns back to timedelta for consistency in analysis functions
    final_output_df['Total Shift Duration_td'] = final_output_df['Total Shift Duration'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else x)
    final_output_df['Daily_Overtime_Hours_td'] = final_output_df['Daily_Overtime_Hours'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else x)
    final_output_df['Daily_Under_Time_Hours_td'] = final_output_df['Daily_Under_Time_Hours'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else x)


    return final_output_df, error_log, global_min_date, global_max_date

# Helper to get expected working days for a period, considering alternating weekends
def _get_expected_working_days_in_period(start_date: date, end_date: date, rules: dict) -> float: # Return float for precision
    """
    Calculates the number of expected working days within a given date range,
    considering company-specific weekend rules, including alternating weekends and rotational offs.
    Returns the expected number of working days (can be float for rotational).
    """
    if start_date is None or end_date is None or start_date > end_date:
        return 0.0

    total_days_in_period_float = (end_date - start_date).days + 1.0 # Use float for calculations

    is_rotational_off = rules.get("is_rotational_off", False)
    rotational_days_off_per_week = rules.get("rotational_days_off_per_week", 1) # Default 1 day off for rotational

    if is_rotational_off:
        # Calculate expected off days based on rate per week
        expected_off_days_exact = total_days_in_period_float * (rotational_days_off_per_week / 7.0)
        expected_working_days_exact = total_days_in_period_float - expected_off_days_exact
        return expected_working_days_exact
    else:
        expected_days = 0
        current_date = start_date
        
        weekend_days = rules.get("weekend_days", [calendar.FRIDAY, calendar.SATURDAY])
        weekend_rule_type = rules.get("weekend_rule_type", "fixed") # "fixed" or "alternating_f_fs"

        while current_date <= end_date:
            day_of_week = current_date.weekday() # Monday is 0, Sunday is 6

            is_weekend = False
            if weekend_rule_type == "fixed":
                if day_of_week in weekend_days:
                    is_weekend = True
            elif weekend_rule_type == "alternating_f_fs":
                iso_week_number = current_date.isocalendar()[1]
                if (iso_week_number % 2) == 1: # Odd weeks: Friday only (Week 1, 3, 5...)
                    if day_of_week == calendar.FRIDAY:
                        is_weekend = True
                else: # Even weeks: Friday and Saturday (Week 2, 4, 6...)
                    if day_of_week == calendar.FRIDAY or day_of_week == calendar.SATURDAY:
                        is_weekend = True
            
            if not is_weekend:
                expected_days += 1
            
            current_date += timedelta(days=1)
        return float(expected_days) # Return float even for fixed, for consistency

# --- Function to generate summary report from detailed DataFrame ---
def generate_summary_report(detailed_df: pd.DataFrame, selected_company_name: str, global_start_date: date, global_end_date: date) -> pd.DataFrame:
    """
    Generates a summary report from the detailed daily shift DataFrame,
    considering company-specific rules and calculating new KPIs for the GLOBAL reporting period.
    """
    if detailed_df.empty:
        return pd.DataFrame()

    # The detailed_df should already have _td columns from calculate_shift_durations_from_uploads
    detailed_df['Date'] = pd.to_datetime(detailed_df['Date'])
    
    # Group by employee (No. and Name) for a single summary row per employee
    # Aggregate Source_Name to show all locations the employee punched at
    summary_grouped = detailed_df.groupby(['No.', 'Name']).agg(
        # Source_Names: aggregate all unique Source_Names for this employee
        Source_Names=('Source_Name', lambda x: ", ".join(x.astype(str).unique())),
        Total_Present_Days=('Date', lambda x: x[detailed_df.loc[x.index, 'Total Shift Duration_td'] > pd.Timedelta(seconds=0)].nunique()),
        Total_Shift_Durations_td=('Total Shift Duration_td', 'sum'),
        Total_Overtime_Hours_td=('Daily_Overtime_Hours_td', 'sum'),
        Total_Under_Time_Hours_td=('Daily_Under_Time_Hours_td', 'sum'),
        Count_Single_Punch_Days=('Punch Status', lambda x: (x == "Single Punch (0 Shift Duration)").sum()),
        Count_More_Than_4_Punches_Days=('Original Number of Punches', lambda x: (x > 4).sum()),
        # New: Count of days with overtime and under-time
        Count_Overtime_Days=('is_overtime_day', 'sum'),
        Count_Under_Time_Days=('is_under_time_day', 'sum'),
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
    summary_grouped['Total_Absent_Days'] = 0 # Initialize for calculation
    summary_grouped['Total_Expected_Weekends_In_Period'] = 0.0 # New: Initialize for expected weekends (float)
    summary_grouped['Total_Employee_Period_OFFs'] = 0.0 # New: Initialize for employee's allowed offs
    summary_grouped['Average Shift Duration'] = '00:00:00' # New: Initialize for average shift duration

    total_days_in_global_period_float = (global_end_date - global_start_date).days + 1.0

    for index, row in summary_grouped.iterrows():
        employee_no = str(row['No.'])
        # Get effective rules for this employee (for is_rotational_off check)
        # We need a source_name for the lookup, so we'll use the first one from aggregated Source_Names
        primary_source_name = row['Source_Names'].split(', ')[0] if ', ' in row['Source_Names'] else row['Source_Names']
        effective_employee_rules = _get_effective_rules_for_employee_day(selected_company_name, employee_no, primary_source_name)
        
        # Determine exact expected working days (float) based on employee's rules
        expected_working_days_exact = _get_expected_working_days_in_period(
            global_start_date, global_end_date, effective_employee_rules
        )
        
        # Round for display in 'Total_Expected_Working_Days_In_Period'
        summary_grouped.loc[index, 'Total_Expected_Working_Days_In_Period'] = int(round(expected_working_days_exact))

        # Calculate Absent Days based on rounded expected working days
        summary_grouped.loc[index, 'Total_Absent_Days'] = max(0, summary_grouped.loc[index, 'Total_Expected_Working_Days_In_Period'] - row['Total_Present_Days'])

        # Calculate Expected Weekends (float) based on total days minus exact working days from rules
        expected_weekends_from_rules = total_days_in_global_period_float - expected_working_days_exact
        
        # Determine the universal minimum expected weekends based on 1 day off per week
        # This now correctly applies based on whether the employee is *actually* rotational or not based on rules.
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

        # --- Calculate Total_Employee_Period_OFFs ---
        employee_punch_start_date = row['Employee_Punch_Start_Date'].to_pydatetime().date() # Convert Timestamp to date
        employee_punch_end_date = row['Employee_Punch_End_Date'].to_pydatetime().date()   # Convert Timestamp to date
        
        total_days_in_employee_punch_period_float = (employee_punch_end_date - employee_punch_start_date).days + 1.0

        expected_working_days_in_employee_period = _get_expected_working_days_in_period(
            employee_punch_start_date, employee_punch_end_date, effective_employee_rules
        )
        allowed_offs_in_employee_period = total_days_in_employee_punch_period_float - expected_working_days_in_employee_period
        summary_grouped.loc[index, 'Total_Employee_Period_OFFs'] = round(allowed_offs_in_employee_period, 1)
        # --- End Total_Employee_Period_OFFs ---


        # Calculate Average Shift Duration
        if row['Total_Present_Days'] > 0:
            avg_shift_td = row['Total_Shift_Durations_td'] / row['Total_Present_Days']
            summary_grouped.loc[index, 'Average Shift Duration'] = format_timedelta_to_hms(avg_shift_td)
        else:
            summary_grouped.loc[index, 'Average Shift Duration'] = '00:00:00'


    # Format final Timedelta columns back to HH:MM:SS string
    summary_grouped['Total Shift Durations'] = summary_grouped['Total_Shift_Durations_td'].apply(format_timedelta_to_hms)
    summary_grouped['Total Overtime Hours'] = summary_grouped['Total_Overtime_Hours_td'].apply(format_timedelta_to_hms)
    summary_grouped['Total Under-Time Hours'] = summary_grouped['Total_Under_Time_Hours_td'].apply(format_timedelta_to_hms)

    # Format the new date columns
    summary_grouped['Employee Punch Start Date'] = summary_grouped['Employee_Punch_Start_Date'].dt.strftime('%Y-%m-%d')
    summary_grouped['Employee Punch End Date'] = summary_grouped['Employee_Punch_End_Date'].dt.strftime('%Y-%m-%d')


    # Select and reorder columns for the final summary report
    summary_report_cols = [
        'No.', 'Name', 'Source_Names', # Consolidated Source_Names
        'Overall Data Start Date', 'Overall Data End Date', # Renamed
        'Total Days in Overall Period', # New column
        'Employee Punch Start Date', 'Employee Punch End Date', # New columns
        'Total_Expected_Working_Days_In_Period', 'Total_Expected_Weekends_In_Period', # Added new column
        'Total_Employee_Period_OFFs', # Added new column here
        'Total_Present_Days', 'Total_Absent_Days',
        'Total Shift Durations', 'Average Shift Duration', # Added new column
        'Total Overtime Hours', 'Total Under-Time Hours',
        'Count_Overtime_Days', 'Count_Under_Time_Days', # New count columns
        'Count_Single_Punch_Days', 'Count_More_Than_4_Punches_Days'
    ]
    summary_df = summary_grouped[summary_report_cols]

    return summary_df


# --- New functions for Analysis Dashboard ---

def analyze_consecutive_absences(detailed_df: pd.DataFrame) -> pd.DataFrame:
    """
    Analyzes detailed daily report to find consecutive absent days for each employee.
    """
    if detailed_df.empty:
        return pd.DataFrame(columns=['No.', 'Name', 'Source_Names', 'Longest Consecutive Absences (Days)', 'Absence Start Date', 'Absence End Date'])

    # Ensure 'Date' is datetime and sort
    df = detailed_df.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values(by=['No.', 'Date'])

    absent_summary = []

    for (emp_no, emp_name), group in df.groupby(['No.', 'Name']):
        # Create a full date range for the employee's active period
        min_date = group['Date'].min()
        max_date = group['Date'].max()
        full_date_range = pd.date_range(start=min_date, end=max_date, freq='D')
        
        # Mark all dates in the full range as potentially absent initially
        attendance_series = pd.Series(False, index=full_date_range) # False means absent initially

        # Mark dates where employee was present
        present_dates = group[group['Total Shift Duration_td'] > pd.Timedelta(seconds=0)]['Date'].dt.normalize().unique()
        attendance_series.loc[present_dates] = True # True means present

        # Identify consecutive absent streaks
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
        
        # Check for streak at the very end of the period
        if current_streak > longest_streak:
            longest_streak = current_streak
            longest_streak_start_date = streak_start_date
            longest_streak_end_date = max_date # Streak extends to end of data

        if longest_streak > 0:
            absent_summary.append({
                'No.': emp_no,
                'Name': emp_name,
                'Source_Names': ", ".join(group['Source_Name'].astype(str).unique()),
                'Longest Consecutive Absences (Days)': longest_streak,
                'Absence Start Date': longest_streak_start_date.strftime('%Y-%m-%d') if longest_streak_start_date else 'N/A',
                'Absence End Date': longest_streak_end_date.strftime('%Y-%m-%d') if longest_streak_end_date else 'N/A'
            })
    return pd.DataFrame(absent_summary)


def analyze_unusual_shift_durations(detailed_df: pd.DataFrame, selected_company_name: str) -> pd.DataFrame:
    """
    Analyzes detailed daily report to find shifts significantly shorter or longer than standard.
    Flags shifts outside a configurable percentage deviation from standard.
    """
    if detailed_df.empty:
        return pd.DataFrame(columns=['No.', 'Name', 'Date', 'Source_Name', 'Shift Duration', 'Standard Hours', 'Deviation (%)', 'Anomaly Type'])

    df = detailed_df.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    # Ensure this column is available from detailed_df
    df['Shift_Duration_Hours'] = df['Total Shift Duration_td'].dt.total_seconds() / 3600.0

    anomalies = []
    
    # Get overall company standard shift hours
    default_standard_shift_hours = COMPANY_CONFIGS.get(selected_company_name, {}).get("default_rules", {}).get("standard_shift_hours", 8)

    for index, row in df.iterrows():
        employee_no = str(row['No.'])
        source_name = row['Source_Name']
        effective_rules = _get_effective_rules_for_employee_day(selected_company_name, employee_no, source_name)
        standard_shift_hours = effective_rules.get("standard_shift_hours", default_standard_shift_hours)

        shift_duration_hours = row['Shift_Duration_Hours']
        
        # Only consider shifts with actual duration for anomaly detection
        if shift_duration_hours > 0:
            deviation = ((shift_duration_hours - standard_shift_hours) / standard_shift_hours) * 100
            
            # Define thresholds for "unusual" deviation (e.g., +/- 25%)
            # These can be made configurable in the Streamlit UI later if needed.
            long_shift_threshold_pct = 25
            short_shift_threshold_pct = -25 # Negative for shorter shifts

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
    """
    if detailed_df.empty:
        return pd.DataFrame()

    df = detailed_df.copy()
    df['Total Shift Duration_td'] = df['Total Shift Duration'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else x)
    df['Daily_Overtime_Hours_td'] = df['Daily_Overtime_Hours'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else x)
    df['Daily_Under_Time_Hours_td'] = df['Daily_Under_Time_Hours'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else x)

    location_summary = df.groupby('Source_Name').agg(
        Total_Employees=('No.', 'nunique'), # Headcount for the location
        Total_Location_Punch_Days=('Date', 'nunique'), # Total distinct days with punches at this location
        Total_Original_Punches=('Original Number of Punches', 'sum'), # Total raw punches recorded
        Total_Shift_Duration_Location_TD=('Total Shift Duration_td', 'sum'),
        Total_Overtime_Location_TD=('Daily_Overtime_Hours_td', 'sum'),
        Total_Under_Time_Location_TD=('Daily_Under_Time_Hours_td', 'sum'),
        Total_Single_Punch_Days_Location=('Punch Status', lambda x: (x == "Single Punch (0 Shift Duration)").sum()),
        Total_More_Than_4_Punches_Days_Location=('Original Number of Punches', lambda x: (x > 4).sum()),
    ).reset_index()

    # Calculate rates for single and multiple punches
    location_summary['Single_Punch_Rate_Per_100_Punches'] = location_summary.apply(
        lambda row: (row['Total_Single_Punch_Days_Location'] / row['Total_Original_Punches']) * 100 if row['Total_Original_Punches'] > 0 else 0,
        axis=1
    )
    location_summary['Multi_Punch_Rate_Per_100_Punches'] = location_summary.apply(
        lambda row: (row['Total_More_Than_4_Punches_Days_Location'] / row['Total_Original_Punches']) * 100 if row['Total_Original_Punches'] > 0 else 0,
        axis=1
    )

    # Format timedelta columns for display
    location_summary['Total Shift Duration (Location)'] = location_summary['Total_Shift_Duration_Location_TD'].apply(format_timedelta_to_hms)
    location_summary['Total Overtime Hours (Location)'] = location_summary['Total_Overtime_Location_TD'].apply(format_timedelta_to_hms)
    location_summary['Total Under-Time Hours (Location)'] = location_summary['Total_Under_Time_Location_TD'].apply(format_timedelta_to_hms)

    # Calculate Avg Shift Duration Per Employee AT THIS LOCATION
    location_summary['Avg Shift Duration Per Employee (Location)'] = location_summary.apply(
        lambda row: format_timedelta_to_hms(row['Total_Shift_Duration_Location_TD'] / row['Total_Location_Punch_Days']) if row['Total_Location_Punch_Days'] > 0 else '00:00:00',
        axis=1
    )

    # Select and reorder columns for display
    location_summary = location_summary[[
        'Source_Name', 'Total_Employees', 'Total_Location_Punch_Days', 'Total_Original_Punches',
        'Total Shift Duration (Location)', 'Avg Shift Duration Per Employee (Location)',
        'Total Overtime Hours (Location)', 'Total Under-Time Hours (Location)',
        'Total_Single_Punch_Days_Location', 'Single_Punch_Rate_Per_100_Punches',
        'Total_More_Than_4_Punches_Days_Location', 'Multi_Punch_Rate_Per_100_Punches'
    ]]
    return location_summary

def calculate_location_absenteeism_rates(summary_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates absenteeism rate per location based on employee summaries.
    Assumes each employee's 'Source_Names' first entry is their primary location.
    """
    if summary_df.empty:
        return pd.DataFrame(columns=['Source_Name', 'Total_Expected_Working_Days_Location_Agg', 'Total_Absent_Days_Location_Agg', 'Absenteeism_Rate_Location'])

    # Prepare a DataFrame that maps each employee to their first listed location and relevant totals
    emp_location_data = summary_df.copy()
    emp_location_data['Primary_Location'] = emp_location_data['Source_Names'].apply(lambda x: x.split(', ')[0] if x else 'N/A')

    # Aggregate by primary location
    location_absenteeism = emp_location_data.groupby('Primary_Location').agg(
        Total_Expected_Working_Days_Location_Agg=('Total_Expected_Working_Days_In_Period', 'sum'),
        Total_Absent_Days_Location_Agg=('Total_Absent_Days', 'sum')
    ).reset_index().rename(columns={'Primary_Location': 'Source_Name'})

    # Calculate absenteeism rate
    location_absenteeism['Absenteeism_Rate_Location'] = location_absenteeism.apply(
        lambda row: (row['Total_Absent_Days_Location_Agg'] / row['Total_Expected_Working_Days_Location_Agg']) * 100 if row['Total_Expected_Working_Days_Location_Agg'] > 0 else 0,
        axis=1
    )
    return location_absenteeism[['Source_Name', 'Absenteeism_Rate_Location']]


def calculate_top_locations_by_metric(location_overview_df: pd.DataFrame, metric_col: str, higher_is_worse: bool = True) -> str:
    """
    Identifies the top location for a given metric.
    """
    if location_overview_df.empty or metric_col not in location_overview_df.columns:
        return "N/A"

    if 'Rate' in metric_col: # Handle rates (higher is worse by default)
        if higher_is_worse:
            top_location_row = location_overview_df.loc[location_overview_df[metric_col].idxmax()]
        else:
            top_location_row = location_overview_df.loc[location_overview_df[metric_col].idxmin()]
        
        value = top_location_row[metric_col]
        return f"{top_location_row['Source_Name']} ({value:.2f}%)"
    
    elif 'Hours' in metric_col: # Handle hours (convert to total_seconds then to hours)
        # Ensure the column is converted to timedelta before operations
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
    """
    if summary_df.empty or location_summary_df.empty:
        return pd.DataFrame(columns=['No.', 'Name', 'Primary Location', 
                                     'Employee Present Days', 'Location Avg Present Days', 'Present Days Deviation',
                                     'Employee Avg Shift Duration', 'Location Avg Shift Duration', 'Avg Shift Deviation',
                                     'Employee Total OT Hours (H)', 'Location Avg OT Hours (H)', 'OT Hours Deviation',
                                     'Employee Total UT Hours (H)', 'Location Avg UT Hours (H)', 'UT Hours Deviation'])

    comparison_data = []

    # Prepare location averages for easy lookup
    location_avg_map = {}
    for _, loc_row in location_summary_df.iterrows():
        # Convert string durations to timedelta for consistent comparison
        avg_shift_td = pd.to_timedelta(loc_row['Avg Shift Duration Per Employee (Location)'])
        total_ot_td = pd.to_timedelta(loc_row['Total Overtime Hours (Location)'])
        total_ut_td = pd.to_timedelta(loc_row['Total Under-Time Hours (Location)'])

        # Calculate average present days per employee for the location
        loc_total_employees = loc_row['Total_Employees']
        loc_total_present_days = loc_row['Total_Location_Punch_Days']
        avg_present_days_loc = loc_total_present_days / loc_total_employees if loc_total_employees > 0 else 0


        location_avg_map[loc_row['Source_Name']] = {
            'Avg_Present_Days': avg_present_days_loc,
            'Avg_Shift_Duration_td': avg_shift_td,
            'Total_OT_Hours_td': total_ot_td,
            'Total_UT_Hours_td': total_ut_td
        }

    for _, emp_row in summary_df.iterrows():
        employee_no = emp_row['No.']
        employee_name = emp_row['Name']
        
        # Use the first mentioned Source_Name as the primary location for comparison
        primary_location = emp_row['Source_Names'].split(', ')[0] if emp_row['Source_Names'] else 'N/A'

        if primary_location in location_avg_map:
            loc_avg = location_avg_map[primary_location]

            # Employee's actual values (convert durations from string back to timedelta)
            emp_present_days = emp_row['Total_Present_Days']
            emp_avg_shift_td = pd.to_timedelta(emp_row['Average Shift Duration'])
            emp_total_ot_td = pd.to_timedelta(emp_row['Total Overtime Hours'])
            emp_total_ut_td = pd.to_timedelta(emp_row['Total Under-Time Hours'])

            # Calculate deviations
            present_days_dev = emp_present_days - loc_avg['Avg_Present_Days']
            avg_shift_dev_td = emp_avg_shift_td - loc_avg['Avg_Shift_Duration_td']
            ot_hours_dev_td = emp_total_ot_td - loc_avg['Total_OT_Hours_td']
            ut_hours_dev_td = emp_total_ut_td - loc_avg['Total_UT_Hours_td']
            
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
                'Employee Total OT Hours (H)': round(emp_total_ot_td.total_seconds() / 3600, 1),
                'Location Avg OT Hours (H)': round(loc_avg['Total_OT_Hours_td'].total_seconds() / 3600, 1),
                'OT Hours Deviation': round(ot_hours_dev_td.total_seconds() / 3600, 1),
                'Employee Total UT Hours (H)': round(emp_total_ut_td.total_seconds() / 3600, 1),
                'Location Avg UT Hours (H)': round(loc_avg['Total_UT_Hours_td'].total_seconds() / 3600, 1),
                'UT Hours Deviation': round(ut_hours_dev_td.total_seconds() / 3600, 1)
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
                'Employee Total OT Hours (H)': round(pd.to_timedelta(emp_row['Total Overtime Hours']).total_seconds() / 3600, 1),
                'Location Avg OT Hours (H)': 'N/A', 'OT Hours Deviation': 'N/A',
                'Employee Total UT Hours (H)': round(pd.to_timedelta(emp_row['Total Under-Time Hours']).total_seconds() / 3600, 1),
                'Location Avg UT Hours (H)': 'N/A', 'UT Hours Deviation': 'N/A'
            })

    return pd.DataFrame(comparison_data)


def generate_location_recommendations(location_overview_df: pd.DataFrame, absenteeism_df: pd.DataFrame) -> dict:
    """
    Generates text-based recommendations for each location based on aggregated metrics.
    """
    recommendations = {}
    if location_overview_df.empty:
        return recommendations

    # Merge absenteeism rates into the location_overview_df for easier access
    merged_df = location_overview_df.merge(absenteeism_df, on='Source_Name', how='left')

    # Ensure 'Absenteeism_Rate_Location' column exists before operations
    if 'Absenteeism_Rate_Location' not in merged_df.columns:
        merged_df['Absenteeism_Rate_Location'] = 0.0 # Default to 0.0 if column is missing

    merged_df['Absenteeism_Rate_Location'] = merged_df['Absenteeism_Rate_Location'].fillna(0) # Fill NaN if no absenteeism data

    # Define thresholds for generating recommendations (can be configurable)
    ABSENTEEISM_THRESHOLD = 10  # %
    OVERTIME_HOURS_THRESHOLD_PER_EMPLOYEE = 20 # hours per employee per period
    UNDERTIME_HOURS_THRESHOLD_PER_EMPLOYEE = 15 # hours per employee per period
    SINGLE_PUNCH_RATE_THRESHOLD = 5 # % of total punches
    MULTI_PUNCH_RATE_THRESHOLD = 5 # % of total punches

    for _, row in merged_df.iterrows():
        location_name = row['Source_Name']
        loc_recs = []

        # Convert timedelta strings to seconds/hours for numerical comparison
        total_ot_hours_loc = pd.to_timedelta(row['Total Overtime Hours (Location)']).total_seconds() / 3600
        total_ut_hours_loc = pd.to_timedelta(row['Total Under-Time Hours (Location)']).total_seconds() / 3600
        
        # Calculate per-employee averages for thresholds
        num_employees = row['Total_Employees'] if row['Total_Employees'] > 0 else 1 # Avoid division by zero
        avg_ot_per_employee = total_ot_hours_loc / num_employees
        avg_ut_per_employee = total_ut_hours_loc / num_employees

        # Absenteeism recommendation
        if row['Absenteeism_Rate_Location'] > ABSENTEEISM_THRESHOLD:
            loc_recs.append(f"- High absenteeism rate ({row['Absenteeism_Rate_Location']:.1f}%). Consider reviewing attendance policies or reasons for frequent absences.")
        
        # Overtime recommendation
        if avg_ot_per_employee > OVERTIME_HOURS_THRESHOLD_PER_EMPLOYEE:
            loc_recs.append(f"- Significant overtime recorded ({avg_ot_per_employee:.1f} hrs/employee). Investigate workload distribution or staffing needs.")

        # Under-time recommendation
        if avg_ut_per_employee > UNDERTIME_HOURS_THRESHOLD_PER_EMPLOYEE:
            loc_recs.append(f"- Notable under-time hours ({avg_ut_per_employee:.1f} hrs/employee). Look into reasons for short shifts or early departures.")

        # Single punch rate recommendation
        if row['Single_Punch_Rate_Per_100_Punches'] > SINGLE_PUNCH_RATE_THRESHOLD:
            loc_recs.append(f"- High single punch rate ({row['Single_Punch_Rate_Per_100_Punches']:.1f}% of punches). This may indicate missed punches; review punch-in/out procedures or device reliability.")
        
        # Multiple punch rate recommendation
        if row['Multi_Punch_Rate_Per_100_Punches'] > MULTI_PUNCH_RATE_THRESHOLD:
            loc_recs.append(f"- High multiple punch rate ({row['Multi_Punch_Rate_Per_100_Punches']:.1f}% of punches). Investigate reasons for frequent entries/exits (e.g., breaks, specific tasks, system issues).")

        if loc_recs:
            recommendations[location_name] = loc_recs
    
    return recommendations


# --- Streamlit page function for the Fingerprint Report Generator ---
def fingerprint_report_page():
    """
    Displays the fingerprint report generator functionality in Streamlit.
    Allows users to upload multiple CSV/Excel files and download an Excel report.
    Includes new tabs for detailed, summary, and analysis reports.
    """
    st.title("📊 Employee Fingerprint Report Generator")
    st.info("⬆️ Upload one or more CSV or Excel files containing employee fingerprint data.")

    # Company selection dropdown
    company_names = list(COMPANY_CONFIGS.keys())
    selected_company_name = st.selectbox(
        "Select Company:",
        options=company_names,
        key="company_selection"
    )

    # Initialize a counter in session state to control the file uploader's key
    if 'uploader_key_counter' not in st.session_state:
        st.session_state.uploader_key_counter = 0
    # Initialize a flag to indicate if data has been successfully processed and displayed
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


    # Create the file uploader with a dynamic key
    uploaded_files = st.file_uploader(
        "Select fingerprint files (.csv, .xls, .xlsx)",
        type=["csv", "xls", "xlsx"],
        accept_multiple_files=True,
        key=f"fingerprint_file_uploader_{st.session_state.uploader_key_counter}" # Dynamic key
    )

    # Text input for custom filename
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
        # Add the "New Files" button
        if st.button("🔄 New Files (Clear and Reset)", key="new_files_button"):
            st.session_state.uploader_key_counter += 1
            st.session_state.processed_data_present = False
            st.session_state.detailed_report_df_cache = pd.DataFrame()
            st.session_state.summary_report_df_cache = pd.DataFrame()
            st.session_state.error_log_df_cache = pd.DataFrame()
            st.session_state.download_filename_cache = "Employee_Punch_Reports.xlsx"
            st.session_state.global_min_date_cache = None
            st.session_state.global_max_date_cache = None
            st.rerun() 

    # Process and display logic, triggered by the "Generate Reports" button and presence of files
    if generate_button and uploaded_files:
        st.session_state.processed_data_present = True
        with st.spinner("Processing files and generating reports... This may take a moment."):
            detailed_report_df, error_log, global_min_date, global_max_date = calculate_shift_durations_from_uploads(uploaded_files, selected_company_name)
            
            st.session_state.detailed_report_df_cache = detailed_report_df
            st.session_state.global_min_date_cache = global_min_date
            st.session_state.global_max_date_cache = global_max_date

            if global_min_date and global_max_date and not detailed_report_df.empty:
                st.session_state.summary_report_df_cache = generate_summary_report(
                    detailed_report_df.copy(), 
                    selected_company_name,
                    global_min_date,      
                    global_max_date
                )
            else:
                st.session_state.summary_report_df_cache = pd.DataFrame()

            error_log_df_for_cache = pd.DataFrame(error_log)
            if error_log_df_for_cache.empty:
                error_log_df_for_cache = pd.DataFrame([{'Filename': 'N/A', 'Error': 'No errors recorded during file processing.'}])
            st.session_state.error_log_df_cache = error_log_df_for_cache
            
            st.session_state.download_filename_cache = f"{custom_filename.strip()}.xlsx" if custom_filename.strip() else f"{default_filename}.xlsx"

            st.rerun() 
    elif uploaded_files is None and not st.session_state.processed_data_present:
        st.info("Please upload your fingerprint files to start the report generation.")
    
    # Display results and download buttons only if data has been processed (flag is true)
    if st.session_state.processed_data_present:
        detailed_report_df = st.session_state.detailed_report_df_cache
        summary_report_df = st.session_state.summary_report_df_cache
        error_log_df = st.session_state.error_log_df_cache
        download_filename = st.session_state.download_filename_cache

        tab1, tab2, tab3 = st.tabs(["Detailed Report", "Summary Report", "Analysis & Insights"])

        with tab1:
            if not detailed_report_df.empty:
                if st.session_state.global_min_date_cache and st.session_state.global_max_date_cache:
                    st.success(f"✅ Successfully processed data for {len(detailed_report_df)} daily records! Overall Reporting Period: {st.session_state.global_min_date_cache.strftime('%Y-%m-%d')} to {st.session_state.global_max_date_cache.strftime('%Y-%m-%d')}")
                else:
                    st.success(f"✅ Successfully processed data for {len(detailed_report_df)} daily records!")
                
                st.subheader("📋 Detailed Report Preview")
                st.dataframe(detailed_report_df.sample(20), use_container_width=True)
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
                # Generate location summary and absenteeism rates
                location_summary_df = generate_location_summary(detailed_report_df.copy())
                location_absenteeism_df = calculate_location_absenteeism_rates(summary_report_df.copy())
                
                # Merge location summary with absenteeism rates for comprehensive overview
                location_overview_for_display = location_summary_df.merge(location_absenteeism_df, on='Source_Name', how='left')
                location_overview_for_display['Absenteeism_Rate_Location'] = location_overview_for_display['Absenteeism_Rate_Location'].fillna(0).round(1) # Fill NaN and format

                st.markdown("---")
                st.markdown("#### 🏢 Location Overviews & Headcounts")
                if not location_overview_for_display.empty:
                    st.info("This table summarizes key metrics and headcounts for each location, including absenteeism rates and punch behaviors.")
                    # Reorder columns for better readability
                    display_cols = [
                        'Source_Name', 'Total_Employees', 'Total_Location_Punch_Days', 'Total_Original_Punches',
                        'Absenteeism_Rate_Location',
                        'Total Shift Duration (Location)', 'Avg Shift Duration Per Employee (Location)',
                        'Total Overtime Hours (Location)', 'Total Under-Time Hours (Location)',
                        'Total_Single_Punch_Days_Location', 'Single_Punch_Rate_Per_100_Punches',
                        'Total_More_Than_4_Punches_Days_Location', 'Multi_Punch_Rate_Per_100_Punches'
                    ]
                    # Only include columns that actually exist in the DataFrame
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
                        st.metric("Highest Total Overtime", calculate_top_locations_by_metric(location_overview_for_display, 'Total Overtime Hours (Location)'))
                    with col_t2:
                        st.metric("Highest Under-Time", calculate_top_locations_by_metric(location_overview_for_display, 'Total Under-Time Hours (Location)'))
                        st.metric("Highest Single Punch Rate", calculate_top_locations_by_metric(location_overview_for_display, 'Single_Punch_Rate_Per_100_Punches'))
                    with col_t3:
                        st.metric("Highest Multiple Punch Rate", calculate_top_locations_by_metric(location_overview_for_display, 'Multi_Punch_Rate_Per_100_Punches'))
                        st.metric("Highest Headcount", calculate_top_locations_by_metric(location_overview_for_display, 'Total_Employees'))
                else:
                    st.info("Location data is needed to identify top locations.")


                st.markdown("---")
                st.markdown("#### 📊 Company-Wide Averages")
                if not summary_report_df.empty:
                    # Calculate overall averages from the summary report
                    avg_total_present_days = summary_report_df['Total_Present_Days'].mean()
                    
                    avg_total_shift_durations_seconds = summary_report_df['Total Shift Durations'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else pd.NaT).dt.total_seconds().sum()
                    avg_total_shift_duration = avg_total_shift_durations_seconds / summary_report_df['Total_Present_Days'].sum() if summary_report_df['Total_Present_Days'].sum() > 0 else 0
                    
                    avg_total_overtime_hours_seconds = summary_report_df['Total Overtime Hours'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else pd.NaT).dt.total_seconds().sum()
                    avg_total_overtime_hours = avg_total_overtime_hours_seconds / 3600
                    
                    avg_total_under_time_hours_seconds = summary_report_df['Total Under-Time Hours'].apply(lambda x: pd.to_timedelta(x) if isinstance(x, str) else pd.NaT).dt.total_seconds().sum()
                    avg_total_under_time_hours = avg_total_under_time_hours_seconds / 3600

                    col_c1, col_c2, col_c3 = st.columns(3)
                    with col_c1:
                        st.metric("Avg Present Days per Employee", f"{avg_total_present_days:.1f}")
                    with col_c2:
                        st.metric("Avg Shift Duration per Day", format_timedelta_to_hms(pd.Timedelta(seconds=avg_total_shift_duration)))
                    with col_c3:
                        st.metric("Avg Total Overtime Hours", f"{avg_total_overtime_hours:.1f} hrs")
                        st.metric("Avg Total Under-Time Hours", f"{avg_total_under_time_hours:.1f} hrs")
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
                            st.markdown("") # Add a blank line for spacing
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
                consecutive_absences_df = analyze_consecutive_absences(detailed_report_df.copy())
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

        # Error Log Display (moved to its own section, always available)
        if not error_log_df.empty:
            st.markdown("---") # Separator
            st.subheader("❌ Error Log")
            st.dataframe(error_log_df, use_container_width=True)

        # Download button always visible if data present
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

                consecutive_absences_df = analyze_consecutive_absences(detailed_report_df.copy())
                unusual_shifts_df = analyze_unusual_shift_durations(detailed_report_df.copy(), selected_company_name)
                employee_vs_location_avg_df = analyze_employee_vs_location_averages(summary_report_df.copy(), location_summary_df.copy())


                if not location_overview_for_excel.empty: # Save the combined location overview
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
            # If no detailed report, only offer to download the error log if it has content
            if not error_log_df.empty and not error_log_df.iloc[0]['Error'] == 'No errors recorded during file processing.':
                 error_log_output_buffer = io.BytesIO()
                 with pd.ExcelWriter(error_log_output_buffer, engine='openpyxl') as writer:
                    error_log_df.to_excel(writer, sheet_name='Error Log', index=False)
                 
                 st.download_button(
                    label="📥 Download Error Log (Excel)",
                    data=error_log_output_buffer.getvalue(),
                    file_name=f"{custom_filename.strip()}_Error_Log.xlsx" if custom_filename.strip() else "Error_Log.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="secondary"
                )
