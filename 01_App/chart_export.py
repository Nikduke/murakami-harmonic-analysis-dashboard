"""PNG and optional case-description CSV chart-set archive generation."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
import re
from tempfile import TemporaryDirectory
from typing import Callable
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from plotting import PLOT_HEIGHT


EXPORT_WIDTH = 1400
EXPORT_SCALE = 2
EXPORT_BATCH_SIZE = 4


@dataclass(frozen=True)
class ChartExportItem:
    """One dataset/location/group and the figures and case metadata to export."""

    dataset: str
    location: str
    group: str
    spectrum_figure: go.Figure
    case_descriptions: pd.DataFrame
    thd_figure: go.Figure | None = None
    thd_order_range: tuple[int, int] | None = None


def slug_name(value: str) -> str:
    """Convert a display name to a stable, filesystem-friendly token."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return slug or "harmonics"


def _reserve_path(path: str, used_paths: set[str]) -> str:
    candidate = path
    source = PurePosixPath(path)
    stem, suffix = source.stem, source.suffix
    index = 2
    while candidate.casefold() in used_paths:
        candidate = str(source.with_name(f"{stem}__{index}{suffix}"))
        index += 1
    used_paths.add(candidate.casefold())
    return candidate


def _artifact_paths(
    item: ChartExportItem,
    split_by_folders: bool,
    used_paths: set[str],
    include_case_descriptions: bool,
) -> dict[str, str]:
    identity = [slug_name(item.dataset), slug_name(item.location), slug_name(item.group)]
    if split_by_folders:
        folder = "/".join(identity)
        names = {
            "spectrum": f"{folder}/harmonic_spectrum.png",
        }
        if include_case_descriptions:
            names["case_descriptions"] = f"{folder}/case_descriptions.csv"
        if item.thd_figure is not None and item.thd_order_range is not None:
            lower, upper = item.thd_order_range
            names["thd"] = f"{folder}/voltage_thd_orders_{lower}-{upper}.png"
    else:
        prefix = "__".join(identity)
        names = {
            "spectrum": f"{prefix}__harmonic_spectrum.png",
        }
        if include_case_descriptions:
            names["case_descriptions"] = f"{prefix}__case_descriptions.csv"
        if item.thd_figure is not None and item.thd_order_range is not None:
            lower, upper = item.thd_order_range
            names["thd"] = f"{prefix}__voltage_thd_orders_{lower}-{upper}.png"
    return {key: _reserve_path(path, used_paths) for key, path in names.items()}


def build_chart_archive(
    items: Iterable[ChartExportItem],
    split_by_folders: bool = True,
    on_progress: Callable[[float, str], None] | None = None,
    total_items: int | None = None,
    include_case_descriptions: bool = True,
    additional_files: dict[str, bytes] | None = None,
) -> tuple[bytes, int]:
    """Render selected figures and supporting files into a ZIP archive."""
    if total_items is None and isinstance(items, Sequence):
        total_items = len(items)
    if total_items == 0 or (isinstance(items, Sequence) and not items):
        raise ValueError("Select at least one dataset, location, and group.")

    def report_progress(fraction: float, message: str) -> None:
        if on_progress is not None:
            on_progress(fraction, message)

    used_paths: set[str] = set()
    batch: list[tuple[ChartExportItem, dict[str, str]]] = []
    processed_items = 0
    file_count = 0
    with TemporaryDirectory(prefix="murakami-chart-set-") as temporary_directory:
        archive_buffer = BytesIO()
        with ZipFile(
            archive_buffer,
            mode="w",
            compression=ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            def flush_batch() -> None:
                nonlocal file_count, processed_items
                if not batch:
                    return

                image_jobs: list[tuple[int, str, go.Figure]] = []
                for item_index, (item, paths) in enumerate(batch):
                    image_jobs.append((item_index, "spectrum", item.spectrum_figure))
                    if item.thd_figure is not None and "thd" in paths:
                        image_jobs.append((item_index, "thd", item.thd_figure))

                image_paths = [
                    Path(temporary_directory)
                    / f"chart_{processed_items * 2 + job_index:04d}.png"
                    for job_index in range(len(image_jobs))
                ]
                pio.write_images(
                    fig=[figure for _, _, figure in image_jobs],
                    file=image_paths,
                    format="png",
                    width=EXPORT_WIDTH,
                    height=PLOT_HEIGHT,
                    scale=EXPORT_SCALE,
                )
                rendered_images = {
                    (item_index, kind): path
                    for (item_index, kind, _), path in zip(image_jobs, image_paths)
                }

                for item_index, (item, paths) in enumerate(batch):
                    for kind in ("spectrum", "thd"):
                        if kind in paths:
                            archive.write(rendered_images[(item_index, kind)], paths[kind])
                            file_count += 1
                    if "case_descriptions" in paths:
                        archive.writestr(
                            paths["case_descriptions"],
                            item.case_descriptions.to_csv(index=False).encode("utf-8-sig"),
                        )
                        file_count += 1

                processed_items += len(batch)
                progress_denominator = total_items or (processed_items + EXPORT_BATCH_SIZE)
                fraction = min(0.95, 0.05 + 0.9 * processed_items / progress_denominator)
                report_progress(
                    fraction,
                    f"Rendered and packaged {processed_items} chart group(s)…",
                )
                batch.clear()

            for item in items:
                batch.append(
                    (
                        item,
                        _artifact_paths(
                            item,
                            split_by_folders,
                            used_paths,
                            include_case_descriptions,
                        ),
                    )
                )
                if len(batch) >= EXPORT_BATCH_SIZE:
                    flush_batch()

            flush_batch()
            if not processed_items:
                raise ValueError("Select at least one dataset, location, and group.")
            for path, contents in (additional_files or {}).items():
                archive.writestr(_reserve_path(path, used_paths), contents)
                file_count += 1

        archive_bytes = archive_buffer.getvalue()

    report_progress(1.0, "Chart set is ready.")
    return archive_bytes, file_count
