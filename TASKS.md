# Tasks

## Active

- [ ] **Auto-detect and adapt to fingerprint file date formats** - stop wrong date formats from blocking report generation
  - Problem: the team sometimes changes the date format on the fingerprint machine export (day/month/year ↔ month/day/year), which currently causes the "Date Range Exceeded" blocking error
  - Read the date column in the uploaded files and assess its actual format first
  - Use the existing period date-range rule as the detection criterion: all dates must fall within the period start/end — a file whose parsed span exceeds the 40-day limit (data_processing.py date integrity check) means the format is wrong; try the alternate format and keep the one that yields a valid range within the period
  - Compare against the store's known date format in config.py, then either auto-convert the file to the config format or adapt to the file's new format — the app keeps working either way
  - Report the mismatch to the user in a message/popup, but only AFTER processing is done
  - A wrong date format must never block the run — the mismatched file is included, not rejected

- [ ] **Add a "Store Management" page to the app** - lets the team add new stores to a company without developer help
  - User flow: select the company first, then manage its stores
  - Store fields: store name, date format, store code, working hours
  - Interactive interface: add, delete, and update stores
  - Must be simple enough for non-developers to use
  - Rules: no fancy packages (keep it simple), do NOT touch the calculations code, don't assume — ask when unclear

## Waiting On

## Someday

## Done
