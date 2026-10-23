# Murakami Harmonic Analysis Dashboard

The dashboard reviews harmonic-voltage distortion spectra from Excel workbooks, organized by result worksheet names and optionally by a case mapping workbook. It can overlay a limit series selected by the user and shows a separate vertical per-case voltage THD bar chart for harmonic orders 2–50 under each group spectrum, at the same plot height. It does not assign engineering pass/fail conclusions.

The project defaults to the light Streamlit theme. Plotly charts keep a white canvas and explicit dark titles, axis labels, ticks, legends, and THD values so their text remains readable if the surrounding page uses a different theme. Hover a harmonic point to see that case first, other cases above the selected limit beneath it, and the selected limit last with a red dash in the symbol column. The hovered case code is bold; other violating case codes use regular weight. When no limit is defined at that order, the hover says `No value at this order`. Very large hover payloads show the number of other violations to keep the chart responsive. Click a point to focus the case; Shift-click the selected point to restore all cases in the group. Case colors stay tied to the full group order when you narrow the selection, including in the spectrum, THD chart, and case chips. The case selector remains available for adding or removing comparison cases.

When a case mapping workbook is loaded, the four mapped case groups appear alongside **All**, optional **Unmapped**, and **Custom selections**. Without a mapping workbook, **All** and **Custom selections** remain available. **Show groups as tabs** is available in either state; turn it off to stack the sections vertically. Custom rules need mapping descriptions to match cases.

The **Custom selections** tab (or section in stacked mode) lets you save filters on the mapping workbook's case **Description** text. Add complete phrases under **Must contain ALL**, **Must contain ANY**, and **Must NOT contain**; ALL terms are combined with AND, ANY terms with OR, and NOT terms are excluded, with the three blocks joined by AND. Leave **Name** blank to generate a readable name from the conditions; duplicate generated names receive a number suffix. The preview and match count use every result case available in the current dataset and location, across the predefined case groups. Select a row in the saved-selections table to activate it immediately and update the existing case chips, spectrum and THD charts. Removing chips narrows only the current view; use **Restore matches** to restore all matches. Dataset or location changes keep the active rule and recalculate its matches. **Clear active** returns to normal case selection without deleting the saved rule. Edit changes take effect only after Save; Cancel discards the draft, and Delete requires confirmation. Actions sit below the saved-selections table. Download selections to keep a versioned JSON copy; upload validates and imports a JSON file to replace the saved list for this session, while invalid files leave the existing list unchanged. Rules stay in Streamlit session state, so changes are not automatically carried into a new session.

Choose the active result dataset, busbar/location, and limit series in the **Analysis setup** sidebar. Up to five choices appear as visible single-choice lists; larger lists use searchable selectors. Locations update with the selected dataset, and limit series update with the selected limit workbook and location. A newly selected location starts with the current limit series; each location then remembers its own choice.

The detailed V1 requirements are in [`01_App/Docs/codex_prompt_murakami_harmonics_streamlit_v1_2026-10-02.md`](01_App/Docs/codex_prompt_murakami_harmonics_streamlit_v1_2026-10-02.md).

## Project files

- `01_App/app.py` — Streamlit interface and application flow.
- `01_App/data_loader.py` — workbook discovery and Excel parsing.
- `01_App/validation.py` — mapping, result, and limit validation.
- `01_App/plotting.py` — order-aligned data preparation and Plotly figures.
- `01_App/chart_export.py` — PNG rendering and ZIP archive generation.
- `01_App/custom_selections.py` and `01_App/custom_selection_ui.py` — deterministic description matching, rule validation/JSON portability, and the session-scoped custom-selection controls.
- `01_App/assets/mpe_app_wordmark.png` — page-header MPE logo, rendered at 140 px wide from a 420 × 139 px PNG (3× display density); resampled from `Temp/11 - MPE Logo/MPE_Logo_high_quality.png`.
- `01_App/assets/mpe_app_icon.png` — 128 × 128 px MPE icon used for the browser tab.
- `01_App/Input_files/` — mapping, limit, and result workbooks. Replace files here outside the app.
- `01_App/tests/` — regression, UI-state, custom-selection, and dynamic-harmonic tests.
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

Use **Download charts** in the left **Analysis setup** controls to prepare a ZIP of selected harmonic spectra, optional THD charts, and optional case-description CSVs (included by default). Plotted data remains available from each chart's **Download plotted data (CSV)** button and is not added to the ZIP. Choose locations, groups, and cases separately for each result dataset; each location shows its workbook row count. Then choose a limit series for each selected location. The live view remembers a separate limit selection for each location, initializing a new location from the currently active series; the export uses one choice per location across selected datasets. PNG export uses Kaleido 1.4 and requires Chrome or Chromium on the machine running the app. The repository-root `packages.txt` installs Chromium on Streamlit Community Cloud; the local Windows setup uses installed Google Chrome.

Within each dataset section, select saved rules under **Additional custom chart sets** to add charts alongside the standard group charts. A rule matches mapped case descriptions among cases available at all selected locations and adds one chart per selected location; rules with no matches are skipped. The ZIP includes the rules that produced charts in `custom_selections.json`; import that file through **Upload selections** to reuse them. When case CSVs are enabled, each chart's CSV lists its exact cases.

Once result data is loaded, **Auto y-axis limits** and **Show all harmonic numbers** are checked by default. In the sidebar, Auto y-axis limits appears below the limit controls and divider. Turn it off to set separate **Spectrum maximum (%)** and **THD maximum (%)** values for the active dataset. Live manual maxima are remembered separately for each result dataset and shared across its locations and groups. When a dataset has no saved maxima, the app finds the highest result value across its valid locations, includes each location's selected limit for Spectrum, then rounds the maxima up to whole percentage points. THD is calculated from result data. Each axis starts at zero, and the app warns when a fixed maximum would clip selected values. Turn off Show all harmonic numbers to use sparse automatic x-axis ticks.

The chart-set dialog has one **Auto y-axis limits** checkbox for the whole ZIP. When it is off, set Spectrum and THD maxima inside each dataset's section. Automatic and fixed ranges are still independent per dataset and apply across that dataset's exported locations, groups, and custom chart sets. New fixed values start from the selected export scope, and these export settings do not change the live charts. Enter the same maxima in multiple dataset sections when you want matching scales.

Dataset controls and chart context use the filename tokens after the shared `Total distortion` prefix. When a mapping workbook includes a `Conditions` sheet, the dashboard also shows the human-readable definition for each recognized token. Full workbook names remain available in the source details. Chart, CSV, and ZIP paths use the condition tokens, location, and group.

Use **Clear uploaded files** to discard the session uploads and return to the files in `01_App/Input_files/`. This does not delete or modify files on disk. Use **Reload project workbooks** after replacing a workbook in that folder.

## Run checks

From the project root with the dedicated environment active:

```powershell
python -m pytest -q
```

Tests use the supplied workbooks as regression fixtures and a synthetic dataset through harmonic order 100. They do not modify the supplied workbooks.

## Streamlit Community Cloud

The app uses paths relative to `01_App`, so its input folder is resolved beside `app.py`. For deployment, choose `01_App/app.py` as the entrypoint and keep the app's `requirements.txt` beside it. The repository-root `packages.txt` installs Chromium, which Kaleido uses to render PNGs for chart ZIP exports. Changing `packages.txt` triggers a Cloud dependency rebuild; use ZIP export after that rebuild finishes. Add at least one result workbook to the deployed repository's `01_App/Input_files/` folder; mapping and limits workbooks are optional. Configure access through the hosting platform; the app has no custom authentication or secrets.
