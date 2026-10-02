# AGENTS.md

## Project

- The application is **Murakami Harmonic Analysis Dashboard**, a local Streamlit viewer for harmonic-voltage results.
- Read `01_App/Docs/codex_prompt_murakami_harmonics_streamlit_v1_2026-10-02.md` before application work; it is the detailed product and engineering specification.
- Keep runtime paths relative to `01_App`; input workbooks remain together in `01_App/Input_files/`.

## Environment

- Use the dedicated Conda environment `murakami-harmonic-analysis-dashboard` with Python 3.12. Never use `base` for project work.
- `environment.yml` defines the Conda environment; `01_App/requirements.txt` lists runtime packages for local use and Streamlit Cloud.
- Do not commit Conda or virtual-environment directories, local secrets, or machine-specific state.

## Engineering and maintenance

- Treat the supplied Excel workbooks as engineering source data. Preserve case codes, units, source precision, and traceability; do not infer groups from case numbering, align by row position, extrapolate limits, label the spectrum THD, or add engineering conclusions contrary to the specification.
- Keep data discovery/parsing, validation, and Plotly figure generation independent of Streamlit UI code. Prefer small, focused changes and avoid speculative layers.
- Do not modify supplied input workbooks as part of tests or application changes.
- Add and run focused tests for changed data or plotting behavior against the supplied workbooks; retain coverage for harmonic orders beyond 50 where relevant. Run the full test suite when practical.
- Update `README.md` when setup, dependencies, input locations, or run commands change. Keep paths relative in project documentation.
