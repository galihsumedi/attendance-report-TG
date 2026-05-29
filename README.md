# Laporan Kehadiran Karyawan — v2.23

Web application for processing employee attendance data from fingerprint scanlog files into formatted Excel reports. New employee names detected in an uploaded file are flagged on-screen for the user to resolve before the report is generated, and are automatically committed back to the repository.

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

## New Employee Name Detection

When a scanlog containing an unregistered fingerprint name is uploaded, the app interrupts the normal flow and shows a form listing each unknown name. The user must provide the full legal name for every entry before the report is generated.

Once confirmed, the new names are:
1. Applied immediately to the current request (in-memory update).
2. Committed to `nama_karyawan.py` in the GitHub repository via the GitHub Contents API, so they persist across future deploys.

This requires two environment variables to be set on the server (see Deployment below).

---

## Deployment

- **Repository**: [github.com/galihsumedi/attendance-report-TG](https://github.com/galihsumedi/attendance-report-TG)
- **Live App**: [attendance-report-tg.onrender.com](https://attendance-report-tg.onrender.com/)

### Required environment variables (Render)

| Variable | Value |
|---|---|
| `GITHUB_TOKEN` | A GitHub Personal Access Token with `repo` (contents write) scope |
| `GITHUB_REPO` | `galihsumedi/attendance-report-TG` |

If these variables are not set, the app runs normally but new names are not persisted to GitHub — they apply only for the current server session.

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

The GitHub commit step is skipped automatically when `GITHUB_TOKEN` is not set, so no extra configuration is needed for local development.
