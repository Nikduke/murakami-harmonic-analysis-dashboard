# Murakami Harmonic Analysis Dashboard

The dashboard reviews harmonic-voltage distortion spectra from Excel workbooks, organized by the case mapping and result worksheet names. It can overlay a limit series selected by the user. It does not calculate THD or assign engineering pass/fail conclusions.

The detailed V1 requirements are in [`01_App/Docs/codex_prompt_murakami_harmonics_streamlit_v1_2026-10-02.md`](01_App/Docs/codex_prompt_murakami_harmonics_streamlit_v1_2026-10-02.md).

## Project files

- `01_App/app.py` — Streamlit interface and application flow.
- `01_App/data_loader.py` — workbook discovery and Excel parsing.
- `01_App/validation.py` — mapping, result, and limit validation.
- `01_App/plotting.py` — order-aligned data preparation and Plotly figures.
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

- exactly one `Cases_description*.xlsx` mapping workbook;
- any `Limits_*.xlsx` limit workbooks;
- other `.xlsx` files are result datasets.

Use **Reload input files** after replacing a workbook in that folder. The app does not upload, edit, or delete source workbooks.

## Run checks

From the project root with the dedicated environment active:

```powershell
python -m pytest -q
```

Tests use the supplied workbooks as regression fixtures and a synthetic dataset through harmonic order 100. They do not modify the supplied workbooks.

## Streamlit Community Cloud

The app uses paths relative to `01_App`, so its input folder is resolved beside `app.py`. For deployment, choose `01_App/app.py` as the entrypoint and keep the app's `requirements.txt` beside it. Add the three required workbooks to the deployed repository's `01_App/Input_files/` folder. Configure access through the hosting platform; the app has no custom authentication or secrets.
