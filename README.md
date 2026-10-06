# Murakami Harmonic Analysis Dashboard

The dashboard reviews harmonic-voltage distortion spectra from Excel workbooks, organized by result worksheet names and optionally by a case mapping workbook. It can overlay a limit series selected by the user and shows a separate vertical per-case voltage THD bar chart for harmonic orders 2–50 under each group spectrum, at the same plot height. It does not assign engineering pass/fail conclusions.

The project defaults to the light Streamlit theme. Plotly charts keep a white canvas and explicit dark titles, axis labels, ticks, legends, and THD values so their text remains readable if the surrounding page uses a different theme. With a limit selected, each case appears once in the hover at each harmonic order; case values are sorted highest first, violations are red, and the limit entry is last with a red dash marker aligned with the case symbols.

When a case mapping workbook is loaded, the four mapped case groups appear as tabs, with **All** always available and **Unmapped** added when result codes lack mapping entries. Turn off **Show groups as tabs** in the sidebar to stack the groups vertically.

Choose the active result dataset, busbar/location, and limit series in the **Analysis setup** sidebar. Up to five choices appear as visible single-choice lists; larger lists use searchable selectors. Locations update with the selected dataset, and limit series update with the selected limit workbook and location. A newly selected location starts with the current limit series; each location then remembers its own choice.

The detailed V1 requirements are in [`01_App/Docs/codex_prompt_murakami_harmonics_streamlit_v1_2026-10-02.md`](01_App/Docs/codex_prompt_murakami_harmonics_streamlit_v1_2026-10-02.md).

## Project files

- `01_App/app.py` — Streamlit interface and application flow.
- `01_App/data_loader.py` — workbook discovery and Excel parsing.
- `01_App/validation.py` — mapping, result, and limit validation.
- `01_App/plotting.py` — order-aligned data preparation and Plotly figures.
- `01_App/chart_export.py` — PNG rendering and ZIP archive generation.
- `01_App/assets/mpe_app_wordmark.png` — page-header MPE logo, rendered at 140 px wide from a 420 × 139 px PNG (3× display density); resampled from `Temp/11 - MPE Logo/MPE_Logo_high_quality.png`.
- `01_App/assets/mpe_app_icon.png` — 128 × 128 px MPE icon used for the browser tab.
- `01_App/Input_files/` — mapping, limit, and result workbooks. Replace files here outside the app.
- `01_App/tests/` — regression and dynamic-harmonic tests.
- `01_App/requirements.txt` — runtime dependencies, also used by Streamlit Community Cloud.
- `.streamlit/config.toml` — light theme colors based on the preliminary results presentation.
- `01_App/run_app.bat` — Windows launcher for the dedicated Conda environment.

## Set up the environment

Use Anaconda Prompt (or another shell where Conda is initialized) from the project root:

```powershell
conda env create -f environment.yml
conda activate murakami-harmonic-analysis-dashboard
```

To update an existing environment after dependency changes:

```powershell
conda env update -f environment.yml --prune
```

The environment uses Python 3.12. `environment.yml` installs the application requirements and adds `pytest` for development.

## Run locally

Double-click `01_App/run_app.bat`, or run it from PowerShell at the project root:

```powershell
& .\01_App\run_app.bat
```

The launcher activates `murakami-harmonic-analysis-dashboard` and starts the `01_App/app.py` entrypoint from the project root, where the shared Streamlit theme is loaded. If Anaconda is installed outside `%USERPROFILE%\anaconda3`, set `CONDA_ROOT` to its installation directory before running the batch file.

The app discovers files in `01_App/Input_files/` using these filename conventions:

- optionally one `Cases_description*.xlsx` mapping workbook (adds case groups and descriptions);
- any `Limits_*.xlsx` limit workbooks;
- at least one other `.xlsx` file as a result dataset.

Open **Add Excel workbooks** in the sidebar to upload individual `.xlsx` workbooks, one or more `.zip` bundles, or a mix. A ZIP may contain workbooks at its root or in subfolders; the app classifies each `.xlsx` member by its own filename and reads it in memory without extracting it to disk. Other archive files, `__MACOSX` entries, and Excel lock files are ignored. Archives are limited to 100 entries and 100 MiB of total uncompressed contents. Invalid or encrypted archives show an error, and duplicate workbook basenames across the uploaded set must be resolved before analysis. A result dataset is required; mapping and limits are optional. Without a mapping workbook, result cases appear by their exact column names without group or description details. With a mapping workbook, unmatched result codes remain plottable and appear under **Unmapped** and **All**; their codes are preserved and no group or description is inferred. In the included case-description CSV, they are labeled `No mapping entry`. Structural result errors still block plotting. The popover lists recognized workbooks and their roles; the sidebar keeps compact role counts and the clear action visible. Uploaded workbooks stay in the current browser session and are parsed in memory. An uploaded mapping workbook replaces the local mapping for that session; uploaded limits and result datasets are added to the local choices, and an upload with the same filename takes precedence over its local counterpart.

Use **Download charts** in the left **Analysis setup** controls to prepare a ZIP of selected harmonic spectra, optional THD charts, and optional case-description CSVs (included by default). Plotted data remains available from each chart's **Download plotted data (CSV)** button and is not added to the ZIP. Choose locations, groups, and cases separately for each result dataset, then choose a limit series for each selected location. The live view remembers a separate limit selection for each location, initializing a new location from the currently active series; the export uses one choice per location across selected datasets. PNG export uses Kaleido 1.4 and requires Chrome or Chromium on the machine running the app; the local Windows setup uses the installed Google Chrome.

Once result data is loaded, **Auto y-axis limits** and **Show all harmonic numbers** are checked by default. In the sidebar, Auto y-axis limits appears below the limit controls and divider. Turn it off to set separate **Spectrum maximum (%)** and **THD maximum (%)** values; each maximum is shared across charts of that type and each axis starts at zero. The app warns when a fixed maximum would clip selected values and remembers manual maxima while Auto is on. Turn off Show all harmonic numbers to use sparse automatic x-axis ticks. The chart-set dialog provides the same y-axis controls, initially copied from the live chart settings when the dialog first opens; changes inside the dialog affect that ZIP only and its manual maxima are also retained while Auto is on.

Dataset controls and chart context use the filename tokens after the shared `Total distortion` prefix. When a mapping workbook includes a `Conditions` sheet, the dashboard also shows the human-readable definition for each recognized token. Full workbook names remain available in the source details. Chart, CSV, and ZIP paths use the condition tokens, location, and group.

Use **Clear uploaded files** to discard the session uploads and return to the files in `01_App/Input_files/`. This does not delete or modify files on disk. Use **Reload project workbooks** after replacing a workbook in that folder.

## Run checks

From the project root with the dedicated environment active:

```powershell
python -m pytest -q
```

Tests use the supplied workbooks as regression fixtures and a synthetic dataset through harmonic order 100. They do not modify the supplied workbooks.

## Streamlit Community Cloud

The app uses paths relative to `01_App`, so its input folder is resolved beside `app.py`. For deployment, choose `01_App/app.py` as the entrypoint and keep the app's `requirements.txt` beside it. Add at least one result workbook to the deployed repository's `01_App/Input_files/` folder; mapping and limits workbooks are optional. Configure access through the hosting platform; the app has no custom authentication or secrets.
