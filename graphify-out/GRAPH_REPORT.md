# Graph Report - Murakami Harmonic Analysis Dashboard (2026-11-09)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 290 nodes · 787 edges · 9 communities
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 27 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from worktree based on commit `f7c20ec0`; includes local uncommitted changes.
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_custom_selections.py
- test_data_loader.py
- app.py
- build_harmonic_figure
- custom_selection_ui.py
- chart_export.py
- test_app_ui.py
- pandas
- cases_from_plot_state

## God Nodes (most connected - your core abstractions)
1. `render_chart_download_dialog()` - 34 edges
2. `build_harmonic_figure()` - 23 edges
3. `render_custom_selection_manager()` - 22 edges
4. `new_rule()` - 18 edges
5. `load_mapping()` - 18 edges
6. `load_result_workbook()` - 18 edges
7. `load_limits()` - 16 edges
8. `build_group_data()` - 15 edges
9. `_dashboard_with_inputs()` - 15 edges
10. `matching_case_codes()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `_display_report()` --uses--> `ValidationReport`  [INFERRED]
  app.py → validation.py
- `test_active_rule_refreshes_when_case_codes_change_in_same_dataset_location()` --calls--> `new_rule()`  [EXTRACTED]
  tests/test_app_custom_selections.py → custom_selections.py
- `test_import_replaces_library_only_after_valid_json_and_clears_active_rule()` --calls--> `new_rule()`  [EXTRACTED]
  tests/test_app_custom_selections.py → custom_selections.py
- `test_import_replaces_library_only_after_valid_json_and_clears_active_rule()` --calls--> `serialise_library()`  [EXTRACTED]
  tests/test_app_custom_selections.py → custom_selections.py
- `test_mapping_filter_preserves_distinct_codes_and_skips_missing_descriptions()` --calls--> `matching_case_codes()`  [EXTRACTED]
  tests/test_custom_selections.py → custom_selections.py

## Import Cycles
- None detected.

## Communities (9 total, 0 thin omitted)

### Custom Rule Logic
Cohesion: 0.10
Nodes (26): new_rule(), _normalise_terms(), normalised_tokens(), parse_library(), phrase_matches(), rule_expression(), rule_matches_description(), rule_summary() (+18 more)

### Workbook Loading
Cohesion: 0.11
Nodes (27): _cached_upload_expansion(), _cached_uploaded_workbook(), discover_input_files(), _drop_fully_blank_rows(), _excel_source(), expand_uploaded_files(), InputFiles, _is_blank() (+19 more)

### Streamlit App Flow
Cohesion: 0.08
Nodes (26): _cached_limits(), _cached_mapping(), _cached_results(), _case_option_label(), _clear_prepared_chart_archive(), _dataset_y_axis_key(), _display_report(), _ensure_positive_number_state() (+18 more)

### Spectrum and THD Plotting
Cohesion: 0.10
Nodes (20): _case_chip_styles(), _dataset_y_axis_maxima(), _integer_y_axis_max(), export_items(), build_group_data(), build_harmonic_figure(), build_thd_data(), build_thd_figure() (+12 more)

### Custom Selection UI
Cohesion: 0.14
Nodes (27): abandon_custom_selection_editor(), advance_saved_selection_radio_generation(), _clear_import_status(), custom_case_selection_key(), custom_case_widget_key(), CustomSelectionView, initialize_custom_selection_state(), render_custom_selection_manager() (+19 more)

### Chart ZIP Export
Cohesion: 0.12
Nodes (11): _artifact_paths(), build_chart_archive(), flush_batch(), report_progress(), ChartExportItem, _reserve_path(), slug_name(), _item() (+3 more)

### App Regression Tests
Cohesion: 0.17
Nodes (15): _dashboard_with_inputs(), _dataset_axis_key(), test_clearing_uploaded_files_resets_the_app_without_a_session_state_error(), test_dashboard_startup_and_global_controls(), test_display_defaults_override_prior_checkbox_state_after_workbook_upload(), capture_spectrum(), capture_thd(), test_download_dialog_exposes_dataset_case_and_output_controls() (+7 more)

### Workbook Validation
Cohesion: 0.29
Nodes (11): test_limit_validation_allows_blank_values_but_rejects_duplicate_orders(), test_result_validation_reports_unmapped_and_duplicate_inputs(), test_supplied_workbooks_pass_validation(), test_unmapped_case_is_a_nonblocking_warning(), _blank(), _column_label(), _duplicate_values(), validate_limits() (+3 more)

### Point Selection
Cohesion: 0.23
Nodes (5): _handle_spectrum_point_selection(), cases_from_plot_state(), test_plot_point_selection_falls_back_to_case_trace_map(), test_plot_point_selection_uses_case_legendgroup(), test_plot_selection_ignores_non_case_traces_and_empty_selections()

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `render_chart_download_dialog()` connect `app.py` to `test_custom_selections.py`, `test_data_loader.py`, `build_harmonic_figure`, `custom_selection_ui.py`, `chart_export.py`, `pandas`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `render_chart_download_dialog()` (e.g. with `_cached_limits()` and `_cached_results()`) actually correct?**
  _`render_chart_download_dialog()` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_custom_selections.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10175763182238667 - nodes in this community are weakly interconnected._
- **Why does `build_harmonic_figure()` connect `build_harmonic_figure` to `test_data_loader.py`, `app.py`, `chart_export.py`, `pandas`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `render_custom_selection_manager()` (e.g. with `_clear_import_status()` and `_select_saved_selection_radio()`) actually correct?**
  _`render_custom_selection_manager()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_data_loader.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10909090909090909 - nodes in this community are weakly interconnected._
- **Why does `render_custom_selection_manager()` connect `custom_selection_ui.py` to `test_custom_selections.py`, `app.py`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._