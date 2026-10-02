# Murakami Harmonic Analysis Dashboard

A local Streamlit application is planned to review harmonic-voltage distortion spectra from the supplied Excel workbooks and compare them with a user-selected limit series. The authoritative V1 requirements are in [`01_App/Docs/codex_prompt_murakami_harmonics_streamlit_v1_2026-10-02.md`](01_App/Docs/codex_prompt_murakami_harmonics_streamlit_v1_2026-10-02.md).

The folder currently contains the specification and input/reference files; `01_App/app.py` has not been implemented yet. The setup below prepares the development environment and the local launcher without adding dashboard behavior.

## Project files

- `01_App/Input_files/` — mapping, IEC limits, and harmonic result workbooks.
- `Example presentation/` — preliminary results presentation used as project reference material.
- `01_App/requirements.txt` — runtime packages, also used by Streamlit Cloud.
- `environment.yml` — reproducible Conda environment, including the test runner.
- `01_App/run_app.bat` — Windows launcher for the dashboard once `01_App/app.py` is present.
- `graphify-out/` — generated project map and report for future code navigation.

## Create and activate the environment

Use Anaconda Prompt (or another shell where `conda` is initialized) from the project root:

```powershell
conda env create -f environment.yml
conda activate murakami-harmonic-analysis-dashboard
```

To update an existing environment after dependency changes:

```powershell
conda env update -f environment.yml --prune
```

The environment uses Python 3.12. Runtime package versions are maintained in `01_App/requirements.txt`; `environment.yml` installs that file and adds `pytest` for development.

## Run locally

Double-click `01_App/run_app.bat`, or run it from PowerShell:

```powershell
& .\01_App\run_app.bat
```

The launcher activates the dedicated environment and runs `streamlit run app.py` from `01_App`. It currently reports that `app.py` is missing; implement the application from the specification before expecting a dashboard to launch. If Anaconda is installed outside `%USERPROFILE%\anaconda3`, set `CONDA_ROOT` to its installation directory before running the batch file.

## Validate

After application code and tests are added, activate the environment and run the focused tests for changed behavior. The full suite can be run from the project root with:

```powershell
python -m pytest -q
```

For input-dependent changes, use the supplied workbooks as regression data and keep the synthetic test for harmonic orders above 50 described in the app specification. No application test suite exists yet.
