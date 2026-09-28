# D&H Group Web App (FIG-D-H)

A web application for the D&H Group team that turns raw fingerprint (punch) machine files into ready-to-share Excel attendance reports. It automatically handles vacations, sick leave, days off, public holidays, and store schedules — so you don't have to calculate anything by hand.

You use it from your web browser. No technical knowledge is needed.

---

## 🧭 What's Inside the App

After logging in, the sidebar on the left has these pages:

| Page | What it does |
|------|--------------|
| 🏠 **Home** | Welcome screen |
| 📷 **SKU Generator** | Turns a folder of product photos (named like `P_SKUnameD1.jpg`) into a CSV file listing each SKU with its photos |
| ⏰ **Fingerprint Reports** | The main tool — builds the employee attendance report (see guide below) |
| 🔍 **Diagnostics** | For checking a specific employee's data when something looks wrong |

---

## 🚀 How to Use the Fingerprint Reports Page (Step by Step)

1. **Log in** with the username and password provided by your administrator.
2. In the sidebar, click **⏰ Fingerprint Reports**.
3. **Select the company** from the dropdown: *Al-hadabah times*, *D&H*, *D&co*, or *Second Cup*.
   ⚠️ Make sure the company matches the files you are about to upload — each company has its own date formats and rules.
4. **Upload the fingerprint files** (.csv, .xls, or .xlsx) exported from the punch machines. You can upload several files at once.
5. *(Optional)* **Upload the Vacation/Sick/Emergency adjustments file** if you have one for this period.
6. **Type a filename** for the report (or keep the default).
7. Click **🚀 Generate Reports** and wait a moment while it processes.
8. Review the results on screen, then click the **download button** to save the Excel report.
9. Starting over with new files? Click **🔄 New Files (Clear and Reset)** first.

### 📥 What the downloaded Excel report contains

- **Detailed Daily Report** — every employee, every day, with punch times and shift durations
- **Summary** — one row per employee: present days, absent days, total hours, single-punch days, etc.
- **Adjusted Absences (Per Type)** — absences broken down by reason (vacation, sick, etc.)
- **Pending OFF Credits** — pending off days owed/used
- **Error Log** — anything the app could not read, so you can fix and re-upload
- **Days_Flags** — day-by-day status flags used in the calculations

### 📅 Store schedule codes (from Google Sheets)

The app reads each store's schedule directly from its Google Sheet and compares it with the actual punches. Use these codes in the sheets:

| Code | Meaning | Counted as |
|------|---------|-----------|
| `PT` | Present / working day | Expected to punch |
| `AB` | Absent | **Not** excused |
| `OFF` / `OF` | Off day | Excused |
| `OH` | Half day off | Excused |
| `VC` | Vacation | Excused |
| `SL` | Sick leave | Excused |
| `DP` or `PH` | Public holiday (both codes work) | Excused |
| `XO` | Extra off | Excused |
| `TR` | Transferred | Excused |
| `HD` / `FD` | Half/Full day pending off | Excused (pending logic) |

Small typos in capitalization or extra spaces (e.g. ` ph `) are handled automatically. Any **other** code is ignored by the calculations — stick to this list.

---

## ⚠️ If You See a "Date Range Exceeded" Error

This means a file's dates are written in a format the app didn't expect for that location. Either:
1. Check you selected the **correct company** before uploading, or
2. Fix the date format in the file and re-upload, or
3. Ask the administrator to update the date format for that store in `config.py`.

---

## 🏗️ Infrastructure (Technical Overview)

For administrators and developers:

- **Framework:** [Streamlit](https://streamlit.io) — the whole app is a Python web app; the browser interface, uploads, and downloads are all Streamlit. There is no separate database: everything is processed in memory per session.
- **Data processing:** pandas throughout. Excel files are read with openpyxl/xlrd and the final report is written with xlsxwriter.
- **Google Sheets integration:** store operations schedules are fetched live over HTTPS as CSV exports of each store's Google Sheet (no Google account/API key needed — the sheets are read via their share links defined in `config.py` → `STORE_OPS_LINKS`).
- **Configuration:** `config.py` is the single source of truth — companies, store codes, per-location date formats, weekend rules, and the Google Sheets links (`COMPANY_CONFIGS`, `LOCATION_MAP`, `STORE_OPS_LINKS`).

### Module map

| File | Purpose |
|------|---------|
| `main.py` | App entry point: login, sidebar navigation, page routing |
| `login_page.py` | Login screen |
| `app_ui.py` | Fingerprint Reports page UI (uploads, buttons, results display) |
| `config.py` | All company/store configuration and Google Sheets links |
| `data_processing.py` | Reads and cleans the raw fingerprint files |
| `second_cup_logic.py` | Punch pairing and 24-hour shift logic (repairs faulty punch statuses) |
| `vacation_adjustment.py` | Applies the vacation/sick/emergency adjustments file |
| `pending_offs.py` | Pending off-day credits logic |
| `store_ops_logic.py` | Fetches Google Sheets schedules and finds discrepancies vs. actual punches |
| `report_generation.py` | Builds the summary, reconciles excused absences, exports the Excel file |
| `photo_sku.py` | The SKU Generator page |
| `diagnostics.py` | The Diagnostics page |
| `analysis_functions.py` | Shared attendance calculation helpers |

### Running the app

```bash
# 1. Install Python 3.10+ then, from the project folder:
pip install -r requirements.txt

# 2. Start the app:
streamlit run main.py
```

Streamlit opens the app in your browser at `http://localhost:8501`. To let the team use it without installing anything, run it on a shared machine/server or deploy it (e.g. Streamlit Community Cloud) and share the link.

---

> ⚠️ **Administrators:** company rules, store codes, date formats, and Google Sheets links live in `config.py`. Adjust them there when a store is added or a sheet link changes.
