# import pandas as pd
# from datetime import timedelta, time # Import time for time comparisons
# import streamlit as st # Used for st.session_state.get('debug_mode', False)

# # Import helper functions from config.py
# from config import format_timedelta_to_hms

# # The calculate_second_cup_shifts function is now removed, as general Second Cup locations
# # will be processed by the _calculate_non_second_cup_shift_details in data_processing.py,
# # which does not include any special first-punch removal logic.

# def calculate_24_hour_shifts(emp_group_full_sorted: pd.DataFrame, emp_no: str, selected_company_name: str) -> list:
#     """
#     Calculates shift durations for 24-hour locations (e.g., specific Second Cup stores)
#     based on C/In and C/Out pairings. This logic allows shifts to span multiple calendar days.
#     It conditionally removes an initial C/Out punch if it falls between 2 AM and 7 AM.

#     Args:
#         emp_group_full_sorted (pd.DataFrame): DataFrame containing all punches for a single employee, sorted by time.
#         emp_no (str): The employee number.
#         selected_company_name (str): The name of the selected company (should be "Second Cup").

#     Returns:
#         list: A list of dictionaries, each representing a calculated shift for the employee.
#     """
#     daily_report_list_for_employee = []
#     records = emp_group_full_sorted.to_dict('records')
    
#     # Define the time window for ignoring initial C/Out punches
#     ignore_start_time = time(2, 0, 0) # 2 AM
#     ignore_end_time = time(7, 0, 0)   # 7 AM

#     # Conditional removal of the first C/Out punch for 24-hour locations
#     # Only remove if it's a C/Out AND its time falls within the 2 AM to 7 AM window
#     if records and str(records[0]['Status']).strip().lower() == 'c/out':
#         first_punch_time = records[0]['Original_DateTime'].time()
#         if ignore_start_time <= first_punch_time <= ignore_end_time:
#             if st.session_state.get('debug_mode', False):
#                 st.write(f"DEBUG (24hr Logic): Employee {emp_no}: Initial C/Out punch {records[0]['Original_DateTime']} ignored (within 2 AM - 7 AM window).")
#             records = records[1:]
#         else:
#             if st.session_state.get('debug_mode', False):
#                 st.write(f"DEBUG (24hr Logic): Employee {emp_no}: Initial C/Out punch {records[0]['Original_DateTime']} NOT ignored (outside 2 AM - 7 AM window).")
    
#     i = 0
#     while i < len(records):
#         current_record = records[i]
#         # Only process if it's a C/In
#         if str(current_record['Status']).strip().lower() == 'c/in':
#             found_cout = False
#             potential_cout_index = -1
            
#             # Look for a matching C/Out anywhere after the current C/In
#             for j in range(i + 1, len(records)):
#                 next_record = records[j]
                
#                 # If the next record is a C/In, it means the current C/In is an open shift,
#                 # or the previous C/Out was missed. Break and process current C/In as open.
#                 if str(next_record['Status']).strip().lower() == 'c/in':
#                     if st.session_state.get('debug_mode', False):
#                         st.write(f"DEBUG (24hr Logic): Employee {emp_no}, C/In at {current_record['Original_DateTime']}: Found subsequent C/In at {next_record['Original_DateTime']} before C/Out. Treating as open shift.")
#                     break # Exit inner loop, current C/In is unmatched for now

#                 if str(next_record['Status']).strip().lower() == 'c/out':
#                     # Found a C/Out, this is our match. No duration or day constraints here.
#                     potential_cout_index = j
#                     found_cout = True
#                     break # Found a valid C/Out, break inner loop
            
#             if found_cout and potential_cout_index != -1:
#                 matched_cout_record = records[potential_cout_index]
#                 duration_td = matched_cout_record['Original_DateTime'] - current_record['Original_DateTime'] # Use Original_DateTime for duration
                
#                 daily_report_list_for_employee.append({
#                     'No.': emp_no,
#                     'Name': current_record['Name'],
#                     'Date': current_record['Original_DateTime'].date(), # Shift attributed to original date of C/In
#                     'Source_Name': current_record['Source_Name'],
#                     'Original Number of Punches': 2, # For this pair
#                     'Number of Cleaned Punches': 2, # For this pair
#                     'First Punch Time': current_record['Original_DateTime'].strftime('%I:%M:%S %p'),
#                     'Last Punch Time': matched_cout_record['Original_DateTime'].strftime('%I:%M:%S %p'),
#                     'Total Shift Duration': format_timedelta_to_hms(duration_td),
#                     'Total Break Duration': '00:00:00', # No breaks in this model for Second Cup
#                     'Daily_More_T_Hours': '00:00:00', # Will be calculated later
#                     'Daily_Short_T_Hours': '00:00:00', # Will be calculated later
#                     'is_more_t_day': False,
#                     'is_short_t_day': False,
#                     'Punch Status': 'Paired C/In-C/Out Shift (24hr Logic)',
#                     'More_T_postMID': '00:00:00' # Will be calculated later
#                 })
#                 i = potential_cout_index + 1 # Move past the consumed C/Out
#             else:
#                 # C/In without a suitable matching C/Out (open shift)
#                 daily_report_list_for_employee.append({
#                     'No.': emp_no,
#                     'Name': current_record['Name'],
#                     'Date': current_record['Original_DateTime'].date(),
#                     'Source_Name': current_record['Source_Name'],
#                     'Original Number of Punches': 1,
#                     'Number of Cleaned Punches': 1,
#                     'First Punch Time': current_record['Original_DateTime'].strftime('%I:%M:%S %p'),
#                     'Last Punch Time': current_record['Original_DateTime'].strftime('%I:%M:%S %p'),
#                     'Total Shift Duration': '00:00:00',
#                     'Total Break Duration': '00:00:00',
#                     'Daily_More_T_Hours': '00:00:00',
#                     'Daily_Short_T_Hours': '00:00:00',
#                     'is_more_t_day': False,
#                     'is_short_t_day': False,
#                     'Punch Status': 'Open Shift (Missing C/Out, 24hr Logic)',
#                     'More_T_postMID': '00:00:00'
#                 })
#                 i += 1 # Move to next punch
#         else:
#             # C/Out or other status without a preceding C/In (ignore)
#             if st.session_state.get('debug_mode', False):
#                 st.write(f"DEBUG (24hr Logic): Employee {emp_no}: Unmatched punch {current_record['Original_DateTime']} ({current_record['Status']}) ignored.")
#             i += 1
#     return daily_report_list_for_employee


import pandas as pd
from datetime import timedelta, time # Import time for time comparisons
import streamlit as st # Used for st.session_state.get('debug_mode', False)

# Import helper functions from config.py
from config import format_timedelta_to_hms

# The calculate_second_cup_shifts function is now removed, as general Second Cup locations
# will be processed by the _calculate_non_second_cup_shift_details in data_processing.py,
# which does not include any special first-punch removal logic.

def calculate_24_hour_shifts(emp_group_full_sorted: pd.DataFrame, emp_no: str, selected_company_name: str) -> list:
    """
    Calculates shift durations for 24-hour locations (e.g., specific Second Cup stores)
    based on C/In and C/Out pairings. This logic allows shifts to span multiple calendar days.
    It conditionally removes an initial C/Out punch if it falls between 2 AM and 7 AM.
    Crucially, it now enforces a maximum shift duration of 20 hours.

    Args:
        emp_group_full_sorted (pd.DataFrame): DataFrame containing all punches for a single employee, sorted by time.
        emp_no (str): The employee number.
        selected_company_name (str): The name of the selected company (should be "Second Cup").

    Returns:
        list: A list of dictionaries, each representing a calculated shift for the employee.
    """
    daily_report_list_for_employee = []
    records = emp_group_full_sorted.to_dict('records')
    
    # Define the time window for ignoring initial C/Out punches
    ignore_start_time = time(1, 0, 0) # 2 AM
    ignore_end_time = time(7, 0, 0)   # 7 AM

    # Define maximum allowed shift duration for 24-hour locations
    MAX_SHIFT_DURATION = timedelta(hours=20)

    # Conditional removal of the first C/Out punch for 24-hour locations
    # Only remove if it's a C/Out AND its time falls within the 2 AM to 7 AM window
    if records and str(records[0]['Status']).strip().lower() == 'c/out':
        first_punch_time = records[0]['Original_DateTime'].time()
        if ignore_start_time <= first_punch_time <= ignore_end_time:
            if st.session_state.get('debug_mode', False):
                st.write(f"DEBUG (24hr Logic): Employee {emp_no}: Initial C/Out punch {records[0]['Original_DateTime']} ignored (within 2 AM - 7 AM window).")
            records = records[1:]
        else:
            if st.session_state.get('debug_mode', False):
                st.write(f"DEBUG (24hr Logic): Employee {emp_no}: Initial C/Out punch {records[0]['Original_DateTime']} NOT ignored (outside 2 AM - 7 AM window).")
    
    i = 0
    while i < len(records):
        current_record = records[i]
        # Only process if it's a C/In
        if str(current_record['Status']).strip().lower() == 'c/in':
            found_cout = False
            potential_cout_index = -1
            
            # Look for a matching C/Out anywhere after the current C/In
            for j in range(i + 1, len(records)):
                next_record = records[j]
                
                # If the next record is a C/In, it means the current C/In is an open shift,
                # or the previous C/Out was missed. Break and process current C/In as open.
                if str(next_record['Status']).strip().lower() == 'c/in':
                    if st.session_state.get('debug_mode', False):
                        st.write(f"DEBUG (24hr Logic): Employee {emp_no}, C/In at {current_record['Original_DateTime']}: Found subsequent C/In at {next_record['Original_DateTime']} before C/Out. Treating as open shift.")
                    break # Exit inner loop, current C/In is unmatched for now

                if str(next_record['Status']).strip().lower() == 'c/out':
                    # Found a C/Out, this is our match. Now check duration constraint
                    potential_duration_td = next_record['Original_DateTime'] - current_record['Original_DateTime']
                    
                    if potential_duration_td <= MAX_SHIFT_DURATION:
                        potential_cout_index = j
                        found_cout = True
                        break # Found a valid C/Out within max duration, break inner loop
                    else:
                        # This C/Out is too far from the current C/In. Skip it and keep looking.
                        # The current C/In will eventually be an open shift if no valid C/Out is found.
                        if st.session_state.get('debug_mode', False):
                            st.write(f"DEBUG (24hr Logic): Employee {emp_no}, C/In at {current_record['Original_DateTime']}: Potential C/Out at {next_record['Original_DateTime']} exceeds MAX_SHIFT_DURATION ({MAX_SHIFT_DURATION}). Skipping this C/Out.")
                        # Do NOT break, continue looking for another C/Out
            
            if found_cout and potential_cout_index != -1:
                matched_cout_record = records[potential_cout_index]
                duration_td = matched_cout_record['Original_DateTime'] - current_record['Original_DateTime'] # Use Original_DateTime for duration
                
                daily_report_list_for_employee.append({
                    'No.': emp_no,
                    'Name': current_record['Name'],
                    'Date': current_record['Original_DateTime'].date(), # Shift attributed to original date of C/In
                    'Source_Name': current_record['Source_Name'],
                    'Original Number of Punches': 2, # For this pair
                    'Number of Cleaned Punches': 2, # For this pair
                    'First Punch Time': current_record['Original_DateTime'].strftime('%I:%M:%S %p'),
                    'Last Punch Time': matched_cout_record['Original_DateTime'].strftime('%I:%M:%S %p'),
                    'Total Shift Duration': format_timedelta_to_hms(duration_td),
                    'Total Break Duration': '00:00:00', # No breaks in this model for Second Cup
                    'Daily_More_T_Hours': '00:00:00', # Will be calculated later
                    'Daily_Short_T_Hours': '00:00:00', # Will be calculated later
                    'is_more_t_day': False,
                    'is_short_t_day': False,
                    'Punch Status': 'Paired C/In-C/Out Shift (24hr Logic)',
                    'More_T_postMID': '00:00:00' # Will be calculated later
                })
                i = potential_cout_index + 1 # Move past the consumed C/Out
            else:
                # C/In without a suitable matching C/Out (open shift)
                daily_report_list_for_employee.append({
                    'No.': emp_no,
                    'Name': current_record['Name'],
                    'Date': current_record['Original_DateTime'].date(),
                    'Source_Name': current_record['Source_Name'],
                    'Original Number of Punches': 1,
                    'Number of Cleaned Punches': 1,
                    'First Punch Time': current_record['Original_DateTime'].strftime('%I:%M:%S %p'),
                    'Last Punch Time': current_record['Original_DateTime'].strftime('%I:%M:%S %p'),
                    'Total Shift Duration': '00:00:00',
                    'Total Break Duration': '00:00:00',
                    'Daily_More_T_Hours': '00:00:00',
                    'Daily_Short_T_Hours': '00:00:00',
                    'is_more_t_day': False,
                    'is_short_t_day': False,
                    'Punch Status': 'Open Shift (Missing C/Out, 24hr Logic)',
                    'More_T_postMID': '00:00:00'
                })
                i += 1 # Move to next punch
        else:
            # C/Out or other status without a preceding C/In (ignore)
            if st.session_state.get('debug_mode', False):
                st.write(f"DEBUG (24hr Logic): Employee {emp_no}: Unmatched punch {current_record['Original_DateTime']} ({current_record['Status']}) ignored.")
            i += 1
    return daily_report_list_for_employee
