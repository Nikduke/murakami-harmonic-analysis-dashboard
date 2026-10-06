from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import plotly.graph_objects as go
import pytest

import chart_export
from chart_export import (
    EXPORT_BATCH_SIZE,
    ChartExportItem,
    build_chart_archive,
)


def _item(dataset: str) -> ChartExportItem:
    return ChartExportItem(
        dataset=dataset,
        location="TSO BB1",
        group="Intact",
        spectrum_figure=go.Figure(go.Scatter(x=[2, 3], y=[0.2, 0.3], mode="markers")),
        case_descriptions=pd.DataFrame(
            {"Case": ["A.0"], "Description": ["Reference case"]}
        ),
        thd_figure=go.Figure(go.Bar(x=["A.0"], y=[0.36])),
        thd_order_range=(2, 3),
    )


@pytest.mark.parametrize("split_by_folders", [True, False])
def test_chart_archive_contains_pngs_case_csvs_and_unique_names(split_by_folders):
    progress = []
    archive_bytes, file_count = build_chart_archive(
        [_item("Dataset.A"), _item("Dataset-A")],
        split_by_folders=split_by_folders,
        on_progress=lambda fraction, message: progress.append((fraction, message)),
    )

    with ZipFile(BytesIO(archive_bytes)) as archive:
        names = archive.namelist()
        assert len(names) == file_count == 6
        assert len({name.casefold() for name in names}) == 6
        assert archive.testzip() is None
        png_names = [name for name in names if name.endswith(".png")]
        csv_names = [name for name in names if name.endswith(".csv")]
        assert len(png_names) == 4
        assert len(csv_names) == 2
        assert not any("plotted_data" in name for name in names)
        assert all(archive.read(name).startswith(b"\x89PNG\r\n\x1a\n") for name in png_names)
        case_csv = next(name for name in csv_names if "case_descriptions" in name)
        assert "Case,Description" in archive.read(case_csv).decode("utf-8-sig")
        assert "A.0,Reference case" in archive.read(case_csv).decode("utf-8-sig")
        if split_by_folders:
            assert any(name.startswith("dataset_a/tso_bb1/intact/") for name in names)
        else:
            assert any(name.startswith("dataset_a__tso_bb1__intact__") for name in names)

    progress_values = [fraction for fraction, _ in progress]
    assert progress_values == sorted(progress_values)
    assert progress_values[-1] == 1.0


def test_chart_archive_consumes_iterable_in_bounded_batches(monkeypatch):
    item_count = EXPORT_BATCH_SIZE * 2 + 1
    consumed = []
    rendered_batch_sizes = []
    item_counts_at_render = []

    def make_items():
        for index in range(item_count):
            consumed.append(index)
            yield _item(f"Dataset {index}")

    def write_images(fig, file, **_kwargs):
        rendered_batch_sizes.append(len(fig))
        item_counts_at_render.append(len(consumed))
        for path in file:
            Path(path).write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setattr(chart_export.pio, "write_images", write_images)
    archive_bytes, file_count = build_chart_archive(
        make_items(),
        total_items=item_count,
    )

    assert rendered_batch_sizes == [8, 8, 2]
    assert item_counts_at_render == [4, 8, 9]
    assert file_count == item_count * 3
    with ZipFile(BytesIO(archive_bytes)) as archive:
        assert len(archive.namelist()) == file_count
        assert archive.testzip() is None
