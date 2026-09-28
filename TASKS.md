# Tasks

## Active

- [ ] **Auto-detect and adapt to fingerprint file date formats** - IMPLEMENTED 2026-09-28, awaiting Kareem's test in the app before marking done
  - Problem: the team sometimes changes the date format on the fingerprint machine export (day/month/year ↔ month/day/year), which currently causes the "Date Range Exceeded" blocking error
  - Read the date column in the uploaded files and assess its actual format first
  - Use the existing period date-range rule as the detection criterion: all dates must fall within the period start/end — a file whose parsed span exceeds the 40-day limit (data_processing.py date integrity check) means the format is wrong; try the alternate format and keep the one that yields a valid range within the period
  - Compare against the store's known date format in config.py, then either auto-convert the file to the config format or adapt to the file's new format — the app keeps working either way
  - Report the mismatch to the user in a message/popup, but only AFTER processing is done
  - A wrong date format must never block the run — the mismatched file is included, not rejected

- [ ] **Add a "Store Management" page to the app** - IMPLEMENTED 2026-09-28, awaiting Kareem's test + GITHUB_TOKEN in Streamlit secrets before marking done
  - Sidebar button opens the page; user flow: select the company first, then manage its stores
  - Add form: store name (same as file naming), date format (dropdown), working hours (8, 9, or 12/24 for Second Cup — 8/9 map to shift hours with derived thresholds shift−0.5 and shift+1; 24 sets the 24-hour flag), weekends (7 weekday checkboxes; none selected = rotational off, shown explicitly), optional Google Sheet schedule link (STORE_OPS_LINKS)
  - Auto-assign the store number: company digit (1 D&H, 2 D&co, 3 Second Cup, 4 Al-hadabah) + next free 2-digit location code; show the number to the user so files get renamed to it (e.g. 117.xlsx)
  - Full interactive: add, update, delete (delete needs a confirmation step)
  - Persistence (decided 2026-09-28): custom stores saved to a JSON overlay file auto-committed to GitHub via the GitHub API (token in Streamlit secrets, requests only) — survives Streamlit Cloud redeploys; config.py merges the overlay at load using the existing merge_configs pattern
  - D&co note: LOCATION_MAP has no D&co section yet; first added store creates it
  - Rules: no fancy packages (keep it simple), do NOT touch the calculations code, don't assume — ask when unclear

## Waiting On

## Someday

## Done
