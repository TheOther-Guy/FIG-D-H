import calendar
from datetime import timedelta # Added this import
import pandas as pd

# --- COMPANY-SPECIFIC CONFIGURATIONS ---
# Define rules for each company.
# Each company can have default rules, location-specific overrides, and employee-specific overrides.
# calendar module constants (0=Monday, 6=Sunday)
COMPANY_CONFIGS = {
    "Al-hadabah times": {
        "default_rules": {
            "standard_shift_hours": 8,
            "short_t_threshold_hours": 7.5, # Employee is "missing" if total shift < this
            "more_t_start_hours": 9,        # More_T is calculated for hours > this
            "more_t_enabled": True,        # Global flag for More_T calculation for this company/location/employee
            "is_rotational_off": False,       # Default for fixed shifts
            "weekend_days": [calendar.FRIDAY], # Default for Al-hadabah if no specific location rule, assuming 1 Friday
            "fixed_break_deduction_minutes": 0, # Default to 0, no fixed break
            "fixed_break_threshold_hours": 0 # Default to 0, no fixed break threshold
        },
        "location_rules": { # Rules specific to `Source_Name` (derived from filename/device)
            "HO": {
                "weekend_days": [calendar.FRIDAY, calendar.SATURDAY], # These are potential weekend days for alternating rule
                "weekend_rule_type": "alternating_f_fs", # Specific rule for alternating weekends (F then F+S)
                "more_t_enabled": False,
                "is_rotational_off": False
            },
            "Warehouse": {"weekend_days": [calendar.FRIDAY], "is_rotational_off": False},
            "lighting plus": {"weekend_days": [calendar.FRIDAY], "more_t_enabled": False, "is_rotational_off": False},
            "S16": {"weekend_days": [calendar.FRIDAY], "more_t_enabled": False, "is_rotational_off": False},
            "S17": {"weekend_days": [calendar.FRIDAY], "more_t_enabled": False, "is_rotational_off": False},
            "S20": {"weekend_days": [calendar.FRIDAY], "more_t_enabled": False, "is_rotational_off": False},
            "S21": {"weekend_days": [calendar.FRIDAY], "more_t_enabled": False, "is_rotational_off": False},
            "S33": {"weekend_days": [calendar.FRIDAY], "more_t_start_hours": 8, "more_t_enabled": True, "is_rotational_off": False}, # Work all week
            "S14": {"weekend_days": [], "more_t_start_hours": 8, "more_t_enabled": True, "is_rotational_off": False}, # Work all week
            "S39": {"weekend_days": [], "more_t_start_hours": 8, "more_t_enabled": True, "is_rotational_off": False}, # Work all week
            "S40": {"weekend_days": [], "more_t_start_hours": 8, "more_t_enabled": True, "is_rotational_off": False}, # Work all week
            "S41": {"weekend_days": [], "more_t_start_hours": 8, "more_t_enabled": True, "is_rotational_off": False}, # Work all week
            "S42": {"weekend_days": [], "more_t_start_hours": 8, "more_t_enabled": True, "is_rotational_off": False}, # Work all week
            "Al hadabah Drivers": {"weekend_days": [], "more_t_start_hours": 8, "more_t_enabled": True, "is_rotational_off": False}, # Work all week
        }
    },
    "D&H": {
        "default_rules": {
            "standard_shift_hours": 8,
            "short_t_threshold_hours": 7.5,
            "more_t_start_hours": 9,
            "more_t_enabled": True,
            "weekend_days": [calendar.FRIDAY], # Default for D&H
            "is_rotational_off": False,
            "fixed_break_deduction_minutes": 0, # Default to 0, no fixed break
            "fixed_break_threshold_hours": 0 # Default to 0, no fixed break threshold
        },
        "employee_overrides": { # Rules specific to employee 'No.' (for Brand Managers)
            # These are Brand Managers who can have rotational offs and no More_T
            "1031": {"more_t_enabled": False, "is_rotational_off": True, "weekend_days": [], "rotational_days_off_per_week": 1}, # Ali Dagher (D&H)
            "12299": {"more_t_enabled": False, "is_rotational_off": True, "weekend_days": [], "rotational_days_off_per_week": 1}, # Fata (D&H)
            "2579": {"more_t_enabled": False, "is_rotational_off": True, "weekend_days": [], "rotational_days_off_per_week": 1},  # Aline Armani (D&H)
            "1494": {"more_t_enabled": False, "is_rotational_off": True, "weekend_days": [], "rotational_days_off_per_week": 1}, # Raeda (D&H)
            "1483": {"more_t_enabled": False, "is_rotational_off": True, "weekend_days": [], "rotational_days_off_per_week": 1}  # Mayada Abou (D&H)
        },
        "location_rules": {
            "HO": {"weekend_days": [calendar.FRIDAY], "is_rotational_off": False},
            "Warehouse": {"weekend_days": [calendar.FRIDAY], "is_rotational_off": False}
        }
    },
    "D&co": {
        "default_rules": {
            "standard_shift_hours": 8,
            "short_t_threshold_hours": 7.5,
            "more_t_start_hours": 9,
            "more_t_enabled": True,
            "weekend_days": [calendar.FRIDAY], # Default for D&co
            "is_rotational_off": False,
            "fixed_break_deduction_minutes": 0, # Default to 0, no fixed break
            "fixed_break_threshold_hours": 0 # Default to 0, no fixed break threshold
        },
        "employee_overrides": {
            # No specific employee overrides for D&co now as BMs moved to D&H
        },
        "location_rules": {
            "DCO HO": {"weekend_days": [calendar.FRIDAY], "is_rotational_off": False},
            "Warehouse": {"weekend_days": [calendar.FRIDAY], "is_rotational_off": False},
            "Fashion SHW": {"weekend_days": [calendar.FRIDAY], "is_rotational_off": True, "rotational_days_off_per_week": 1},
        }
    },
    "Second Cup": { # Added as a top-level company based on provided data
        "default_rules": {
            "standard_shift_hours": 9,
            "short_t_threshold_hours": 8.5,
            "more_t_start_hours": 10, # Default opening hours for general Second Cup locations
            "more_t_enabled": True,
            "weekend_days": [], # Based on "Only Fridays" # the weekend rotaion to be edited for each location
            "is_rotational_off": False,
            "opening_hours_count" : 12, # Default to 9 hours for general Second Cup
            "fixed_break_deduction_minutes": 0, # Set to 0 for Second Cup as per user's request: "2 punches days has no breaks"
            "fixed_break_threshold_hours": 0 # Not relevant if fixed_break_deduction_minutes is 0
        },
        "location_rules": {
            "2nd cup Warehouse": {"weekend_days": [calendar.FRIDAY], "is_rotational_off": False},
            # 24-hour locations with specific rules
            "Dar al Shifa": {
                "weekend_days": [],
                "is_rotational_off": True,
                "opening_hours_count": 24,
                "is_24_hour_location": True # Flag to trigger 24-hour specific logic
            },
            "Dar al Shifa Clinic": {
                "weekend_days": [],
                "is_rotational_off": True,
                "opening_hours_count": 24,
                "is_24_hour_location": True
            },
            "Farwaniya Hospital": {
                "weekend_days": [],
                "is_rotational_off": True,
                "opening_hours_count": 24,
                "is_24_hour_location": True
            },
            "Bustan": {
                "weekend_days": [],
                "is_rotational_off": True,
                "opening_hours_count": 24,
                "is_24_hour_location": True
            },
            "Jahar Hospital": {
                "weekend_days": [],
                "is_rotational_off": True,
                "opening_hours_count": 24,
                "is_24_hour_location": True
            },
            "Khaitan": {
                "weekend_days": [],
                "is_rotational_off": True,
                "opening_hours_count": 24,
                "is_24_hour_location": True
            },
            "Capital Governorate": {
                "weekend_days": [],
                "is_rotational_off": True,
                "opening_hours_count": 24,
                "is_24_hour_location": True
            },
            # 12-hour locations
            "Admin Science": {
                "standard_shift_hours": 12,
                "short_t_threshold_hours": 11,
                "more_t_start_hours": 13,
            },
            "Life Science": {
                "standard_shift_hours": 12,
                "short_t_threshold_hours": 11,
                "more_t_start_hours": 13,
            },
            "College of Science": {
                "standard_shift_hours": 12,
                "short_t_threshold_hours": 11,
                "more_t_start_hours": 13,
            },
            "Edu Boys": {
                "standard_shift_hours": 12,
                "short_t_threshold_hours": 11,
                "more_t_start_hours": 13,
            },
            "Edu Girls": {
                "standard_shift_hours": 12,
                "short_t_threshold_hours": 11,
                "more_t_start_hours": 13,
            },
            "Edu Girls 2": {
                "standard_shift_hours": 12,
                "short_t_threshold_hours": 11,
                "more_t_start_hours": 13,
            },
            "Marina mall": {
                "standard_shift_hours": 12,
                "short_t_threshold_hours": 11,
                "more_t_start_hours": 13,
                "weekend_days": [],
            },
            "Boys PAAET": {
                "standard_shift_hours": 12,
                "short_t_threshold_hours": 11,
                "more_t_start_hours": 13,
            },
            "Nursing Girls": {
                "standard_shift_hours": 12,
                "short_t_threshold_hours": 11,
                "more_t_start_hours": 13,
            },
            "Nursing Boys": {
                "standard_shift_hours": 12,
                "short_t_threshold_hours": 11,
                "more_t_start_hours": 13,
            },
            "Makki Juma": {
                "standard_shift_hours": 12,
                "short_t_threshold_hours": 11,
                "more_t_start_hours": 13,
            },
            "International Hospital": {
                "weekend_days": [],
                "standard_shift_hours": 8,
                "short_t_threshold_hours": 11,
                "more_t_start_hours": 13,
            },
            # Locations with Friday and Saturday weekends, inheriting other defaults
            "Admin Science": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "Life Science": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "College of Science": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "Edu Boys": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "Edu Girls": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "Boys PAAET": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "BEAUTY AND TRAVEL": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "PAAET Admin": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "Edu Girls 2": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "Nursing Girls": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "Nursing Boys": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "CIT-SABA SALEM": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "Police Force": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "CIT-SABA SALEM": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "Edu Boys PAAET": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "Admin Tower PAAET": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "Capital Governorate": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            "Khaitan": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},

            # "Badriya Hospital": {"weekend_days": [calendar.FRIDAY, calendar.SATURDAY]},
            
        }
    }
}
# --- END COMPANY-SPECIFIC CONFIGURATIONS ---

def normalize_employee_id(emp_id) -> str:
    """
    Robustly normalizes employee IDs to a standard string format.
    Handles:
      - Floats: 1084.0 -> '1084'
      - Integers: 1084 -> '1084'
      - Strings: ' 1084 ' -> '1084', '1084.0' -> '1084'
      - None/NaN: -> ''
    """
    if pd.isna(emp_id):
        return ""
    
    s = str(emp_id).strip()
    
    # Handle '1084.0' specifically
    if '.' in s:
        try:
            # Try to convert to float then to int to remove .0
            f = float(s)
            if f.is_integer():
                return str(int(f))
        except (ValueError, TypeError):
            pass
            
    return s

# --- FILE-SPECIFIC DATE FORMATS ---
# Maps Source_Name (derived from filename) to its specific datetime format string.
# These formats are tried first for matching files.
FILE_DATE_FORMATS = {
    "Benetone Mohalab BM": '%d-%b-%y %I:%M:%S %p',
    "Benetone Mohalab Vm": '%d-%b-%y %I:%M:%S %p',
    "Benetone Mohalab": '%d-%b-%y %I:%M:%S %p',
    "BM D&H Dagher": '%m/%d/%Y %I:%M:%S %p',
    "Celio Marina BM": '%m/%d/%Y %I:%M:%S %p',
    "Celio Marina VM": '%m/%d/%Y %I:%M:%S %p',
    "Celio Marina": '%m/%d/%Y %I:%M:%S %p', # files recveived has 2x space in the middle
    "Celio Warehouse": '%m/%d/%Y %I:%M:%S %p',
    "D&H Dagher Vm": '%m/%d/%Y %I:%M:%S %p',
    "D&H HO": '%m/%d/%Y %I:%M:%S %p',
    "D&H Warehouse": '%m/%d/%Y %I:%M:%S %p',
    "Designer Avenue": '%m/%d/%Y %I:%M:%S %p',
    "Etam 360": '%m/%d/%Y %I:%M:%S %p',
    "Etam 360 Vm": '%d/%m/%Y %I:%M:%S %p',
    "Etam Avenue": '%m/%d/%Y %I:%M:%S %p',
    "Etam Gatemall": '%m/%d/%Y %I:%M:%S %p',
    "Etam Marina": '%m/%d/%Y %I:%M:%S %p',
    "Etam Warehouse": '%m/%d/%Y %I:%M:%S %p',
    "FD Al Bahar BM": '%m/%d/%Y %I:%M:%S %p',
    "FD Al Bahar Vm": '%m/%d/%Y %I:%M:%S %p',
    "FD Boulevard Bm": '%d/%m/%y %I:%M:%S %p',
    "FD Boulevard Vm": '%d/%m/%y %I:%M:%S %p',
    "Head OFfice VM": '%d/%m/%Y %I:%M:%S %p',
    "Lipsy Mohalab": '%d-%b-%y %I:%M:%S %p',
    "Spring Field": '%m/%d/%Y %I:%M:%S %p', # files received with "field" while we use "Field"
    "TT Mohalab": '%d-%b-%y %I:%M:%S %p',
    "Ws Koutmall": '%m/%d/%Y %I:%M:%S %p',
    "Ws 360 Vm": '%d-%b-%y %I:%M:%S %p',
    "Ws 360": '%m/%d/%Y %I:%M:%S %p',
    "Ws Avenue": '%m/%d/%Y %I:%M:%S %p',
    "Ws Gatemall": '%m/%d/%Y %I:%M:%S %p',
    "Ws Mohalab": '%d-%b-%y %I:%M:%S %p',
    "Ws Olympia": '%m/%d/%Y %I:%M:%S %p',
    "Ws Sharq Vm": '%m/%d/%Y %I:%M:%S %p',
    "Ws Sharq": '%m/%d/%Y %I:%M:%S %p',
    "Yammay Avenue": '%m/%d/%Y %I:%M:%S %p',
    "BM FD Boulevard": '%d/%m/%y %I:%M:%S %p',
    "Bm Ws sharq": '%m/%d/%Y %I:%M:%S %p',
    "DCO HO": '%m/%d/%Y %I:%M:%S %p',
    "Yammay Al koutmall": '%m/%d/%Y %I:%M:%S %p',


    # alhadaba
    "Doha Store": '%m/%d/%Y %I:%M:%S %p',
    "Hawally Warehouse ( Hadabah )": '%m/%d/%Y %I:%M:%S %p',
    "Doha Store Warehouse": '%d/%m/%Y %I:%M:%S %p',
    "Hadaba HO": '%m/%d/%Y %I:%M:%S %p',
    "Lighting Plus": '%m/%d/%Y %I:%M:%S %p',
    "S14": '%m/%d/%Y %I:%M:%S %p',
    "S16": '%m/%d/%Y %I:%M:%S %p',
    "S17": '%m/%d/%Y %I:%M:%S %p',
    "S20": '%m/%d/%Y %I:%M:%S %p',
    "S21": '%m/%d/%Y %I:%M:%S %p',
    "S33": '%m/%d/%Y %I:%M:%S %p',
    "S39": '%m/%d/%Y %I:%M:%S %p',
    "S40": '%m/%d/%Y %I:%M:%S %p',
    "S41": '%m/%d/%Y %I:%M:%S %p',
    "S42": '%m/%d/%Y %I:%M:%S %p',
    "Al hadabah Drivers": '%m/%d/%Y %I:%M:%S %p',

    # 2nd cup
    "2nd cup Warehouse": '%m/%d/%Y %I:%M:%S %p',
    "Admin Science": '%m/%d/%Y %I:%M:%S %p',
    "Badriya Hospital": '%m/%d/%Y %I:%M:%S %p',
    "Boys PAAET": '%m/%d/%Y %I:%M:%S %p',
    "Bustan": '%m/%d/%Y %I:%M:%S %p',
    "College of Science": '%m/%d/%Y %I:%M:%S %p',
    "Dar al Shifa Clinic": '%m/%d/%Y %I:%M:%S %p',
    "Dar al Shifa": '%m/%d/%Y %I:%M:%S %p',
    "Edu Boys": '%m/%d/%Y %I:%M:%S %p',
    "Edu Girls 2": '%m/%d/%Y %I:%M:%S %p',
    "Edu Girls": '%m/%d/%Y %I:%M:%S %p',
    "Farwaniya Hospital": '%m/%d/%Y %I:%M:%S %p',
    "Homz Mall": '%m/%d/%Y %I:%M:%S %p',
    "IC Salmiya": '%m/%d/%Y %I:%M:%S %p',
    "International Hospital": '%m/%d/%Y %I:%M:%S %p',
    "Jaber Hospital": '%m/%d/%Y %I:%M:%S %p',
    "Jahar Hospital": '%m/%d/%Y %I:%M:%S %p',
    "Life Science": '%m/%d/%Y %I:%M:%S %p',
    "Makki Juma": '%m/%d/%Y %I:%M:%S %p',
    "Marina Mall": '%m/%d/%Y %I:%M:%S %p',
    "Mohalab": '%m/%d/%Y %I:%M:%S %p',
    "MOI": '%m/%d/%Y %I:%M:%S %p',
    "Nursing Boys": '%m/%d/%Y %I:%M:%S %p',
    "Nursing Girls": '%m/%d/%Y %I:%M:%S %p',
    "PAAET Admin": '%m/%d/%Y %I:%M:%S %p',
    "Scup Vm": '%m/%d/%Y %I:%M:%S %p',
    "BEAUTY AND TRAVEL": '%m/%d/%Y %I:%M:%S %p',
    "CIT": '%m/%d/%Y %I:%M:%S %p',
    "Edu Boys PAAET": '%m/%d/%Y %I:%M:%S %p',
    "Khaitan": '%m/%d/%Y %I:%M:%S %p',
    "Capital Governorate": '%m/%d/%Y %I:%M:%S %p',
    "Police Force": '%m/%d/%Y %I:%M:%S %p',
    "Adan Hospital": '%m/%d/%Y %I:%M:%S %p',


    # D&Co
    "BEBE Olympia": '%m/%d/%Y %I:%M:%S %p',
    "BYL Mohalab": '%d-%b-%y %I:%M:%S %p',
    "BYL 360": '%m/%d/%Y %I:%M:%S %p',
    "BYL Avenue": '%m/%d/%Y %I:%M:%S %p',
    "BYL Koutmall": '%m/%d/%Y %I:%M:%S %p',
    "FD Al Bahar": '%m/%d/%Y %I:%M:%S %p',
    "FD Boulevard": '%d/%m/%y %I:%M:%S %p',
    "FD Olympia": '%m/%d/%Y %I:%M:%S %p',
    "Hunkemoller": '%m/%d/%Y %I:%M:%S %p',
    "LVER 360": '%m/%d/%Y %I:%M:%S %p',
    "LVER Avenue": '%m/%d/%Y %I:%M:%S %p',
    "LVER Koutmall": '%m/%d/%Y %I:%M:%S %p',
    "LVER Gatemall": '%m/%d/%Y %I:%M:%S %p',
    "LVER Olympia": '%m/%d/%Y %I:%M:%S %p',
    "LVER Al Raya": '%m/%d/%Y %I:%M:%S %p',
    "LVER Mohalab": '%d-%b-%y %I:%M:%S %p',
    "Menbur Avenue": '%m/%d/%Y %I:%M:%S %p',
    "DCO HO": '%m/%d/%Y %I:%M:%S %p',
    "Hunkemoller Avenue": '%m/%d/%Y %I:%M:%S %p',
}
# --- END FILE-SPECIFIC DATE FORMATS ---

# =====================================================================
# NUMERIC FILE NAME → LOCATION MAPPING
# =====================================================================

LOCATION_MAP = {
    "D&H": {
        "Benetone Mohalab BM": "01",
        "Benetone Mohalab Vm": "02",
        "Benetone Mohalab": "03",
        "BM D&H Dagher": "04",
        "Celio Marina BM": "05",
        "Celio Marina VM": "06",
        "Celio Marina": "07",
        "Celio Warehouse": "08",
        "D&H Dagher Vm": "09",
        "D&H HO": "10",
        "D&H Warehouse": "11",
        "Designer Avenue": "12",
        "Etam 360": "13",
        "Etam 360 Vm": "14",
        "Etam Avenue": "15",
        "Etam Gatemall": "16",
        "Etam Marina": "17",
        "Etam Warehouse": "18",
        "FD Al Bahar BM": "19",
        "FD Al Bahar Vm": "20",
        "FD Boulevard Bm": "21",
        "FD Boulevard Vm": "22",
        "Head OFfice VM": "23",
        "Lipsy Mohalab": "24",
        "Spring Field": "25",
        "TT Mohalab": "26",
        "Ws Koutmall": "27",
        "Ws 360 Vm": "28",
        "Ws 360": "29",
        "Ws Avenue": "30",
        "Ws Gatemall": "31",
        "Ws Mohalab": "32",
        "Ws Olympia": "33",
        "Ws Sharq Vm": "34",
        "Ws Sharq": "35",
        "Yammay Avenue": "36",
        "BM FD Boulevard": "37",
        "Bm Ws sharq": "38",
        "DCO HO": "39",
        "Yammay Al koutmall": "40",
    },
    "Al-hadabah times": {
        "Doha Store": "01",
        "Hawally Warehouse ( Hadabah )": "02",
        "Doha Store Warehouse": "03",
        "Hadaba HO": "04",
        "Lighting Plus": "05",
        "S14": "06",
        "S16": "07",
        "S17": "08",
        "S20": "09",
        "S21": "10",
        "S33": "11",
        "S39": "12",
        "S40": "13",
        "S41": "14",
        "S42": "15",
        "Al hadabah Drivers": "16",
    },
    "Second Cup": {
        "2nd cup Warehouse": "01",
        "Admin Science": "02",
        "Badriya Hospital": "03",
        "Boys PAAET": "04",
        "Bustan": "05",
        "College of Science": "06",
        "Dar al Shifa Clinic": "07",
        "Dar al Shifa": "08",
        "Edu Boys": "09",
        "Edu Girls 2": "10",
        "Edu Girls": "11",
        "Farwaniya Hospital": "12",
        "Homz Mall": "13",
        "IC Salmiya": "14",
        "International Hospital": "15",
        "Jaber Hospital": "16",
        "Jahar Hospital": "17",
        "Life Science": "18",
        "Makki Juma": "19",
        "Marina Mall": "20",
        "Mohalab": "21",
        "MOI": "22",
        "Nursing Boys": "23",
        "Nursing Girls": "24",
        "PAAET Admin": "25",
        "Scup Vm": "26",
        "BEAUTY AND TRAVEL": "27",
        "CIT": "28",
        "Edu Boys PAAET": "29",
        "Khaitan": "30",
        "Capital Governorate": "31",
        "Police Force": "32",
        "Adan Hospital": "33",
    },
    "D&co": {
        "BEBE Olympia": "01",
        "BYL Mohalab": "02",
        "BYL 360": "03",
        "BYL Avenue": "04",
        "BYL Koutmall": "05",
        "FD Al Bahar": "06",
        "FD Boulevard": "07",
        "FD Olympia": "08",
        "Hunkemoller": "09",
        "LVER 360": "10",
        "LVER Avenue": "11",
        "LVER Koutmall": "12",
        "LVER Gatemall": "13",
        "LVER Olympia": "14",
        "LVER Al Raya": "15",
        "LVER Mohalab": "16",
        "Menbur Avenue": "17",
        "DCO HO": "18",
        "Hunkemoller Avenue": "19",
    },
}



def resolve_location_from_numeric(filename: str):
    """
    Convert numeric filename like '111.xlsx' → real location name.
    Format: CLLL
        C   = company number (1,2,3,4)
        LLL = location number (no leading zeros)
    Returns the location name or None.
    """
    import os

    base = os.path.splitext(filename)[0].strip()

    # Must be numeric
    if not base.isdigit():
        return None

    # Company = first digit
    company = base[0]

    # Location code = rest
    location = base[1:]
    if not location:
        return None

    company_dict = LOCATION_MAP.get(company)
    if not company_dict:
        return None

    return company_dict.get(location)


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

def get_effective_rules_for_employee_day(company_name: str, employee_no: str, source_name: str) -> dict:
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

    # --- Reverted Logic: Only imply rotational if explicitly empty/None ---
    if (effective_rules.get("weekend_days") == [] or effective_rules.get("weekend_days") is None) and \
       not effective_rules.get("is_rotational_off", False):
        effective_rules["is_rotational_off"] = True
        if "rotational_days_off_per_week" not in effective_rules:
            effective_rules["rotational_days_off_per_week"] = 1
    # --- End New Logic ---

    # Apply employee-specific overrides (highest precedence)
    employee_rules = company_config.get("employee_overrides", {}).get(employee_no, {})
    effective_rules = merge_configs(effective_rules, employee_rules)
    
    return effective_rules

# Helper to get expected working days for a period, considering alternating weekends
def get_expected_working_days_in_period(start_date, end_date, rules: dict) -> float: # Return float for precision
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
                else:
                    is_weekend = False
            elif weekend_rule_type == "alternating_f_fs":
                iso_week_number = current_date.isocalendar()[1]
                if (iso_week_number % 2) == 1: # Odd weeks: Friday only (Week 1, 3, 5...)
                    if day_of_week == calendar.FRIDAY:
                        is_weekend = True
                    else:
                        is_weekend = False
                else: # Even weeks: Friday and Saturday (Week 2, 4, 6...)
                    if day_of_week == calendar.FRIDAY or day_of_week == calendar.SATURDAY:
                        is_weekend = True
                    else:
                        is_weekend = False
            
            if not is_weekend:
                expected_days += 1
            
            current_date += timedelta(days=1)
        return float(expected_days) # Return float even for fixed, for consistency
