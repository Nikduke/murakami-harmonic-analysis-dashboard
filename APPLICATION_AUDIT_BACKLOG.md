# Application audit and verified optimisation backlog

## Update status

V1–V3, D1, P1, P2, and UX1, UX2, UX7, and UX9 are implemented. P1 has visual checks for 4- and 22-case groups; calculation verification remains open. D2 is deferred by the user. UX3–UX6 and UX8 remain proposals for user selection.

| ID | Status | Update |
| --- | --- | --- |
| **V1** | Implemented | Close mapping and result workbook readers to release Windows file locks. |
| **V2** | Implemented | Remove the duplicate native “Select all” action while retaining the custom Select all / Clear all menu. |
| **V3** | Implemented | Remove the repeated harmonic-order range from the location caption. |
| **D1** | Implemented; visually checked at 1536×864 | Compact the first-screen hierarchy and make dataset/location/reference context easier to scan. |
| **D2** | Deferred | Improve trace identity in 22-case plots with marker shapes while preserving the palette. |
| **P1** | Implemented; visually checked at 1536×768 for 4-case and 22-case groups | Add a separate per-case vertical THD bar chart below each group's harmonic spectrum, at the same plot height. |
| **P2** | Implemented; focused tests passed | Upload individual workbooks and complete workbook sets from ZIP archives. |
| **UX1** | Implemented; focused regression passed | Show one correct hover entry per case and harmonic, sort values descending, emphasize violations, and keep the limit last. |
| **UX2** | Implemented; visually checked in Chrome | Render with a fixed Plotly theme and explicitly colored text so page theme overrides cannot wash out chart labels. |
| **UX7** | Implemented | Omit plotted harmonic-data CSVs from chart ZIPs; retain the separate per-plot CSV download and optional case-description CSV. |
| **UX8** | Candidate; needs selected implementation | Restore the red limit dash in the hover marker column, aligned with the colored case dots. |
| **UX9** | Implemented; browser-verified 2026-10-06; 29 tests pass | Default Auto y-axis limits and Show all harmonic numbers on, show manual maxima only when Auto is off, retain maxima while hidden, and remember the live limit series separately for each bus. |

**Marker balance:** Case markers are 8 px at 72% opacity (previously 6 px opaque); red limit ticks are 6.5 px in the current figure code. The case chips remain native Streamlit chips, and D2 remains deferred.

## Runtime map

The application is a single-process Streamlit dashboard. This map follows the current code path from a user opening the page to selecting and exporting plotted data.

1. **Startup and discovery —** The Streamlit entry point is 01_App/app.py. It sets the page layout, then calls discover_input_files from 01_App/data_loader.py on every script run. Discovery scans 01_App/Input_files, classifies Cases_description*.xlsx, Limits_*.xlsx, and other .xlsx workbooks, and ignores Excel lock files beginning with ~$. The root .streamlit/config.toml supplies the theme.
2. **Mapping load and validation —** Mapping is optional. If present, the app allows at most one mapping workbook, then calls _load_cached(_cached_mapping, source). The cached loader calls load_mapping, which reads Cases and Conditions as strings and removes fully blank rows. validate_mapping checks required fields, duplicates, groups, and descriptions. Without mapping, case IDs come directly from result-column names and the app presents one `Cases` group without descriptions. Local-file cache keys use path, modification time, and size; uploaded-file keys use filename and bytes. Each cached loader has a 16-entry limit.
3. **Result load, validation, and location choice —** The user chooses a result workbook in the sidebar. _cached_results calls load_result_workbook, which reads every worksheet and retains the first row as headers so duplicate case names can be validated. validate_result runs for every result sheet on every app rerun. The location selector is built from the selected workbook’s worksheet names; only errors in the selected location block its plot.
4. **Limit load and choice —** If limit workbooks exist, the app selects the only one or presents a source selector when there are several. _cached_limits calls load_limits, which parses the first worksheet’s multi-row headers. validate_limits checks the orders, series, and values. The user explicitly chooses a valid series or “No limit”; no engineering limit is selected automatically. The selection is stored separately for each limit source and location, restored when the user returns to that location, and used to seed its export choice.
5. **Case selection —** When mapping is present, the exact Group values determine the four mapped sections; `Unmapped` and `All` sections are added as applicable. Each section’s cases are intersected with the selected result sheet’s headers. Without mapping, all result columns appear in one `All` section. Available cases start selected. Session state is keyed by dataset, location, and group; the Select all and Clear all menu actions update that state.
6. **Data preparation and rendering —** build_group_data in 01_App/plotting.py sorts by harmonic order and aligns a selected limit by exact order, leaving missing limit orders undefined. build_harmonic_figure renders each case as markers and the limit as short red horizontal markers. Descriptions appear in hover text when mapping is present. In tab mode, `st.tabs(on_change="rerun")` and the `.open` check skip inactive group content; stacked mode renders all groups by design.
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

# THD Update and Remaining Proposal

P1 and P2 are implemented and documented below. P1's calculation verification remains open.

### [P1 · Implemented; visual check complete; calculation verification pending] Add a THD comparison plot to each dashboard case group

**Workbook evidence:** The reference workbook has five visible result sheets with one `Total Harmonic Distortion (%)` clustered-column chart on each. Each chart has 26 case series. The intact sheets combine the 4 `Intact` cases with the 22 `Intact energisation` cases; the transformer-out sheets combine the 4 `TX out` cases with the 22 `TX out energisation` cases. It is therefore one chart per result sheet/scenario-location combination, not one separate chart per mapping group in the Streamlit app.

**Calculation evidence:** IEC TR 61000-3-6:2008, clause 3.26.7, defines THD as the RMS sum of harmonic components from order 2 through a specified upper order `H`, divided by the RMS fundamental; `H` is generally 40 or 50 depending on the application, while higher orders can matter in some cases. The reference workbook’s case formulas use `=SQRT(SUMSQ(CN5:CN53))` over orders 2–50, and label the result THD (%). Its chart series refer to one scalar THD cell per case, but their shared category reference points to harmonic orders 2–25. Treat that category wiring as an artifact of the earlier Excel attempt; use case identifiers as categories in the app. [IEC publication](https://webstore.iec.ch/en/publication/4155)

**Current specification constraint:** The V1 specification excludes automatic THD calculation and says not to label a harmonic spectrum as THD. This proposal is for a distinct, derived summary plot. Selecting it must explicitly amend the calculation and labeling requirements before implementation.

**Implemented behaviour:** Add one separate vertical bar chart inside each existing case-group section, directly below its harmonic spectrum and at the same 505 px plot height. The selected result location (bus) determines the data; each chart uses that group's current case selection and dataset, and each bar represents one selected case. No second selector is added. Case IDs label the bars, descriptions appear on hover, values sort high to low, and each bar reuses the case's spectrum color. Without mapping, the single `Cases` section gets one chart. The current limits workbook contains order-specific limits, not a total-distortion limit, so the THD chart has no limit overlay.

**Calculation basis:** Current result values are supplied as individual voltage-distortion percentages, so the chart calculates `sqrt(sum(u_h[%]²))` without additional scaling for integer harmonic orders 2–50. A case with any missing value in the included range has no THD bar; the app lists its missing harmonic orders instead of treating them as zero. The chart title states the included order range. The harmonic spectrum remains dynamic and may still display orders above 50.

**Verification pending:** Recompute a reference-sheet case from its own orders 2–50 and compare it with that workbook's cached THD formula result. Independently verify the app calculation against selected source values, the explicit order range, missing-value handling, and case colors after sorting. Do not compare reference THD values directly with the current MinFLTSO dataset because the reference workbook is a MaxFLTSO scenario. Confirm only selected cases appear and no per-harmonic limit is presented as a THD limit.

**Acceptance criterion:** Each group’s separate bar chart shows one traceable THD value per selected case for the current bus/location, responds to Select all/Clear all, keeps the 22-case labels readable, stays visually secondary to the harmonic spectrum, and uses explicitly approved calculation and missing-data rules.

### [P2 · Implemented] Upload a workbook set from one ZIP archive

**Current workflow:** The sidebar accepts multiple `.xlsx` uploads. Uploads are held in memory for the current session, merged with project workbooks by filename, and removed by **Clear uploaded files**. A result workbook is required; one mapping workbook and limit workbooks are optional.

**Implementation:** Keep individual `.xlsx` uploads and accept `.zip` bundles in the same uploader. Read `.xlsx` members directly into memory, including members in nested folders; do not extract files to `Input_files/` or another disk folder. Classify each member by its own filename (`Cases_description...`, `Limits_...`, or result workbook), not by the ZIP name. Direct `.xlsx` uploads and ZIP members can be combined in one session.

**Archive handling:** Ignore directories, non-`.xlsx` members, Excel lock files (`~$...`), and common archive metadata such as `__MACOSX/`. Reject corrupt or encrypted archives with a clear message. Detect duplicate workbook basenames within the uploaded set and stop analysis until they are resolved; continue allowing an uploaded workbook to replace a local workbook with the same name under the existing session-upload rule. Preserve the current at-most-one-mapping rule and report missing result data as today. Each ZIP is limited to 100 entries and 100 MiB total uncompressed contents.

**User feedback:** The uploader lists recognized workbook roles and filenames, so the user can confirm that the archive contains results and any intended mapping/limits files. **Clear uploaded files** removes both direct uploads and ZIP members from the session and returns to project workbooks.

**Verification:** Focused tests confirm nested workbook discovery and filename classification, equivalent result frames for direct and ZIP uploads, mixed direct/ZIP uploads, duplicate basename detection, corrupt ZIP handling, and the archive entry-count limit. The implementation reads archive members as bytes and does not write extracted files to disk.

**Outcome:** A user can upload one archive containing the workbook set and get the same parsed results as uploading those `.xlsx` files separately. Archive errors and duplicate basenames are reported, and no files are extracted to disk.

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

## Streamlit/data-app review — selected updates implemented; remaining backlog pending (2026-10-03)

**Review scope:** Read the building-data-apps and Streamlit guidance, reviewed the current app and backlog, and visually inspected the desktop app at 1536×864 in Chrome, including the All group, THD chart, case-description table, and a limit-enabled hover. The current workbook has 52 cases and 49 unique harmonic-order rows per location. At the time of that review, this section recorded candidate updates only; no workbook was changed. Mobile work is out of scope because the app is used on PC.

**Selection status:** UX1 and UX2 were selected and implemented after the review; UX3–UX6 remain candidates. UX7 is tracked separately above.

### [UX1 · P1 · Implemented] Correct limit-enabled hover rows and violation emphasis

**Finding:** With a limit selected, the hover at harmonic order 5 showed each of the four cases twice: its order-5 value and its order-6 value appeared under the same order-5 heading. The result workbook has unique harmonic orders, so this was a chart-hover issue. The normal and violating values were drawn as separate traces per case; unified hover could pick a nearby point from each partial trace. The rows also defeated descending-value reading, and the affected-case red text was not distinct.

**Implementation:** Each case now uses one hover-capable trace over all harmonic orders. Per-point hover text uses dark red for values above the selected limit; other case text remains dark navy. Unified hover remains sorted by value descending, and the red limit dash/value remains last.

**Verification:** A focused regression using the supplied nominal workbook and its TSO_BB1 planning limit checks the order-5 value for every case in the Intact group, confirms one case trace each, and checks violation emphasis. The complete suite passes all 22 tests. Two stale UI assertions were aligned with the existing per-location limit selectors and the All group shown when sections are stacked.

### [UX6 · P1 · Recheck prior update] Ensure large hover panels are not clipped

**Finding:** The user previously reported that the multi-case value hover was cut off and asked for a more compact presentation. The app uses a unified hover panel with one row per plotted trace. The four-case hover inspected in the prior review fits, but 22-, 52-, and 92-case hovers were not visually verified; at 92 rows, the panel is likely to exceed common desktop viewport heights.

**Proposal:** Recheck the existing compacting update at 22, 52, and the newly supplied 92-case count. If rows still clip, compare a multi-column or otherwise space-efficient presentation while preserving case descriptions, descending value order, violation emphasis, and the limit row at the end.

**Acceptance check:** Every selected case remains reachable and legible in the hover at 22, 52, and 92 cases, including when the pointer is near a plot edge; no case or limit information is cut off.

### [UX2 · P1 · Implemented] Make chart text readable in the live theme

**Finding:** The project theme config sets `base = "light"`. During this implementation check, the active Chrome page also rendered light (`body` background `rgb(255, 255, 255)`). On the white Plotly canvas, titles were dark navy, but axis tick and title labels rendered as muted gray (`rgb(128, 132, 149)`), making them harder to read. The currently inspected session did not show the dark page described in the earlier audit.

**Implementation:** Both chart types use an explicit white plotting surface and explicit dark-navy colors for titles, axis titles, ticks, legends, THD bar values, and normal hover text. Violation hover text uses dark red. `st.plotly_chart(theme=None)` keeps Streamlit from replacing these styles with page-theme colors.

**Verification:** After rerunning the app in Chrome, computed SVG fills for both chart titles and x/y axis titles and ticks were `rgb(32, 40, 60)` on the white chart canvas. Focused tests assert explicit contrast colors for the harmonic and THD figures. The inspected browser theme remained light; no theme preference was changed. The complete suite passes all 22 tests.

### [UX3 · P2 · New] Improve readability of the high-case-count THD chart

**Finding:** In All, 52 vertical bars already carry a two-decimal label above every bar and 52 rotated case labels below; the newly supplied result workbooks have 92 cases. At the available chart width, labels become too small and crowded to scan as case count rises. The vertical chart, shared 505 px height, and two-decimal presentation reflect prior user decisions and should be preserved while options are compared.

**Proposal:** Prototype a high-case-count label treatment that keeps exact values available and avoids collisions. Compare options such as selective visible value labels with a compact exact-value detail view, or another layout that preserves case identification. Do not silently drop precision or change the chart to horizontal bars.

**Acceptance check:** The 52- and 92-case views are readable at desktop size; case identity and exact THD values remain recoverable; the four-case view retains the requested two-decimal values; the chart remains vertical and the same height as the spectrum.

### [UX4 · P2 · New] Reduce the vertical footprint of the All-case selector

**Finding:** The 52 selected case chips wrap to four rows above the spectrum and take substantial first-screen space. The new 92-case result sets increase that footprint. All cases selected by default and case-colored chips are explicit preferences.

**Proposal:** Compare a compact selected-state summary with the existing searchable multiselect, keeping the full colored selection visible when the user opens it. Preserve Select all/Clear all and the all-selected default.

**Acceptance check:** The spectrum begins higher on screen without hiding selected-case count, search, Clear all, or the ability to inspect/change cases; group-specific selection state remains intact.

### [UX5 · P2 · Needs user decision] Decide whether startup is upload-first or project-file-first

**Finding:** The no-results screen now clearly tells users to upload a `Total distortion` result workbook and explains that `Cases_description` and `Limits_` workbooks are optional. However, the app auto-discovers and loads workbooks present in `01_App/Input_files`; when those files exist, users bypass that upload-first instruction and see the project data immediately. This overlaps with the earlier request to replace the old-file startup view with a clear upload prompt.

**Decision to make:** Should the app keep auto-loading project workbooks when present, or should a clean launch wait for session uploads even if project workbooks exist? Do not delete or move input workbooks as part of this backlog item.

**Acceptance check after selection:** A first-time user sees the intended startup state; the required result and optional mapping/limits roles are clear; Clear uploaded files returns to the intended default source state.

### Confirmed existing decisions — retain unless selected otherwise

- D2, improving trace identity for 22-case plots without changing the palette, remains **deferred**. The 52-case All view makes the repeated palette colors more apparent, but this review does not reopen D2.
- The upload popover keeps the selected workbook list collapsed, shows a role-count summary, and provides **Clear uploaded files**. The no-results message gives the naming convention and optionality of mapping and limits.
- The inline **Groups:** label, All tab, dataset-condition/location/limit hierarchy, default harmonic-number checkbox, case-colored chips, light limit-bar fill, Bars/Dashes control, and the Case/Description table are present.
- The THD chart is vertical, matches the spectrum height, and shows two decimal places. The limit value remains last in the hover; whether its red dash is visible in the hover marker column is now tracked under UX8.
- The chart-set dialog organizes datasets, per-dataset locations/groups/cases, per-location limits, CSV descriptions, and ZIP folder layout; progress/status feedback is present.
- Current measured workload remains small and the code already caches workbook parsing with bounded entries. No new runtime or large-data bottleneck was established in this review; previous performance measurements remain in **Audit evidence**.

### [UX7 · P2 · Selected and implemented] Keep plotted-data CSVs out of chart ZIPs

**User decision:** The downloadable chart ZIP does not need plotted harmonic-data CSVs.

**Implementation:** Chart ZIPs contain the selected spectrum PNGs, optional THD PNGs, and optional `case_descriptions.csv` files. The separate **Download plotted data (CSV)** action remains available below each live chart.

### [UX8 · P1 · Candidate] Restore the red limit dash in the hover marker column

**Finding:** The latest supplied hover screenshot shows the colored case dots in the left marker column and the limit entry last, but the limit entry has no red dash beside it. In `plotting.py`, the visible red limit trace is skipped by hover; a separate hover-proxy trace supplies the limit value with marker opacity set to zero. That proxy is the likely reason its glyph is missing.

**Proposal:** Keep the limit as the last hover row and render its red horizontal dash in the same left marker column used by the case dots. Do not place a dash in the text label or change the plotted limit bars/dashes.

**Acceptance check:** A fresh live hover at 4, 22, and 92 selected cases shows one red dash aligned with the colored case-dot column; the limit value remains last, and each case still appears once in descending value order.

## Code and visual audit — current review (2026-10-05)

**Scope:** Reviewed the project instructions and specification, Streamlit/data-visualization guidance, workbook discovery/loading, validation, plotting, ZIP export, UI orchestration, documentation, and tests. No application behavior or source workbook was changed. The audit backlog and its out-of-date rendering note were updated.

**Verification:** The full test suite passed: 24 tests in 16.97 s using the dedicated `murakami-harmonic-analysis-dashboard` environment. Both result workbooks in `01_App/Input_files_2/` have three locations, 92 cases per location, and 49 harmonic rows. With the supplied mapping, each location reports 42 unmapped result codes but zero blocking result errors. The current code keeps these cases available in **Unmapped** and **All**. The earlier screenshot showing plotting disabled does not match current validation results and likely reflects an older app run. The open Chrome tab at `localhost:8501` currently shows Streamlit's connection-error screen, so this audit could not capture a fresh live-app view; visual notes below use the supplied screenshots, existing 2026-10-03 browser review, and current figure/UI code.

**Measured workload:** On one 92-case × 49-order location, result-workbook parsing took 67.8 ms median, validation of all three locations 31.5 ms, group-data preparation 3.7 ms, harmonic figure construction 79.2 ms, JSON serialization 6.7 ms (0.195 MiB), THD-data calculation 11.9 ms, and THD figure construction 16.3 ms. The existing synthetic 125-case × 1,000-order workload took 673 ms for figure construction and 146 ms for JSON serialization (3.70 MiB). One real-resolution spectrum + THD + case-CSV export took 2.20 s and produced a 0.32 MiB ZIP; the renderer already batches four chart groups at a time and shows progress.

**Optimisation decision:** No measured interactive bottleneck justifies changing the data or plotting pipeline for the current and tested workloads. Workbook parsing is cached with bounded entry counts; inactive tabs skip plot construction; discovery is cheap; validation of all three current locations is about 31 ms, and harmonic figure construction is about 79 ms per group. THD preparation and figure construction add about 28 ms. ZIP image rendering is the slowest single operation, but the current one-combination export is small and progress is shown. Revisit export speed only if real multi-combination exports feel slow. Cache limits are by entry count rather than total bytes, so large uploaded ZIPs could use substantial process memory; this is a scale watch, not a demonstrated issue with the current ~0.4 MB input set.

**Visual review:** The current code keeps dataset conditions, location, and limit context separate; places the group label inline with tabs; uses explicit dark Plotly text on white charts; and preserves requested marker/limit semantics. Existing open visual candidates UX3, UX4, and UX6 become more relevant with 92-case datasets. UX8 records the missing hover dash visible in the supplied screenshot. The currently disconnected browser prevented checking whether the screenshot also predates recent selector/layout changes.

**Confirmed no-change findings:**

- The app's workload layers are separated across `data_loader.py`, `validation.py`, `plotting.py`, and `chart_export.py`; `app.py` is about 1,520 lines because it also owns the extensive Streamlit state and download dialog. Splitting it would be a maintainability change, not a measured runtime optimisation, so no refactor is proposed.
- The 125 × 1,000 synthetic spectrum remains under the existing 5 MiB figure-JSON guard. No hard-coded order-50 truncation was found in the harmonic spectrum; THD remains intentionally capped at order 50.
- `_drop_fully_blank_rows` uses a row-wise pandas callback, but the 1,000 × 125 stress check took 3.6 ms. This does not justify replacing blank-row semantics or parser code for current files.
- No lint run was available because Ruff is not installed in the project environment; no dependency was added for this audit.

### [UX9 · P1 · Implemented; browser-verified 2026-10-06] Add shared y-axis scales and retain per-location limit choices

**Update:** Place the y-axis scale controls immediately below the divider after limit source/series/display. Keep **Auto y-axis limits** checked by default in a new app session. Store its manual spectrum and THD maxima separately from the conditional number-input widgets so hiding those widgets while Auto is enabled does not erase the values. Apply each maximum consistently across charts of that type from zero, and warn when selected data will be clipped. The chart-set dialog starts with the live settings on first open, retains its own hidden manual maxima, and keeps its controls independent. Preserve each live limit-series choice by limit source and location when the user switches locations; use the stored location choice as the export default.

**Audit finding and correction (2026-10-06):** On an upload-first run, the sidebar controls are mounted only after workbooks are loaded. Initializing the intended defaults before that point did not guarantee the newly mounted checkboxes looked checked: Auto y-axis limits appeared off even though the charts behaved as if Auto were on, and Show all harmonic numbers appeared off despite full-order ticks. The app now gives both widgets explicit checked defaults and uses versioned state keys to avoid stale values from earlier releases. The separate stored manual maxima continue to preserve spectrum and THD caps while Auto hides their number inputs; export controls use the same separate-value pattern.

**Verification:** On the upload-first local app with the four-workbook `Input_files_2` set, both checkboxes were visibly checked after upload. Turning Auto off revealed its manual fields; setting the spectrum maximum to 8% changed the chart range to 8%. Turning Show all harmonic numbers off and on switched between sparse and complete harmonic labels. Selecting a limit series, changing bus, then returning preserved each bus's choice. The chart-set dialog opened with its documented defaults and generated the selected ZIP (three files, 0.1 MB). The complete suite passed all 29 tests in the dedicated environment.
