@echo off
setlocal
cd /d "%~dp0"

if not exist "app.py" (
    echo Murakami Harmonic Analysis Dashboard cannot start because app.py is not present yet.
    echo Implement the application using Docs\codex_prompt_murakami_harmonics_streamlit_v1_2026-10-02.md.
    exit /b 2
)

if not defined CONDA_ROOT set "CONDA_ROOT=%USERPROFILE%\anaconda3"
if not exist "%CONDA_ROOT%\Scripts\activate.bat" (
    echo Could not find Anaconda's activate.bat under "%CONDA_ROOT%\Scripts".
    echo Set CONDA_ROOT to the Anaconda installation directory and try again.
    exit /b 3
)

call "%CONDA_ROOT%\Scripts\activate.bat" murakami-harmonic-analysis-dashboard
if errorlevel 1 (
    echo Could not activate the murakami-harmonic-analysis-dashboard Conda environment.
    echo Create it from the project root with: conda env create -f environment.yml
    exit /b 4
)

python -m streamlit run app.py %*
set "APP_EXIT_CODE=%ERRORLEVEL%"
call conda deactivate >nul 2>&1
exit /b %APP_EXIT_CODE%
