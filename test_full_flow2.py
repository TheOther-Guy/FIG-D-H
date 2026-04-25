import pandas as pd
from store_ops_logic import fetch_store_ops_from_url, compare_criteria_with_actual

url = "https://docs.google.com/spreadsheets/d/153tgWpTT65qOVL_KJpGOMP7xNYmG-Sc5JNNIhcsz490/export?format=csv&gid=2085306002"
raw_result = fetch_store_ops_from_url(url)

detailed_report_df = pd.DataFrame()
res = compare_criteria_with_actual(raw_result, detailed_report_df)
overrides_map = res['overrides']

import json
# print the overrides for 2825
emp_overrides = overrides_map.get("2825", {})
print("Overrides for 2825:")
for d, s in emp_overrides.items():
    print(d, s)
