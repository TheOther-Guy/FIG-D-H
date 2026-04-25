import pandas as pd
from datetime import datetime, time, timedelta
import sys
import os

# Add project dir to path
sys.path.append('/Users/Smile2DeaTH/Desktop/FIG/multipage_APP/FIG-D-H google sheets ')

from second_cup_logic import calculate_24_hour_shifts

def test_1433_pattern():
    # Simulate all C/In pattern for employee 1433
    data = [
        {'No.': '1433', 'Name': 'Baida Pakil', 'Status': 'C/In', 'Original_DateTime': datetime(2026, 2, 8, 7, 53, 26), 'Source_Name': 'Dar al Shifa Clinic'},
        {'No.': '1433', 'Name': 'Baida Pakil', 'Status': 'C/In', 'Original_DateTime': datetime(2026, 2, 9, 7, 56, 3), 'Source_Name': 'Dar al Shifa Clinic'},
        {'No.': '1433', 'Name': 'Baida Pakil', 'Status': 'C/In', 'Original_DateTime': datetime(2026, 2, 10, 8, 2, 42), 'Source_Name': 'Dar al Shifa Clinic'},
    ]
    df = pd.DataFrame(data)
    results = calculate_24_hour_shifts(df, '1433', 'Second Cup')
    
    print("--- 1433 Pattern Results (All C/In) ---")
    for r in results:
        print(f"Date: {r['Date']}, Duration: {r['Total Shift Duration']}, Status: {r['Punch Status']}, Fixed: {r['Status_Autofixed']}")

def test_carry_over_skip():
    # First punch is a morning C/Out
    data = [
        {'No.': '1', 'Name': 'Test', 'Status': 'C/Out', 'Original_DateTime': datetime(2026, 2, 8, 5, 0, 0), 'Source_Name': 'S1'},
        {'No.': '1', 'Name': 'Test', 'Status': 'C/In', 'Original_DateTime': datetime(2026, 2, 8, 9, 0, 0), 'Source_Name': 'S1'},
        {'No.': '1', 'Name': 'Test', 'Status': 'C/Out', 'Original_DateTime': datetime(2026, 2, 8, 17, 0, 0), 'Source_Name': 'S1'},
    ]
    df = pd.DataFrame(data)
    results = calculate_24_hour_shifts(df, '1', 'Second Cup')
    
    print("\n--- Carry Over Skip Results ---")
    for r in results:
        print(f"Date: {r['Date']}, Duration: {r['Total Shift Duration']}, Status: {r['Punch Status']}")

def test_night_shift():
    # Night shift: 8 PM to 8 AM
    data = [
        {'No.': '2', 'Name': 'NightWorker', 'Status': 'C/In', 'Original_DateTime': datetime(2026, 2, 20, 20, 0, 0), 'Source_Name': 'S2'},
        {'No.': '2', 'Name': 'NightWorker', 'Status': 'C/Out', 'Original_DateTime': datetime(2026, 2, 21, 8, 0, 0), 'Source_Name': 'S2'},
    ]
    df = pd.DataFrame(data)
    results = calculate_24_hour_shifts(df, '2', 'Second Cup')
    
    print("\n--- Night Shift Results ---")
    for r in results:
        print(f"Date: {r['Date']}, Duration: {r['Total Shift Duration']}, Status: {r['Punch Status']}")

if __name__ == "__main__":
    test_1433_pattern()
    test_carry_over_skip()
    test_night_shift()
