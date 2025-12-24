# FIG-D-H
# Attendance Processing & Summary Report Generator

This is a Python-based application designed to process fingerprint attendance data from biometric systems and generate detailed summary reports for HR and operations teams. It includes intelligent logic for handling vacations, absences, exceptions, and rotational offs based on company-specific rules.

## 📌 Key Features

- ✅ **Attendance Summarization**  
  Processes daily punch logs and calculates total present days, shift durations, early/late metrics, single punch flags, and more.

- 📅 **Vacation Adjustment**  
  Integrates approved vacations and adjusts absence records accordingly to ensure accuracy in absentee reports.

- 📤 **Pending Offs Logic**  
  Applies company-configured rotational offs, exception lists, and excused days across different employee roles and sources.

- 📊 **Summary Report Generation**  
  Aggregates all metrics into a summary DataFrame, with exportable reports that include:
  - Total working days
  - Total absences
  - Present days
  - Adjusted absence types
  - Shift hour summaries (formatted HH:MM:SS)

- 🧠 **Rule-Based Customization**  
  Reads attendance rules per employee/source dynamically (e.g., expected working days per week, weekends, rotational days off).

## 📂 Modules Overview

| File | Purpose |
|------|---------|
| `main.py` | Entry point that coordinates report generation |
| `pending_offs.py` | Logic for identifying OFF days using rules & attendance |
| `vacation_adjustment.py` | Applies vacation rules, adjusts excused absences |
| `second_cup_logic.py` | Contains utility functions and exception handling rules |
| `report_generation.py` | Builds summary report with aggregation logic |

## 🏗️ How It Works

1. **Input:**  
   Fingerprint data logs in tabular format with punch times, shift durations, and daily metadata.

2. **Preprocessing:**  
   - Calculates effective attendance windows per employee.
   - Identifies and flags excused days (vacations, OFFs, exceptions).
   - Computes present vs absent days.

3. **Report Generation:**  
   - Merges daily punch data with business rules.
   - Outputs detailed summaries per employee with absence breakdowns.
   - Formats shift durations to readable HH:MM:SS format.

4. **Final Output:**  
   - A full summary DataFrame with all KPIs.
   - A sheet for adjusted absences with excused and non-excused separation.

## 🛠️ Configuration

- Weekend days, OFF policies, and expected workdays per week are dynamically derived per employee using `get_effective_rules_for_employee_day()`.

- Excused absence sources include:
  - Vacation entries
  - Rotational OFFs
  - Manual overrides or exception flags

## ✅ Output Columns (Highlights)

- `Total_Present_Days`
- `Total_Absent_Days` & `Final_Absent_Days`
- `Total_Shift_Durations_hours`
- `Total_Shift_Durations` (formatted)
- `Count_Single_Punch_Days`
- `Total_Employee_Period_OFFs`
- `Total_Expected_Weekends_In_Period`
- `Absent_Dates` (comma-separated)

## 🚀 Usage

This tool is intended for integration into internal HR/Operations workflows or Streamlit dashboards for visual inspection and export.

---

> ⚠️ Make sure to adjust the configuration rules per your company policy in `second_cup_logic.py` and `pending_offs.py`.

