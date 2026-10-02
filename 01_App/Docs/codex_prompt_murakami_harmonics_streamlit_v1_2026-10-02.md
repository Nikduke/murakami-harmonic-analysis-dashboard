# Codex Development Prompt — Murakami Harmonic Analysis Streamlit App (V1)

## Role

Develop the first working version of a **local Streamlit harmonic-analysis dashboard** for the **Murakami** project.

This is a project-specific V1, but the code structure must be clean enough that the data-loading, validation and plotting logic can later be reused in a more universal MPE harmonic-analysis application and potentially packaged as a standalone desktop executable.

Do not over-engineer this version. The immediate objective is a reliable, clean, client-ready Streamlit application using the existing Excel input structure.

---

## 1. Working location

The application folder is:

```text
01_App/
```

The input folder is:

```text
01_App/Input_files/
```

Current input files are:

```text
Input_files/
├── Total distortion_MinFLTSO_InjTSO_Nom_UPD.xlsx
├── Cases_description_UPD.xlsx
└── Limits_IEC61000_3_6.xlsx
```

Use **application-relative paths** in the code, e.g. resolve `Input_files` relative to `app.py`. Do not hard-code the Windows absolute path in runtime code. The same code must be deployable later to Streamlit Community Cloud.

Before changing anything, inspect the repository and any existing `AGENTS.md`, README, environment files or project conventions and follow them where they do not conflict with this specification.

---

## 2. Deployment approach

### V1

Develop and test locally with Streamlit.

Input files are managed **outside the app** by placing/removing/replacing Excel files in `Input_files`.

Do **not** build file upload, delete or persistent file-management functionality in V1.

A simple **Reload input files** control is useful so that during local development the files can be replaced externally and the application refreshed without restarting the full development process.

### Later deployment

The V1 app will later be pushed to a private GitHub repository and deployed to **Streamlit Community Cloud** with private/email-restricted access.

Authentication will be handled by the hosting platform. Do not implement a custom password or authentication system inside the application.

The app must therefore:

- avoid Windows-only runtime assumptions;
- use relative paths;
- include a complete `requirements.txt`;
- contain no local secrets or credentials;
- not require an external database;
- not require a separately managed server.

### Longer-term direction

A more universal application may later be produced and possibly packaged as an `.exe` for internal MPE use.

For this reason, keep the following separate from Streamlit UI code:

- file discovery;
- Excel parsing;
- validation;
- case mapping;
- limit parsing;
- data transformation;
- Plotly figure generation.

Do not build the executable now.

---

# 3. Purpose of the application

The dashboard is intended to interactively review harmonic-voltage results that are currently presented manually in Excel/PowerPoint.

The user must be able to:

1. select the available result dataset;
2. select the available busbar/location;
3. select the applicable limit curve;
4. review four defined case groups separately;
5. select one or more cases within each group;
6. view the harmonic spectrum for the selected cases;
7. compare the result traces against the selected limit;
8. identify the case through its short case code while still having access to the full case description;
9. use Plotly zoom/hover/legend controls;
10. download/capture useful plot output using Plotly's standard plot controls;
11. optionally download the currently displayed numerical data as CSV if straightforward to implement.

The current requirement is deliberately focused. Do not add speculative analysis modules, compliance scoring, statistical analysis, automated engineering conclusions or additional derived calculations unless they are directly required by this specification.

---

# 4. Terminology: do not incorrectly call the spectrum THD

The current result workbook contains a value for each **harmonic order** and case. It is therefore a harmonic-voltage distortion spectrum.

Do **not** label the plotted spectrum as `THD`.

Use terminology such as:

```text
Harmonic voltage distortion (%)
```

or a concise equivalent consistent with the supplied data.

Do not calculate a single THD value in V1 unless a future input explicitly defines that requirement and calculation basis.

The result data values are already supplied in the units required for presentation. Do not rescale them.

For example, the current result file contains values of approximately `2.1768` at the 5th harmonic for case `A.0` at `TSO_BB1`; this is to be plotted as approximately `2.1768 %`, not multiplied by 100.

---

# 5. Input-file philosophy

All supported project input files are kept in one folder:

```text
Input_files
```

The app must discover and classify files automatically.

Do not require separate `results`, `limits` or `mapping` subfolders for V1.

The classification rules are:

### 5.1 Case/condition mapping file

Any Excel file whose filename starts with:

```text
Cases_description
```

is a mapping-file candidate.

Examples:

```text
Cases_description.xlsx
Cases_description_UPD.xlsx
Cases_description_Murakami.xlsx
```

For V1 there must be exactly **one active mapping file**.

If more than one matching file is found, show a clear blocking validation message rather than silently choosing one.

### 5.2 Limit files

Any Excel file whose filename starts with:

```text
Limits_
```

is a limit-file candidate.

Current example:

```text
Limits_IEC61000_3_6.xlsx
```

The app should be written so that more than one limit file can be supported later without redesign.

### 5.3 Result files

Other supported `.xlsx` files in `Input_files` are result-file candidates.

Current example:

```text
Total distortion_MinFLTSO_InjTSO_Nom_UPD.xlsx
```

Do not depend on this exact filename.

---

# 6. Mapping workbook specification

The current mapping workbook is:

```text
Cases_description_UPD.xlsx
```

It contains two worksheets:

```text
Cases
Conditions
```

## 6.1 `Cases` worksheet

Required columns:

```text
Case number | Group | Description
```

Example:

| Case number | Group | Description |
|---|---|---|
| A.0 | Intact | with 154 kV Filters and WTGs |
| A0.1 | Intact | no 154 kV Filters and with WTGs |
| A.2 | Intact energisation | no Strings |
| A.13 | TX out | with one 154 kV Filter and WTGs |
| A.15 | TX out energisation | no strings |

The `Case number` must match a case-column header in the result workbook exactly.

Do not derive the case group from case-number ranges in the application.

The `Group` field is authoritative.

This is important because future cases may be numbered `A26`, `A27`, etc. even if they logically belong to earlier groups.

The currently agreed groups are exactly:

```text
Intact
Intact energisation
TX out
TX out energisation
```

The current case-number ranges are useful only as a reference to understand the existing file:

```text
Intact:                     A0 to A1.1
Intact energisation:        A2 to A12.1
TX out:                     A13 to A14.1
TX out energisation:        A15 to A25.1
```

Do **not** implement those ranges as grouping logic.

Current mapping contains 52 cases in total:

```text
Intact                     4
Intact energisation       22
TX out                     4
TX out energisation       22
```

Future additional cases must work by adding rows to this mapping worksheet and assigning the required `Group`.

## 6.2 `Conditions` worksheet

Required columns:

```text
Token | Description
```

Current examples include:

| Token | Description |
|---|---|
| MinFLTSO | Minimum TSO fault level |
| MaxFLTSO | Maximum TSO fault level |
| InjTSO | TSO harmonic injection |
| Nom | Nominal parameters |
| Tol | Tolerance parameters |

These tokens occur in result filenames.

The purpose of this sheet is to provide human-readable explanations for compact filename tokens.

Do not hard-code the descriptions into Python.

---

# 7. Result workbook specification

Current example:

```text
Total distortion_MinFLTSO_InjTSO_Nom_UPD.xlsx
```

The current workbook contains three worksheets:

```text
TSO_BB1
BB2_66kV
BB1_66kV
```

These worksheet names define the available **busbars/locations**.

This is a critical requirement:

> Do not hard-code a requirement that all three worksheets must exist.

For some methodologies a result workbook may contain:

- only the PoC/TSO busbar;
- only one or both 66 kV busbars;
- all three busbars;
- potentially another valid location in a future project.

The app must dynamically obtain the available busbar/location selector from the worksheets present in the selected result workbook.

## 7.1 Result sheet structure

Each result sheet uses this structure:

```text
Column A       = Harmonic Order
Columns B...N  = Case results
```

Example:

| Harmonic Order | A.0 | A0.1 | A.1 | A1.1 | ... |
|---:|---:|---:|---:|---:|---:|
| 2 | ... | ... | ... | ... | ... |
| 3 | ... | ... | ... | ... | ... |
| 4 | ... | ... | ... | ... | ... |
| 5 | ... | ... | ... | ... | ... |

The current workbook covers harmonic orders 2 to 50.

However:

> **Never hard-code a maximum harmonic order of 50.**

Future projects may contain harmonics to 100 or another range.

The app must read the harmonic-order values from the selected worksheet and use those values directly.

The app should therefore work with:

```text
2–50
2–100
another contiguous range
or a valid non-contiguous set of harmonic orders
```

provided the source file is internally valid.

No artificial maximum harmonic order should be introduced by the UI or plotting logic.

## 7.2 Case columns

Every case column in a result worksheet must be matched against `Cases -> Case number`.

The current result workbook has already been corrected so that codes such as:

```text
A13.1
A14.1
```

match the mapping workbook.

Do not attempt to "repair" case codes automatically.

If a result workbook contains an unmapped case code, flag it clearly in input validation rather than guessing the intended mapping.

It is acceptable for the mapping workbook to contain future cases that are not present in the currently selected result workbook.

---

# 8. Result filename handling

The current result filename is:

```text
Total distortion_MinFLTSO_InjTSO_Nom_UPD.xlsx
```

The meaningful compact conditions include:

```text
MinFLTSO
InjTSO
Nom
```

The current `_UPD` suffix is a file/revision naming suffix, not an engineering condition.

Do not build a fragile parser that assumes a fixed number of underscore-separated fields.

For V1:

1. use the result filename as the dataset identity;
2. split the filename stem into underscore-separated tokens;
3. match any exact tokens that appear in the `Conditions` mapping;
4. use the mapped descriptions to explain those conditions in the UI;
5. do not invent meanings for unrecognised tokens;
6. an unrecognised token should not crash the app.

The user should be able to see concise dataset information such as:

```text
Total distortion | MinFLTSO | InjTSO | Nom
```

with the descriptions available nearby, for example:

```text
MinFLTSO — Minimum TSO fault level
InjTSO   — TSO harmonic injection
Nom      — Nominal parameters
```

Do not put all long descriptions into every plot legend.

For V1 it is sufficient to select a **result dataset/file** rather than creating separate selectors for every filename-token category. The `Conditions` mapping does not currently define token categories, so do not hard-code speculative categories such as "fault level", "injection" and "parameter set" into the parser.

---

# 9. Limits workbook specification

Current file:

```text
Limits_IEC61000_3_6.xlsx
```

Current sheet:

```text
Sheet1
```

The current file uses a two-row header structure:

| Harmonic orders | Planning Levels |  | Compatibility limits |
|---|---|---|---|
|  | MV (1 kV < Un <= 35 kV) | HV-EHV (35 kV < Un) | LV-MV (Un <= 35 kV) |
| 2 | 1.8 | 1.4 | 2 |
| 3 | 4 | 2 | 5 |
| ... | ... | ... | ... |

The parser should expose the three current limit series with useful combined labels, for example:

```text
Planning Levels — MV (1 kV < Un <= 35 kV)
Planning Levels — HV-EHV (35 kV < Un)
Compatibility limits — LV-MV (Un <= 35 kV)
```

Do not hard-code the current last harmonic order.

Read the harmonic orders from the limit file.

Do not extrapolate limits beyond the orders present in the limit file.

If a result dataset contains harmonics outside the selected limit series:

- continue to display the result values;
- show the limit only where a limit value exists;
- do not invent/interpolate/extrapolate missing limits.

Do **not** automatically select a limit based on busbar voltage. The engineering method may intentionally use a specific reference limit. The user must explicitly select the required limit series.

Include a `None` / `No limit` option.

---

# 10. Main UI structure

Use a clean, engineering-oriented Streamlit layout. Avoid excessive decoration, animation or dashboard gimmicks.

Use a wide page layout.

Suggested title:

```text
Murakami Harmonic Analysis Dashboard
```

A short subtitle may identify this as the interactive harmonic-voltage results viewer.

## 10.1 Global selectors

Use the sidebar or a compact top control area for global selections:

### Dataset

Select one detected result workbook.

Display the recognised condition tokens and their descriptions below or in a compact expander/help section.

### Busbar / Location

Populate dynamically from the sheet names in the selected result workbook.

Examples for the current dataset:

```text
TSO_BB1
BB2_66kV
BB1_66kV
```

Do not show unavailable busbars.

### Limit file / limit series

If one limit file exists, it does not need a prominent separate file selector; the series selector is enough.

If multiple limit files exist later, support:

```text
Limit source
Limit series
```

The selected limit is global and can be shown on all visible case-group figures.

### Reload input files

Provide a small control that:

- clears relevant Streamlit data caches;
- rescans `Input_files`;
- reruns the app.

This replaces upload/delete management in V1.

---

# 11. Four case-group figures

The user needs the cases shown as four logically separate figures/sections:

```text
1. Intact
2. Intact energisation
3. TX out
4. TX out energisation
```

The grouping must come from the `Group` column of the mapping file.

Do not determine group membership from case numbers.

Each group should be an independent Streamlit section or expander and contain:

- a case multiselect;
- a Plotly harmonic spectrum;
- selected-case descriptions in a compact form;
- optional CSV download of the currently plotted data.

Allow sections to be collapsed so the page does not become unnecessarily long.

## 11.1 Case selectors

Use compact case codes in the multiselect:

```text
A.0
A0.1
A.2
...
```

Do not make long descriptions the permanent selector text if this makes the UI difficult to read.

For selected cases, provide the description through one or more of:

- Plotly hover;
- a compact table/expander below the selector;
- concise nearby text.

Do not build custom JavaScript only to provide dropdown hover text in V1.

## 11.2 Plot content

For each visible group figure:

- x-axis = harmonic order;
- y-axis = harmonic voltage distortion (%);
- one trace per selected case;
- selected limit as a clearly distinct reference trace;
- Plotly legend;
- standard Plotly zoom/pan/hover controls;
- standard Plotly image download/camera control.

The x-axis range must be data-driven.

Do not fix it to 50 harmonics.

For many harmonic orders, use sensible automatic ticks so a 2–100 dataset remains readable.

## 11.3 Plot hover

For case traces, include at least:

```text
Case
Full case description
Harmonic order
Distortion value (%)
```

The full description must come from the mapping workbook.

For the limit trace include:

```text
Limit name
Harmonic order
Limit value (%)
```

Keep plot legends concise. Use case codes rather than full case descriptions as trace names.

---

# 12. Data and plot behaviour

### Result/limit alignment

Join the selected limit to the result by harmonic order.

Never assume row number = harmonic order.

### Sorting

Plot harmonic orders in ascending numeric order.

### Missing limits

Missing limit points are gaps/undefined values, not zeros.

### Missing result values

Do not silently replace missing result values with zero.

### Numeric precision

Keep source precision internally.

Use practical display precision in hover/table output, without changing the underlying values.

### No automatic compliance conclusions in V1

Do not generate statements such as:

```text
Filter is inadequate
Case is unacceptable
Design fails
```

The app can visually show results against a selected limit, but engineering interpretation remains with the engineer.

If a simple factual exceedance indicator is added, it must only mean:

```text
result value > selected numerical limit
```

and must not be presented as a broader design conclusion.

---

# 13. Input validation

Input validation is important. Fail clearly rather than silently producing a misleading graph.

Create a compact **Input data status** section or expander.

For valid current inputs it could show information such as:

```text
Mapping file:        Cases_description_UPD.xlsx
Limit file:          Limits_IEC61000_3_6.xlsx
Result datasets:     1
Selected busbars:    3 available
Mapped cases:        52
Unmapped cases:      0
```

Implement validation for at least the following.

## Mapping file

- exactly one `Cases_description*.xlsx` file for V1;
- required `Cases` sheet exists;
- required `Conditions` sheet exists;
- required `Cases` columns exist:
  - `Case number`
  - `Group`
  - `Description`
- required `Conditions` columns exist:
  - `Token`
  - `Description`
- no duplicate case numbers;
- no duplicate condition tokens;
- no blank case number/group for active case rows;
- unknown group values should be reported clearly.

## Result workbook

For every result worksheet considered a busbar/location:

- first required column is `Harmonic Order`;
- at least one case column exists;
- harmonic orders are numeric;
- harmonic orders are unique within a sheet;
- duplicate case columns are invalid;
- result values must be numeric or blank;
- every result case code must exist in the mapping file.

A mapping case not present in the selected result workbook is not an error.

A result workbook containing only one busbar worksheet is valid.

## Limit workbook

- harmonic-order column can be identified;
- harmonic orders are numeric and unique;
- at least one limit series can be parsed;
- limit values are numeric or blank;
- missing higher-order limits are allowed.

## Errors vs warnings

Blocking structural problems should prevent plotting the affected dataset and show a clear message.

Non-critical issues should be warnings.

Do not hide parsing failures in logs only.

---

# 14. Expected current-data checks

Use the supplied files as regression fixtures during development.

At minimum, verify that the current data produces the following:

```text
Mapping:
52 case mappings
4 groups
```

Current group counts:

```text
Intact                     4
Intact energisation       22
TX out                     4
TX out energisation       22
```

Current result workbook:

```text
3 busbar sheets:
TSO_BB1
BB2_66kV
BB1_66kV
```

Current harmonics:

```text
2 through 50
```

but this must not become a code limitation.

Known numerical regression check:

```text
Dataset: Total distortion_MinFLTSO_InjTSO_Nom_UPD.xlsx
Sheet:   TSO_BB1
Case:    A.0
Order:   5
Value:   approximately 2.176775042841753
```

Known current limit check:

```text
Limits_IEC61000_3_6.xlsx
Harmonic order: 5
Planning Levels — HV-EHV (35 kV < Un): 2.0
```

These checks are intended to detect accidental rescaling or incorrect row/column parsing.

---

# 15. Test dynamic harmonic range explicitly

The current data stops at the 50th harmonic, but the application requirement is dynamic.

Add a small automated test using a temporary/synthetic dataframe or workbook-equivalent parser input with harmonic orders extending to at least:

```text
100
```

Verify that:

- all values are retained;
- the plot data reaches the 100th harmonic;
- no UI/data-loader constant truncates at 50;
- limits remain undefined beyond their actual available range rather than being extrapolated.

Do not modify the supplied project workbooks to perform this test.

---

# 16. Suggested code structure

Keep the code compact but modular.

A suitable structure is:

```text
01_App/
├── app.py
├── data_loader.py
├── validation.py
├── plotting.py
├── Input_files/
│   ├── Cases_description_UPD.xlsx
│   ├── Limits_IEC61000_3_6.xlsx
│   └── Total distortion_MinFLTSO_InjTSO_Nom_UPD.xlsx
├── tests/
│   ├── test_data_loader.py
│   └── test_validation.py
├── .streamlit/
│   └── config.toml
├── requirements.txt
└── README.md
```

Do not create unnecessary architectural layers/classes.

Prefer clear pure functions for parsing and transformation.

For example:

```text
discover_input_files()
load_mapping()
load_result_workbook()
load_limits()
validate_mapping()
validate_result()
validate_limits()
build_harmonic_figure()
```

The Streamlit layer should mainly orchestrate these functions and manage UI state.

---

# 17. Technology

Use:

```text
Python
Streamlit
Plotly
pandas
```

Use a normal Excel-reading dependency compatible with pandas/Streamlit Cloud as required.

Pin sensible dependency versions in `requirements.txt` once the implementation has been tested.

Do not introduce a database, API server, React frontend or separate backend service.

Use `st.cache_data` where it materially improves workbook loading, but make cache invalidation/reload straightforward.

---

# 18. Styling

The app should look like a professional engineering tool, not a generic demo.

Use:

- wide layout;
- clear hierarchy;
- compact controls;
- readable engineering labels;
- restrained colours;
- consistent Plotly formatting;
- adequate plot height;
- legends that do not obscure the data;
- no unnecessary icons/animations.

Do not encode engineering meaning using colour alone.

Ensure plots remain readable when several cases are selected.

A light default theme is acceptable. Do not spend significant time building a custom design system in V1.

---

# 19. Downloads

V1 should at least preserve Plotly's standard image-download control.

If straightforward, also provide a Streamlit CSV download for the currently selected group plot containing:

```text
Harmonic Order
selected case columns
selected limit column, if any
```

The CSV filename should include enough context to identify:

```text
dataset
busbar
group
```

Do not build PDF or PowerPoint report generation in V1.

---

# 20. Explicit non-goals for V1

Do not implement the following unless required to make the defined V1 work:

- file upload through the dashboard;
- file deletion through the dashboard;
- persistent cloud storage;
- user accounts;
- custom passwords;
- database;
- `.exe` packaging;
- automated PowerPoint generation;
- automated report writing;
- advanced statistical analysis;
- automatic THD calculation;
- automatic selection of the "correct" engineering limit;
- automatic engineering pass/fail conclusions beyond direct numerical comparison;
- editing the Excel input files from the app;
- case grouping inferred from numeric ranges.

These can be considered later after the Murakami version has been validated.

---

# 21. Development sequence

Follow this order.

## Stage 1 — Inspect and document inputs

Read the actual files in `Input_files`.

Confirm their structure against this specification.

If the actual files conflict with the specification, do not silently reinterpret them. Report the mismatch before implementing logic around it.

## Stage 2 — Data layer

Implement:

- input-file discovery;
- file classification;
- mapping parser;
- result parser;
- limits parser;
- validation;
- result/limit alignment by harmonic order.

Test this independently of Streamlit.

## Stage 3 — Regression tests

Add tests against the supplied data and the known values in this specification.

Add the synthetic dynamic-harmonic-range test to at least the 100th harmonic.

## Stage 4 — Plotting layer

Create Plotly figure generation as functions independent from Streamlit.

Verify:

- multiple selected cases;
- dynamic harmonic range;
- selected limit;
- useful hover data;
- concise legend.

## Stage 5 — Streamlit UI

Build the global selectors and four case-group sections.

Do not duplicate plotting logic across the four groups.

## Stage 6 — Local functional test

Run the application locally.

Exercise at least:

- each current busbar;
- each of the four groups;
- single-case selection;
- multi-case selection;
- each current limit series;
- no-limit mode;
- reload input files;
- collapsed/expanded group sections.

Check the browser UI for clipping, unreadable legends and avoidable horizontal scrolling.

## Stage 7 — Cloud readiness

Confirm:

- no absolute local paths;
- complete `requirements.txt`;
- no credentials;
- no Windows-only dependencies;
- README contains local run instructions and short Streamlit Cloud deployment notes.

Do not deploy to Streamlit Cloud unless explicitly asked.

---

# 22. Acceptance criteria

The V1 is acceptable only when all of the following are true:

1. The app starts locally without manual code edits.
2. Input files are discovered from the relative `Input_files` folder.
3. `Cases_description*.xlsx` is used as the mapping-file convention.
4. `Limits_*.xlsx` is used as the limit-file convention.
5. The current result workbook is detected automatically.
6. Available busbars come from the workbook sheet names.
7. A result workbook does not need to contain all three current busbars.
8. Harmonic orders are read from the source data with no hard-coded maximum.
9. A synthetic 100th-harmonic test passes.
10. Case codes match the mapping exactly; unmapped codes are reported.
11. The four figures use the mapping `Group`, not numeric case ranges.
12. Future A26/A27-type cases can be assigned to any group by editing the mapping file only.
13. Full case descriptions are available without making the plot legend excessively long.
14. The selected limit is joined by harmonic order.
15. Limits are not extrapolated where they do not exist.
16. The current 5th-harmonic regression value for `TSO_BB1 / A.0` is preserved.
17. Plotly interactive controls work.
18. The user can select multiple cases within each group.
19. Input validation is visible and understandable.
20. The code is structured so data/plot logic is not tied unnecessarily to Streamlit.
21. The app is ready to be moved to Streamlit Community Cloud without changing path logic.
22. All automated tests pass.

---

# 23. Deliverables

When complete, leave the working application in `01_App` and provide:

```text
app.py
data_loader.py
validation.py
plotting.py
requirements.txt
README.md
tests/
.streamlit/config.toml   (if used)
```

You may adjust this exact file split if there is a simpler equivalent, but preserve the separation between input/data logic, validation, plotting and Streamlit UI.

At the end of the task, provide a concise implementation report containing:

- files created/changed;
- how to run the app locally;
- tests executed and their results;
- any input-data issues found;
- any deliberate deviations from this specification and why;
- remaining limitations that belong to a future version.

---

# 24. Engineering principles

Treat the Excel files as engineering source data.

Do not:

- guess missing case mappings;
- silently rename case codes;
- silently convert units;
- extrapolate limits;
- assume all projects have the same busbars;
- assume all projects stop at the 50th harmonic;
- infer case groups from numbering;
- label a harmonic spectrum as THD;
- hide invalid input structures.

Prefer explicit validation and traceable behaviour.

The objective is not merely to produce a visually attractive dashboard. The numerical result displayed for a selected dataset/busbar/case/harmonic must remain traceable to the corresponding source workbook cell.
