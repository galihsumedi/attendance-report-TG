# Change Logs — Laporan Kehadiran Karyawan

> **Reminder for every update:** Before closing any version, always update:
> 1. `Change Logs.md` — add new version entry at the top, in descending order (latest first)
> 2. `README.md` — bump version number in the title header
> 3. `templates/index.html` — bump version in both the `<title>` tag and the subtitle paragraph

---

## v2.3 — Indonesian National Holiday Highlighting

### Feature: Automatic national holiday detection via live API
- Laporan Individual now highlights Indonesian national holidays (excluding cuti bersama) with a distinct soft orange background and red font, separate from the existing weekend formatting (light blue).
- Holiday name (in Indonesian) is automatically populated in the Catatan column for the relevant day.
- Holiday data is fetched from the Nager.Date public API (`date.nager.at`) on each report generation — no manual upkeep required.
- Results are cached in memory per year for the session, so multiple reports in the same session do not trigger repeated API calls.
- If the API is unreachable, the app falls back gracefully and generates the report without holiday marking.

---

## v2.23 — Hide Data Harian Sheet by Default

### Feature:
- The **Data Harian** sheet in the output Excel report is now hidden by default.
  Users can still reveal it via Excel's Unhide option if needed.

---

## v2.22 — Output Cleanup and Visual Polish

### Fix: Removed "Tepat Waktu" and "Cepat Pulang" from Laporan Individual
- The "Catatan" section at the bottom of each employee block in Laporan Individual no longer includes the "Tepat Waktu" and "Cepat Pulang" rows.
- Both the label rows and their formulas have been removed entirely — no blank rows are left in their place.
- Block spacing adjusted accordingly (2 fewer rows per employee block).

### Fix: Removed blank row 2 from Rekapitulasi
- Row 2 in Rekapitulasi was intentionally blank, creating unnecessary visual gap between the company title and the month header.
- Removed: the month header now sits directly on row 2, and the column headers and data rows shift up by one row each.

### Feature: Gridlines hidden on Rekapitulasi and Laporan Individual
- Sheet gridlines are now turned off for both Rekapitulasi and Laporan Individual when the file is opened in Excel.
- Data Mentah and Data Harian are unaffected.

---

## v2.21 — UI Fix: Laporan Individual Total Row and Column Header

### Fix: TOTAL row in Laporan Individual no longer merges across all columns
- The TOTAL row was previously merged across columns A–G, hiding the total minutes late value entirely.
- Fixed: columns A–E are merged for the "TOTAL" label; column F now displays a SUM formula showing the total minutes late for the employee.

### Fix: Column F header renamed from "Jam Terlambat" to "Menit Terlambat"
- The column header in Laporan Individual for lateness was labelled "Jam Terlambat" (hours late), which was incorrect — the column stores values in minutes.
- Renamed to "Menit Terlambat" to match the actual data.

---

## v2.2 — Auto-Detection of New Employee Names on Upload

### Feature: New employee name detection
- When a scanlog is uploaded, the app now checks every `Nama` value in the file against the registered names in `nama_karyawan.py`.
- If any unregistered names are found, the download is held and the user is shown a form listing each unknown fingerprint name with an input field for the full legal name.
- All fields are required — the form cannot be submitted with any name left blank.
- Once confirmed, the new names are registered in memory immediately and the report is generated and downloaded as normal.

### Feature: Automatic commit of new names to GitHub
- After the user confirms new names, the app commits the updated `nama_karyawan.py` directly to the GitHub repository via the GitHub Contents API.
- Requires two environment variables: `GITHUB_TOKEN` (a PAT with `contents:write` scope) and `GITHUB_REPO` (e.g. `galihsumedi/attendance-report-TG`).
- If the environment variables are not set (e.g. local development), the GitHub commit step is silently skipped — the in-memory update still applies for the current session.
- If the API call fails at runtime, the report download still proceeds and a warning is shown asking the user to update `nama_karyawan.py` manually.

---

## v2.1 — Laporan Individual Reformatting and Nama Lengkap Automatic Conversion

### Request: HR requested a different layout for Laporan Individual
- Laporan Individual is reformatted for HR.
- Laporan Individual does not include the dropdown but rather individual reports are printed independently.

### Feature: Full name conversion
- Added nama_lengkap.py to automatically convert 'fingerprint' names into full legal names of the employees for reporting purporses.

---

## v1.3 — .xls Input Support

### Feature: Accept .xls Files as Input
- App now accepts both `.xlsx` and `.xls` upload formats, not just `.xlsx`.
- File validation in `app.py` updated to allow either extension.
- Error message on invalid upload updated to mention both formats.
- `xlrd` added to `requirements.txt` as the pandas engine for reading `.xls` files.

---

## v1.2 — Logic Improvements and Output Polish

### Logic: Reference Month Detection Changed to Most Frequent
- Previously, the reference month was determined by the earliest date found in the file.
- Changed to use the most frequently occurring month across all rows in the file.
- This prevents stray rows from a neighbouring month (e.g. a carry-over entry on the 1st) from incorrectly shifting the detected month.

### Feature: Auto Column Width on Data Harian
- Data Harian sheet now automatically adjusts each column's width based on the longest value in that column, capped at 40 characters.
- Previously all columns were a fixed width, causing content to be cut off.

---

## v1.1 — Fixes, Redesign, and Feature Additions

### Fix: Rekapitulasi Header Columns Empty
- Column headers in Sheet 2 (Rekapitulasi) were blank because values were written to slave cells before merging, causing them to be lost.
- Fixed by writing the label to the anchor (top-left) cell first, then performing the merge.

### Fix: Laporan Individual Lookup Formulas Not Working
- The original lookup used a two-criteria array MATCH formula that requires Ctrl+Shift+Enter in older Excel versions — it silently returned no results.
- Replaced with a single-criteria MATCH on a concatenated key column (`Nama|NoHari`) added to Data Harian (column M), which works in all Excel versions without array entry.

### Redesign: Visual Style and Sheet 3 Behaviour
- Reformatted Rekapitulasi and Laporan Individual to match the visual style of the provided reference files.
- Laporan Individual changed from showing all employees at once to showing one employee at a time, with the active employee selected via a dropdown in cell C6.
- All data rows in Laporan Individual are populated by lookup formulas that respond to the dropdown selection.

### Logic: Lateness Calculation Moved to Data Harian
- Lateness values in Rekapitulasi (columns G, H, I) were previously hardcoded.
- Data Harian now stores lateness as a plain number (minutes) in one column and as a display string (e.g. "5 menit", "1 jam 5 menit") in a separate column.
- Rekapitulasi calculates total lateness per employee using a SUMIF formula referencing the numeric minutes column in Data Harian, then converts to hours and remaining minutes using INT and MOD formulas.

### Rule: Day 1 of Each Month Exempt from Lateness
- The first calendar day of each month is excluded from lateness calculation.
- Reason: the first entry often contains only an exit scan carried over from a night shift in the previous month, not a genuine clock-in.

### Feature: Catatan (Manual) Column in Data Harian
- Added a new editable column (Catatan Manual) to Data Harian where users can enter free-text notes per employee per day.
- Laporan Individual now pulls this column via lookup alongside the auto-generated notes.

### Feature: Laporan Individual Edit Warning
- Added a warning message in row 1 of Laporan Individual informing users that the sheet is read-only and manual notes should be entered in Data Harian instead.

### Feature: Data Harian No Longer Hidden
- Data Harian sheet was previously hidden; it is now visible so users can directly edit the Catatan Manual column.

### Feature: Auto-Filter on Data Harian Headers
- Auto-filter is now applied to all header columns in Data Harian, allowing users to filter and sort rows directly in Excel.

### Logic: Lateness Rounding Changed to Floor-by-Minute
- Previously, lateness was calculated using raw seconds, so 08:00:59 would register as late.
- Changed to compare only hours and minutes. Seconds are ignored entirely.
- Examples: 08:00:59 → 0 minutes late. 08:01:30 → 1 minute late. 08:05:59 → 5 minutes late.

### Fix: Laporan Individual Cleanup
- Removed the TOTAL row and all content below it from Laporan Individual.
- Sheet protection applied: all cells are locked except C6 (the employee name dropdown), preventing accidental edits to formula cells.

### Fix: Rekapitulasi Header Borders and Labels
- Full borders applied to all merged header cells, including the bottom edge of merged pairs.
- Header label "N A M A" renamed to "Nama Karyawan".
- Removed the subtitle row containing the group name ("Kelompok Makmur").
- "Dinas Lapangan" changed from two separate cells to one merged, word-wrapped cell spanning the two header rows.

### Fix: Upload Form Simplified
- Removed the "Nama Kelompok" and "Bulan & Tahun" input fields from the upload page.
- Both values are now derived automatically from the uploaded file — no manual entry required.

---

## v1.0 — Initial Release

- Built the full app from scratch based on project specifications.
- Flask handles file upload and serves the output file.
- Processor reads the scanlog, parses dates and times, and computes per-employee daily data.
- Excel writer generates a 4-sheet workbook: Data Mentah, Rekapitulasi, Laporan Individual, Data Harian.
