# Change Logs — Laporan Kehadiran Karyawan

> **Reminder for every update:** Before closing any version, always update:
> 1. `Change Logs.md` — add new version entry at the top, in descending order (latest first)
> 2. `README.md` — bump version number in the title header
> 3. `templates/base.html` — bump version in the nav brand and page title

---

## v3.0 — Stateful Review App (in progress)

> **Status: Beta — actively being worked on. See planned items at the bottom of this entry.**

### Implemented (1 June 2026)

Complete rewrite from a stateless upload-download tool into a database-backed web app.

#### Adjustment logic
- **Status** (read-only in UI) — set at import from fingerprint data: `Tidak Ada Scan`, `Hanya Scan Masuk`, `3 Scan Terdeteksi`. Never editable by HR.
- **Penyesuaian Keterlambatan** — independent control, affects `menit_terlambat` only:
  - Options: Cuaca · Dinas Lapangan atau Kerja · Keterlambatan Disetujui · Koreksi Scan
  - All options (including Koreksi Scan) zero lateness for that day
- **Penyesuaian Absen** — independent control, affects HK Tidak Ada Scan only:
  - Options: Cuti · Izin · Sakit · Koreksi Scan
  - Any option exempts the day from the missing-scan count
- **Catatan** — single free-text field per cell, shared across both adjustment types
- **Penyesuaian Massal** — two options only: `Cuaca atau Banjir` · `Cuti Bersama`; both affect lateness AND HK Tidak Ada Scan for all employees on the selected date; written as one audit row (not one per employee)

#### Export — Laporan Individual
- **Cuti/Sakit/Izin/Dinas counts** auto-populated from DB adjustments (no longer blank):
  - Cuti: `adj_absen = cuti` or `cuti_bersama`
  - Sakit: `adj_absen = sakit`
  - Izin: `adj_absen = izin`
  - Dinas Lapangan: `adj_keterlambatan = dinas_lapangan` only
- **Catatan column** now shows: `[auto label] | [HR free-text note]` (e.g. `Izin | ijin keluarga`)
- Employees listed **alphabetically by name** in both Laporan Individual and Rekapitulasi

#### Employee list persistence across Render restarts
- Any change to the employee list (add, rename, delete employee; add or remove alias; resolve unknown aliases on upload) automatically rewrites `nama_karyawan.py` and commits it to the `v3.0` branch on GitHub
- On service restart, the empty DB re-seeds from the updated `nama_karyawan.py`, so the employee list is fully restored
- Requires `GITHUB_TOKEN`, `GITHUB_REPO`, and `GITHUB_BRANCH=v3.0` env vars; silently skips if not configured (local dev unaffected)

#### Petugas Keamanan — separate reporting format (2 June 2026)

- Added `employee_type` column to `employees` table (`standard` | `keamanan`); existing employees default to `standard`
- Four employees tagged as `keamanan`: Marto, Purnama Sancang, Bayu Prastyo, Yulian Nur Rahman
- Employee create/edit form now has a **Tipe Karyawan** dropdown (Karyawan Standar / Petugas Keamanan)
- **Laporan Individual** differences for `keamanan` employees:
  - Jam Kerja column shows `8 Jam` instead of `08:00-17:00`
  - Menit Terlambat column always blank (no lateness tracking)
  - Red Jam Masuk font and "Terlambat x menit" catatan are suppressed
  - Weekends and holidays still show scan data (security staff work all days)
- **HOK (Hari Orang Kerja)** = count of days in the month where the employee has at least one scan
- **Rekapitulasi** — new section appended below the main alphabetical table:
  - Lists each Petugas Keamanan (alphabetical) with their HOK count
  - Followed by a signature block (Dibuat Oleh / Diperiksa Oleh / Diketahui Oleh) with date and signer names

#### Fix: employee_type persisted across Render restarts (2 June 2026)
- `nama_karyawan.py` now includes an `EMPLOYEE_TYPES` dict for non-standard employees (e.g. `'keamanan'`)
- `github_service.py` writes `EMPLOYEE_TYPES` to `nama_karyawan.py` on every employee mutation, alongside the existing `NAMA_LENGKAP` dict
- `database.py` re-seed migration now reads `EMPLOYEE_TYPES` and applies the correct type when creating employees from scratch
- Without this fix, Petugas Keamanan employees would revert to `'standard'` after every Render restart

#### Export — Rekapitulasi HOK signature date in Indonesian (2 June 2026)
- The "Samarinda, [date]" line in the HOK signature block now uses Indonesian month names (e.g. `02 Juni 2026` instead of `02 June 2026`)
- Date still reflects the day of export, not the reporting period

#### Penyesuaian Massal — Hari Libur (2 June 2026)
- Added **Hari Libur** as a third option in Penyesuaian Massal, alongside Cuaca atau Banjir and Cuti Bersama
- Same behaviour as the other massal types: zeros lateness and exempts all employees on that date from HK Tidak Ada Scan
- Applies `adj_keterlambatan = hari_libur` and `adj_absen = hari_libur` to each affected row; written as one audit record

#### Penyesuaian Absen — Dinas Lapangan atau Kerja (2 June 2026)
- Added **Dinas Lapangan atau Kerja** to the Penyesuaian Absen dropdown in the cell edit form
- Previously only available in Penyesuaian Keterlambatan; now also exempts the day from HK Tidak Ada Scan

#### Export — Laporan Individual lateness highlights (2 June 2026)
- When an employee has both a scan-in and scan-out and is late that day, the **Jam Masuk cell is now red**
- The **Catatan column** for that day now includes `Terlambat x menit` (appended with ` | ` separator if other catatan text is already present)
- Only applies to normal workdays with both scans present; weekend and holiday rows are unaffected (those already render the full row in red)

#### Bug fixes
- Log Penyesuaian no longer shows phantom entries for employees who had no personal adjustments (was caused by bulk actions writing one audit row per employee)
- Dropdown menus in the cell edit form (Penyesuaian Keterlambatan, Penyesuaian Absen) now open correctly — clicks inside the form were bubbling up to the parent `<td>`'s HTMX handler, causing the form to reload before any dropdown could open

---

## v3.0 — Stateful Review App (original spec, 1 June 2026)

Complete rewrite from a stateless upload-download tool into a database-backed web app. Nothing is left blank for hand-editing in Excel.

### What changed

| Area | v2.3 | v3.0 |
|---|---|---|
| State | Ephemeral — lost on each request | SQLite on persistent disk |
| Employee names | `nama_karyawan.py` committed to GitHub via write token | `employees` + `employee_aliases` tables; migrated on first run |
| Output | Excel generated immediately, downloaded once | Generated on demand from DB; re-downloadable anytime |
| HR corrections | Hand-edits inside protected Excel | Inline cell editing in review grid, logged as adjustments |
| Audit trail | None | `adjustments` table → "Log Penyesuaian" 5th sheet in export |

### Three-screen workflow

**Screen 1 — Upload & match**
- Pre-flight card: detected month, employee count, record count
- Unknown fingerprint aliases resolved inline via autocomplete (alias to existing employee, or create new)

**Screen 2 — Review grid**
- All employees × all days of the month in one scrollable table
- Three frozen columns: Karyawan · Menit Terlambat · HK Tdk Scan
- Cell badges: Tepat (green) / 1–15 mnt (yellow) / >15 mnt (red) / Tdk ada scan (orange) / Libur (grey)
- Click any cell → inline edit form (HTMX, no page reload)
- **Two independent controls per cell:**
  - *Status* — affects "HK Tdk Scan" count only. Setting Cuti / Sakit / Izin / Dinas Lapangan / Hadir (Cuaca) exempts the day from the missing-scan count. Does not touch menit terlambat.
  - *Tipe Penyesuaian* — affects menit terlambat only. Any type except `scan_manual` zeros lateness; `scan_manual` recalculates from the corrected scan time. Does not touch the noscan count.
  - Saved tipe is pre-selected the next time the cell is opened
  - One adjustment record per day per employee (upsert — no duplicates)
- Bulk adjustment bar: apply cuaca or dinas to all employees on a date in one action
- "HK Tdk Scan" column: count of workdays (non-weekend, non-holiday) with no scan and no exempt status

**Screen 3 — Finalize & export**
- Finalize locks the period
- Export available anytime (draft or finalized) without re-uploading
- All 4 existing sheets fully populated (Cuti / Sakit / Izin / Denda columns no longer blank)
- New 5th sheet: **Log Penyesuaian** — full HR correction audit trail

### Business logic (unchanged from v2.3)
- Lateness = minutes only, seconds ignored; strict 08:00 cutoff
- Day 1 of month always exempt from lateness
- Reference month = most frequent month in the file
- National holidays from Nager.Date API, cached per year

### Configurable settings (`/pengaturan`)
Jam masuk/keluar batas · Grace period · Day-1 exemption toggle · Denda per menit · Sangsi multiplier. Changing any setting immediately recalculates lateness for all draft periods.

### Auth
Single-user session. Password via `HR_PASSWORD_HASH` env var (bcrypt). Falls back to `admin` locally. Set `SECRET_KEY` env var in production.

### New dependencies
`bcrypt==4.1.3` · `python-dotenv==1.0.1`

### Migration from v2.3
On first startup, all 41 entries in `nama_karyawan.py` are imported into `employees` + `employee_aliases`. GitHub token hack retired.

---

### Planned — Security Employee Schedules

> Not yet implemented. Pending answers on shift patterns.

Three security employees work non-standard schedules and do not need lateness tracking. HR only needs to know how many days they attended out of their scheduled working days each month.

**Proposed approach — two new flags on `employees`:**

| Flag | Type | Default | Purpose |
|---|---|---|---|
| `lacak_keterlambatan` | boolean | TRUE | If FALSE: `menit_terlambat` is always 0, lateness column blank in Laporan Individual, Penyesuaian Keterlambatan hidden in cell edit form |
| `hari_kerja` | text (e.g. `"0,1,2,3,4,5,6"`) | `"0,1,2,3,4"` (Mon–Fri) | Determines which days of the week count as workdays for HK Tidak Ada Scan. Security working 7 days would use all 7. |

**What changes:**
- `employees` table: two new columns
- `lateness_service.py`: skip calculation if `lacak_keterlambatan = FALSE`
- Noscan count: use employee's `hari_kerja` instead of `is_weekend` flag
- Cell edit form: hide Penyesuaian Keterlambatan for employees with `lacak_keterlambatan = FALSE`
- Employee management UI: expose both flags when creating/editing an employee

**What does not change:**
- Regular employees: zero impact
- Laporan Individual layout: no new columns
- Export logic: the Menit Terlambat column stays; it just shows 0 / blank for security staff

**Open question before implementation:** Do the three security employees work all 7 days, or on a pattern such as 6 days on / 1 day off? A fixed day-of-week list (`hari_kerja`) works cleanly for 7-day schedules but not for rotating rest days.

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
