# Laporan Kehadiran Karyawan — v1.3

Web application for processing employee attendance data from fingerprint scanlog files into formatted Excel reports.

---

## What It Does

Upload a raw `.xlsx` or `.xls` scanlog exported from a fingerprint machine. The app reads the data, processes it, and generates a ready-to-use Excel report file with four sheets:

1. **Data Mentah** — an unmodified copy of the uploaded scanlog, kept as a reference.
2. **Rekapitulasi** — a monthly summary per employee showing total lateness (hours and minutes), calculated penalties, and manual fields for leave categories (Cuti, Sakit, Izin, Dinas Lapangan).
3. **Laporan Individual** — a single-employee daily attendance report. Select an employee from the dropdown and the sheet updates automatically. Protected from accidental edits.
4. **Data Harian** — the flat daily data table that powers all lookups and calculations. Visible and editable. Users can add manual notes per employee per day in the Catatan (Manual) column.

---

## How to Use

1. Open the web app in a browser.
2. Upload the `.xlsx` or `.xls` scanlog file from the fingerprint machine.
3. Click **Proses & Download Laporan**.
4. Open the downloaded file in Excel:
   - Fill in leave columns and penalty rate in **Rekapitulasi**.
   - Add daily notes in the **Data Harian** sheet (column N).
   - Use the name dropdown in **Laporan Individual** to view per-employee reports.

---

## Key Rules

- Work hours are fixed at **08:00–17:00**.
- Lateness is calculated by minutes only — seconds are ignored (08:00:59 = not late, 08:01:00 = 1 minute late).
- The **first day of each month** is always exempt from lateness, as it typically contains only a carry-over exit scan from the previous month.
- The reference month is determined by the **most frequently occurring date** in the uploaded file, not the earliest date.

---

## Deployment

- **Repository**: [github.com/galihsumedi/attendance-report-TG](https://github.com/galihsumedi/attendance-report-TG)
- **Live App**: [attendance-report-tg.onrender.com](https://attendance-report-tg.onrender.com/)

---

## Tech Stack

- **Backend**: Python 3.9+ with Flask
- **Excel processing**: openpyxl, pandas, xlrd
- **Frontend**: HTML with drag-and-drop file upload

---

## Setup

From the project folder, create a virtual environment, install dependencies, and run the app:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

App runs on `http://localhost:5000` by default.
