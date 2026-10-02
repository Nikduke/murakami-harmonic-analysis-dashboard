# Application audit and verified optimisation backlog

## Update status

The selected updates V1, V2, V3, and D1 are implemented. D2 is deferred by the user.

| ID | Status | Update |
| --- | --- | --- |
| **V1** | Implemented | Close mapping and result workbook readers to release Windows file locks. |
| **V2** | Implemented | Remove the duplicate native “Select all” action while retaining the custom Select all / Clear all menu. |
| **V3** | Implemented | Remove the repeated harmonic-order range from the location caption. |
| **D1** | Implemented; visually checked at 1536×864 | Compact the first-screen hierarchy and make dataset/location/reference context easier to scan. |
| **D2** | Deferred | Improve trace identity in 22-case plots with marker shapes while preserving the palette. |

**Marker balance:** Case markers are 6 px (previously 5 px); red limit ticks are 8 px (previously 10 px). The case chips remain native Streamlit chips, and D2 remains deferred.

## Runtime map

The application is a single-process Streamlit dashboard. This map follows the current code path from a user opening the page to selecting and exporting plotted data.

1. **Startup and discovery —** The Streamlit entry point is 01_App/app.py. It sets the page layout, then calls discover_input_files from 01_App/data_loader.py on every script run. Discovery scans 01_App/Input_files, classifies Cases_description*.xlsx, Limits_*.xlsx, and other .xlsx workbooks, and ignores Excel lock files beginning with ~$. The root .streamlit/config.toml supplies the theme.
2. **Mapping load and validation —** app.py requires exactly one mapping workbook, then calls _load_cached(_cached_mapping, path). The cached loader calls load_mapping, which reads Cases and Conditions as strings and removes fully blank rows. validate_mapping checks required fields, duplicates, groups, and descriptions. Cache keys include the path, modification time, and file size; each cached loader has a 16-entry limit.
3. **Result load, validation, and location choice —** The user chooses a result workbook in the sidebar. _cached_results calls load_result_workbook, which reads every worksheet and retains the first row as headers so duplicate case names can be validated. validate_result runs for every result sheet on every app rerun. The location selector is built from the selected workbook’s worksheet names; only errors in the selected location block its plot.
4. **Limit load and choice —** If limit workbooks exist, the app selects the only one or presents a source selector when there are several. _cached_limits calls load_limits, which parses the first worksheet’s multi-row headers. validate_limits checks the orders, series, and values. The user explicitly chooses a valid series or “No limit”; no engineering limit is selected automatically.
5. **Case selection —** The exact Group value in the mapping workbook determines the four sections. Each section’s cases are intersected with the selected result sheet’s headers. All available cases start selected. Session state is keyed by dataset, location, and group; the Select all and Clear all menu actions update that state.
6. **Data preparation and rendering —** build_group_data in 01_App/plotting.py sorts by harmonic order and aligns a selected limit by exact order, leaving missing limit orders undefined. build_harmonic_figure renders each case as markers and the limit as short red horizontal markers. Descriptions appear in hover text. All four group blocks are executed on each app rerun, including collapsed expanders.
7. **Export and recovery —** Each rendered group offers CSV data and Plotly’s image-download control. CSV bytes are prepared inline for each rendered group. There is no database, background processing, or cross-session persistence. The Reload input files button clears Streamlit’s data cache and reruns discovery and loading. Parser and validation errors are shown in the page and status expander.

## Audit evidence

- Reviewed AGENTS.md, README.md, environment.yml, requirements, the app specification, tests, and all four application modules. No separate architecture note was present.
- Environment: Python 3.12, Streamlit 1.64.0, pandas 2.3.3, Plotly 6.9.0, openpyxl 3.1.5, in the project Conda environment.
- Current data: 52 mapped cases; 3 result locations; 49 harmonic rows per location; groups of 4, 22, 4, and 22 cases. The three source workbooks are about 11 KB, 103 KB, and 11 KB.
- Automated suite: 8 passed in 4.13 seconds. A separate AppTest run had no exceptions; cold run was 1.26 seconds and seven warm reruns had a 150.7 ms median (139.9–189.9 ms).
- The live page was inspected in Chrome at 1536×864, including the 22-case group. The app started on localhost:8501. The actual run_app.bat path also started successfully on port 8502; its Streamlit health endpoint returned HTTP 200. That temporary startup check was stopped afterward.
- Workbook handle experiments used disposable copies in the system temporary folder. The supplied Excel inputs were not changed.
- No production code was changed for this audit.

# Verified Backlog

### [V1 · P1 · Implemented] Close mapping and result workbook readers

**Stage:** Mapping and result parsing, including the local file replacement and Reload workflow.

**Current implementation:** load_mapping and load_result_workbook each create a pandas ExcelFile and read one or more sheets, but never close the ExcelFile explicitly. The returned DataFrames are cached by Streamlit; the file reader itself is not part of the cache result.

**Evidence / problem:** On Windows, immediate os.replace of a temporary copy failed with PermissionError (WinError 32) after each current parser returned. A context-managed ExcelFile version allowed the same copies to be renamed immediately. Frame-by-frame pandas equality checks confirmed identical parsed output. As a control, a copy read through load_limits could be renamed immediately. This prevents the documented local workflow of replacing a mapping or results workbook while the app is running; clearing Streamlit’s cache does not release the open OS file handle.

**Hypothesis tested:** Explicitly closing the ExcelFile releases the Windows file lock without changing parsed values.

**Test / measurement:** Parsed disposable mapping and result copies using the current functions, then attempted to rename them. Repeated with equivalent parsing inside a with pd.ExcelFile(...) context manager; compared every returned DataFrame.

**Result:** Both current ExcelFile-based loaders left their source copies locked. Both context-managed versions closed the files and returned identical frames.

**Recommended update:** Use a context manager around ExcelFile and all sheet reads in both loaders, so the reader closes on success and on parse errors.

**Expected benefit:** Users can replace mapping and result workbooks and use Reload input files without stopping the local Streamlit process.

**Correctness / regression checks:** Add Windows regression coverage that copies each workbook to a temporary path, parses it, renames it immediately, and compares the returned frames. Retain the supplied-workbook value checks and all existing tests.

**Affected areas:** 01_App/data_loader.py: load_mapping and load_result_workbook; 01_App/tests/test_data_loader.py.

### [V2 · P2 · Implemented] Remove the duplicate “Select all” menu option

**Stage:** Case selection in each group.

**Current implementation:** app.py adds custom Select all and Clear all sentinel options and handles both in a callback. Streamlit 1.64.0 also supplies its own Select all option by default for this multiselect; its select_all parameter defaults to 1000.

**Evidence / problem:** In the live browser, opening the case selector showed two entries both labelled “Select all” and one “Clear all”. The native Select all entry selected all cases. The app’s custom action also supports the same behavior, so users see a redundant choice in the compact dropdown they asked to use.

**Hypothesis tested:** The duplicate comes from the Streamlit-native bulk action plus the app’s explicit sentinel.

**Test / measurement:** Inspected the actual multiselect menu with all cases selected and after clearing. Clicked the native Select all entry and verified the four-case selection repopulated. The installed Streamlit API docs confirm that select_all=False hides the native option.

**Result:** The live menu contains both actions; the native option independently selects the cases.

**Recommended update:** Set select_all=False on this multiselect and retain the app’s custom Select all and Clear all actions. This keeps the requested menu behavior while removing the duplicate.

**Expected benefit:** One unambiguous Select all option and one Clear all option in every group menu.

**Correctness / regression checks:** Verify in the browser that each menu has exactly one of each action. Confirm both actions still work in the 4-case and 22-case groups and that session state contains case codes only. Retain the current AppTest state assertions.

**Affected areas:** 01_App/app.py: _handle_case_dropdown_action, _case_option_label, and the case multiselect; 01_App/tests/test_app_ui.py.

### [V3 · P3 · Implemented] Remove the repeated harmonic-order range from the location caption

**Stage:** Dashboard context above the group plots.

**Current implementation:** The header displays the selected harmonic-order range in a metric and repeats it in the following location caption.

**Evidence / problem:** In the live opening view, “2–50” appears in the Harmonic order range metric and again in “Location: TSO_BB1 · Harmonic order 2–50”. The same duplication is present in app.py.

**Hypothesis tested:** Removing the second range label leaves the range available while reducing repeated metadata.

**Test / measurement:** Compared the rendered opening view with the corresponding metric and caption construction in app.py.

**Result:** The range is visible in both places; the dedicated metric already communicates it.

**Recommended update:** Keep the Harmonic order range metric and make the caption identify the location only.

**Expected benefit:** Cleaner context and one less line of repeated metadata above the first plot.

**Correctness / regression checks:** Confirm the location caption remains visible and the metric still reports the selected sheet’s actual minimum and maximum harmonic orders.

**Affected areas:** 01_App/app.py: order_range metric and location caption.

# Hypotheses Requiring Validation

### [D2 · Deferred] Improve trace identity in the 22-case plots without changing the palette

**Status:** Deferred by the user. If resumed later, prototype first and preserve the case palette, marker-only rendering, selected cases, and red horizontal limit marks.

**Observation:** The 22-case groups use 10 colors, then repeat them; all case traces use circle markers. In the live Intact energisation data, all 22 values are below 0.05% at 47 of 49 orders, so most case markers overlap near the baseline. The 22-case legend visibly repeats colors.

**Hypothesis:** A secondary marker shape cycle for cases after the first 10 could help distinguish overlapping traces while preserving the existing palette, marker-only rendering, and engineering values.

**Proposed experiment:** Make a temporary Plotly prototype for the supplied 22-case group, comparing the current all-circle plot with a color-plus-shape pattern such as circles, squares, then diamonds. Inspect both at the same browser size and hover several overlapping orders.

**Metrics:** Count unique color-and-symbol pairs; compare how many overlapping traces can be distinguished in the plot and legend; record any change in legend space or readability.

**Correctness checks:** Assert identical x/y data, case order, descriptions, and limit data; case traces remain markers only; the limit remains red horizontal markers.

**Acceptance criterion:** All 22 cases have distinct color-and-symbol pairs, and a same-size screenshot makes overlapping cases easier to distinguish without obscuring the red limit or making the legend harder to read.

### [D1 · Implemented] Compact the opening hierarchy and dataset context

**Outcome:** Implemented. In the live 1536×864 view, the first plot begins about 100 px earlier while retaining the 480 px chart height. The 1366×768 viewport was not inspected.

**Observation:** At 1536×864, the first plot begins around 600 px below the top of the page, leaving only about half of the 480 px figure visible before scrolling. The large title, three metrics, status disclosure, raw filename plus repeated condition tokens, location/order line, group heading, and case selector precede the plot. The sidebar dataset selector truncates the filename. The extra design pass confirmed the hierarchy gives the application title more prominence than the analysis canvas.

**Hypothesis:** A compact title and one condition-first dataset/location/reference row can make the spectrum the first-screen focus while retaining counts, selected context, and source traceability.

**Design direction:**

- Preserve slate ink `#20283C`, white canvas `#FFFFFF`, cool-gray setup rail `#F3F5F8`, case blue `#4472C4`, soft grid `#E5E8EE`, red limit marks `#FF0000`, and the complete existing ten-color case palette.
- Keep a restrained sans-serif hierarchy: compact application heading, body-sized condition/location context, and the existing chart-label scale. Avoid decorative display type.
- Keep setup controls in the left rail. In the main canvas, use one scannable context row, keep valid data status collapsed, then place the active group selector and full-height spectrum near the top.
- Keep the spectrum visually primary through spacing and hierarchy. Do not add ornamental cards, gradients, or imagery.

```text
┌ Analysis setup ─────────┐  ┌ Murakami Harmonic Analysis Dashboard ──────────┐
│ Result dataset          │  │ Distortion · MinFLTSO · InjTSO · Nom          │
│ Busbar / location       │  │ TSO_BB1 · Reference: selected limit           │
│ Limit series            │  │ 52 mapped cases · 52 traces · orders 2–50    │
└─────────────────────────┘  │ Input data status (collapsed)                  │
                             │ Intact · Cases to compare [compact dropdown]  │
                             │ [full 480 px harmonic spectrum]                │
                             └────────────────────────────────────────────────┘
```

**Proposed experiment:** Build a disposable layout prototype and compare it with the current page at 1536×864 and 1366×768. Try a condition-first context label such as `Total distortion · MinFLTSO · InjTSO · Nom · TSO_BB1 · Reference: no limit`. Keep the exact workbook filename available in Input data status. Retain the 480 px chart and all existing controls; change only the hierarchy and vertical arrangement above the plot.

**Metrics:** Measure the first plot’s top position, visible plot height before scrolling, line wrapping, and whether the dataset/location/reference context remains easy to find.

**Correctness checks:** Compare selected dataset, location, limit, case state, and rendered traces before and after. Confirm the exact workbook filename remains accessible, and no selector or validation message is hidden.

**Acceptance criterion:** Move the first plot at least 80 px earlier at both viewports without truncating key context or reducing chart height. Do not implement if the layout cannot meet that criterion cleanly.

# No-Change Findings

- The operational data path is appropriately split between discovery/parsing, validation, plotting, and Streamlit orchestration. No unused module or duplicate implementation was found in the reviewed code.
- Result locations are derived from workbook sheets, case groups from the mapping, and harmonic orders from source data. The synthetic order-100 regression passes; there is no hard-coded order-50 ceiling.
- Limit alignment uses exact harmonic-order values and does not extrapolate missing higher-order limits. The supplied TSO_BB1/A.0/order-5 value remains 2.176775042841753%, and the selected planning limit is 2.0%.
- The current chart rendering matches the requested visual semantics: case results are unconnected markers, and limits appear as short red horizontal marks. Keep the existing case palette; the shape hypothesis above is intended to complement it.
- All cases being selected initially is explicit user preference. The many chips and large legend in the 22-case group are a consequence of that preference, not a reason to change the default selection.
- Workbook parsing is already cached with path, modification time, and size in the key, and Reload clears those caches. File discovery itself is cheap. Validation distinguishes blocking errors from warnings and reports issues for other locations without blocking a valid selected location.
- The supplied inputs pass the current validators. The temporary Excel lock file in Input_files is ignored by discovery. No data-structure or numerical mismatch was found.

# Removed / Rejected Hypotheses

- **Cache input-file discovery:** 30 repeated scans of the three source workbooks had a 0.071 ms median. Caching would add invalidation complexity for negligible time saved.
- **Cache validation or add fragments for every group:** Full validation of the current mapping, three result sheets, and limits took 21.3 ms median. Generating all four Plotly figures took 72.8 ms median, and the complete warm AppTest rerun took 150.7 ms median with no exceptions. No user-visible delay was observed that justifies a new validation cache or rerun architecture for this dataset.
- **Defer CSV generation until download:** Serializing all four group CSVs took 1.7 ms median. The current eager preparation is not a meaningful cost at this workload.
- **Reduce the 480 px plot height to fit more above the fold:** The 22-case plot already uses a multi-row legend. Shrinking the figure would trade readability for initial viewport coverage; test compacting the header first.
