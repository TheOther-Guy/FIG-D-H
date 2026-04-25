import pandas as pd
from store_ops_logic import fetch_store_ops_from_url

url = "https://docs.google.com/spreadsheets/d/153tgWpTT65qOVL_KJpGOMP7xNYmG-Sc5JNNIhcsz490/export?format=csv&gid=2085306002"
df = fetch_store_ops_from_url(url)
print(df.columns.tolist())
