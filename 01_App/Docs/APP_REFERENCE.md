# Application reference — current behaviour

**Purpose:** Describe the current Murakami Harmonic Analysis Dashboard for developers and future Codex chats.

**Status:** This document describes the implemented application. It is not a proposed design or a replacement for engineering source data. If the code changes, update this reference in the same change.

## Product scope

The dashboard reads harmonic-voltage results from Excel workbooks. It lets users compare case spectra, view optional limit series, calculate voltage THD, and export selected charts.

The spectrum is not THD. The application does not make engineering pass/fail decisions, infer case groups from case numbers, or alter source workbooks.

## Inputs and file naming

The app scans `01_App/Input_files/` when it runs. It reads `.xlsx` files in that folder. It also accepts `.xlsx` files and `.zip` bundles in the browser. Uploads stay in memory for the current Streamlit session.

| Filename | Role | Required |
| --- | --- | --- |
| `Cases_description*.xlsx` | Case groups, descriptions, and filename-condition definitions | No; at most one |
| `Limits_*.xlsx` | Harmonic limit series | No; users can select **No limit** |
| Any other `.xlsx` file | Result dataset | Yes; at least one |

The role prefixes are case-insensitive. The app classifies files by their own names, including workbooks inside ZIP folders. A result filename does not have to start with `Total distortion`. When that prefix is present, the dashboard uses the tokens after it for the dataset label. It matches those tokens to the optional `Conditions` sheet for readable definitions.

The app does not extract ZIP files. It ignores non-Excel files, `__MACOSX` entries, and Excel lock files beginning with `~$`. An archive can contain up to 100 entries and 100 MiB of uncompressed content. Duplicate workbook basenames in the uploaded set block analysis because the app cannot identify the intended source reliably.

An uploaded mapping workbook replaces local mapping files for the session. Uploaded limit and result workbooks are added to local choices. An upload with the same filename takes precedence over its local counterpart. **Clear uploaded files** removes session uploads and returns to local files. **Reload project workbooks** clears the data cache and scans local files again; it keeps current uploads. Neither action changes files on disk.

## Workbook structure

### Result workbook

- Every worksheet is treated as a location. Its worksheet name becomes the location name.
- The first row contains column headers. The first column must be `Harmonic Order`; each other column is a case code.
- Harmonic orders must be numeric and unique. Case codes must be present and unique. Non-blank result values must be numeric.
- The spectrum uses the harmonic orders supplied by the workbook. It is not capped at order 50.

### Mapping workbook

The workbook must contain `Cases` and `Conditions` worksheets.

- `Cases` requires `Case number`, `Group`, and `Description` columns.
- `Conditions` requires `Token` and `Description` columns.
- Case numbers must be unique and groups must be present. Blank descriptions are allowed with a warning.
- The four standard group names are `Intact`, `Intact energisation`, `TX out`, and `TX out energisation`. Other group names are warned about and remain available in **All**.
- Result codes without mapping entries are preserved. They appear under **Unmapped** and **All**, with no inferred description or group.

Without a mapping workbook, result column names are the case codes. The app still provides **All** and **Custom selections** views, but description-based rules cannot match cases.

### Limit workbook

The first worksheet must contain a `Harmonic Order` column and at least one named limit series. The parser searches the first ten rows for the order heading and supports multi-row or merged series headings. Harmonic orders must be numeric and unique. Limit values can be blank or numeric.

More than one limit workbook can be loaded. The user chooses one limit source, then a series from that source. The app aligns limits to results by harmonic order, not by row position. Missing limit orders have no limit value. It does not interpolate or extrapolate limits.

## Main screen and interaction

The left **Analysis setup** column contains workbook upload and source controls, followed by chart controls.

1. Select a result dataset. The label uses filename condition tokens where available.
2. Select a busbar or location. The selector shows the number of worksheet data rows.
3. Select **No limit** or a limit series. Each location remembers its own series for the selected limit source. A new location starts with the currently active series.
4. If a limit series is active, choose **Bars** or **Dashes**. Bars use a light translucent fill and no borders; the limit marker remains red.
5. Set the y-axis and harmonic-number controls. **Auto y-axis limits** and **Show all harmonic numbers** are on by default. **Show groups as tabs** is also on by default.
6. Choose a group tab, select cases, and inspect the charts. Cases start selected. The case dropdown contains **Select all** and **Clear all** actions.

When there are five or fewer options, dataset, location, and limit choices appear as single-choice lists. Larger lists use searchable selectors.

With a mapping workbook, the live view shows each standard group, **All**, **Unmapped** when needed, and **Custom selections**. Without mapping, it shows **All** and **Custom selections**. Turn off **Show groups as tabs** to stack the sections. The active tab is rendered; stacked mode renders all sections.

Case selection state is kept separately for each dataset, location, and group. Clicking a spectrum point focuses that case in the case selector. Shift-click the selected point to restore all cases in that group. Case colours remain assigned from the full group order, so filtering does not reassign colours.

### Y-axis limits

The live **Auto y-axis limits** checkbox controls both the spectrum and THD charts. When it is off, users can set separate **Spectrum maximum (%)** and **THD maximum (%)** values. The manual values are stored per result dataset and apply across that dataset's locations and groups. Each axis starts at zero. Values above a fixed maximum are clipped and the app displays a warning.

When a dataset has no saved manual maximum, the app finds the highest result value across valid locations. The spectrum default also includes the selected limit value at each location. It rounds each maximum up to a whole percentage point. THD uses result values only.

## Custom case selections

Custom rules match complete ordered phrases in mapped case descriptions. Matching is case-insensitive and normalises supported text variants, including `filters`/`filter`, `strings`/`string`, and common formatting of `154 kV`.

- **Must contain ALL:** every phrase must match.
- **Must contain ANY:** at least one phrase must match when this block is not empty.
- **Must NOT contain:** any matching phrase excludes the case.
- The three blocks are combined with AND. A rule must contain at least one phrase.
- Leave the name blank to generate a readable name from the entered phrases. Duplicate generated names receive a numeric suffix.

The preview and match count use result cases available at the current dataset and location. Choose one saved rule from the radio list to activate it. Each full-width row shows the rule name, summary and match count; clicking anywhere in the row selects it. Only one rule can be active. Selecting the active option again does not clear it. Removing case chips narrows the active view; **Restore matches** restores every match. Dataset or location changes recalculate the matches. **Clear active** returns to normal case selection but keeps the rule. Edit changes apply only after Save; Delete requires confirmation.

The saved rule library belongs to the current session. Users can download a versioned JSON backup or upload a validated JSON file to replace the session library. Invalid JSON leaves the existing library unchanged. There is no server-side or cross-session library storage.

## Charts

### Harmonic spectrum

- The x-axis is harmonic order. The y-axis is harmonic voltage distortion in percent.
- Each case is a set of coloured markers. The app does not connect points with lines.
- **Bars** show each selected limit as a light translucent vertical bar. **Dashes** show short horizontal limit markers. The limit itself is red in both modes.
- Hover shows the point's harmonic order and that case first, with its description when mapping is available. It then shows only other cases above the limit, sorted by value. Violating case text is red. The selected limit is last and has a red dash in the marker column.
- Very large hover details are reduced to a count of other violating cases to limit browser payload size.
- The live chart has a separate **Download plotted data (CSV)** action. This CSV is not added to the chart ZIP.

### Voltage THD

The app displays a separate vertical bar chart below each group spectrum. It calculates one THD value per case as the root-sum-square of the case's voltage-distortion values at integer harmonic orders 2 through the lesser of 50 and the highest order available in that result.

A case receives a THD value only when every expected order in that range is present and has a numeric value. Incomplete cases are omitted from the bars and identified below the chart. Limit series do not affect THD. Bars are sorted from highest to lowest, use the case palette, and display values to two decimal places.

Both chart types use a white Plotly canvas and explicit dark text. This keeps chart labels readable when a browser's theme differs from the project light theme.

## Download chart set

Open **Download charts** in the left control column. The dialog creates a ZIP from the selected combinations.

1. Select result datasets. All available datasets start selected.
2. For each dataset, select locations, case groups, and cases. These start selected. With multiple locations, only case codes available at every selected location can be selected.
3. When mapping and saved rules are available, select rules under **Additional custom chart sets**. They start selected. A rule adds one chart per selected location, using matching cases available at all selected locations. It adds charts alongside the standard group charts.
4. Select one limit series per location. The choice applies to every selected dataset containing that location. The export has one limit source and one Bars/Dashes choice.
5. Keep **Auto y-axis limits** on to calculate ranges from the selected export data. This is one mode switch for the ZIP; automatic maxima remain separate per dataset. When it is off, set separate Spectrum and THD maxima inside each dataset section. Fixed maxima apply across that dataset's selected locations, groups, and custom charts. Export y-axis settings do not change the live charts.
6. Choose whether to include THD charts, show every harmonic number, add case-description CSVs, and organise files into folders. THD and case CSVs are included by default; folder organisation and all harmonic numbers are on by default.
7. Review the chart-set count and options, select **Prepare ZIP**, then select **Download ZIP** when preparation finishes.

The ZIP contains spectrum PNGs and, when enabled and complete, THD PNGs. It can contain one `case_descriptions.csv` per chart group. Without mapping, the CSV contains case codes and blank descriptions. It does not contain plotted harmonic-data CSVs. When a selected saved rule produces charts, the ZIP also contains `custom_selections.json` so the rule can be reused.

For mapped data, standard export groups are the four known groups and **Unmapped** when needed. **All** is a live comparison view, not a separate standard export group. Without mapping, the export uses one **Cases** group containing codes shared across the selected locations.

With folder organisation enabled, files use `dataset/location/group/` folders. Otherwise, filenames identify the dataset, location, group, and chart type. Duplicate output paths receive numeric suffixes. ZIP PNG export uses a fixed 1400 × 505 px canvas at 2× render scale, producing 2800 × 1010 px images independent of the user's display resolution. Local PNG rendering requires Chrome or Chromium through Kaleido.

The dialog reports preparation progress, completion, errors, clipped values, and THD omissions. The prepared ZIP stays in the current session until the dialog state is cleared or the session ends.

## Validation and status behaviour

The **Data validation and sources** expander lists workbook sources and validation by location.

- Mapping errors block the dashboard because group and description data would be unreliable. Mapping warnings do not block it.
- Result structural errors block the selected location's charts. Other locations remain selectable if their result sheets are valid.
- Unmapped result codes produce warnings, not errors.
- Invalid limits can be bypassed by selecting **No limit**. A selected invalid limit cannot be plotted.
- The ZIP cannot be prepared if any selected dataset/location has result errors. Correct the workbook, upload a corrected copy, or remove that location from the export selection.

## Code map and development

| File | Responsibility |
| --- | --- |
| `01_App/app.py` | Streamlit page, session state, selectors, validation flow, chart rendering, and export planning |
| `01_App/data_loader.py` | Local discovery, upload and ZIP expansion, and Excel parsing |
| `01_App/validation.py` | Structural checks for mapping, result, and limit workbooks |
| `01_App/plotting.py` | Harmonic-order alignment, THD calculation, and Plotly figures |
| `01_App/custom_selections.py` | Rule matching, naming, validation, and JSON portability |
| `01_App/custom_selection_ui.py` | Custom selection editor, saved-rule radio list, and session actions |
| `01_App/chart_export.py` | PNG rendering, safe filenames, optional case CSVs, and ZIP writing |
| `01_App/tests/` | Loader, validation, plotting, state, custom-rule, and export regressions |

Use the dedicated Conda environment `murakami-harmonic-analysis-dashboard` with Python 3.12. Run `01_App/run_app.bat` from Windows, or use `streamlit run 01_App/app.py` from the project root after activating the environment. See the [README](../../README.md) for environment setup, dependency details, and Streamlit Community Cloud deployment.

For code changes, keep workbook parsing, validation, and Plotly figure generation separate from Streamlit UI code. Preserve source case codes, units, precision, and traceability. Do not modify supplied workbooks as part of development or tests.
