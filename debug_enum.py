import pandas as pd
from vacation_adjustment import _enumerate_absent_dates

start = pd.to_datetime("2026-03-25")
end = pd.to_datetime("2026-04-22")

# Mock emp_df with 28 days present
dates = pd.date_range(start, end)
# Remove one date (e.g., 2026-04-01) to make it 28 days
dates = dates[dates != pd.to_datetime("2026-04-01")]

emp_df = pd.DataFrame({
    "Date": dates,
    "Is_Present": [True] * 28
})

absent = _enumerate_absent_dates(emp_df, start, end, [], [])
print("Absent dates:", absent)
print("Absent count:", len(absent))
