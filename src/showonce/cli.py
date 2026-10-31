"""Command-line entry point: ``showonce <command>``."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from showonce import __version__
from showonce.config import get_settings
from showonce.meta.client import MetaClient
from showonce.meta.sam import group_by_object

app = typer.Typer(
    help="Teach a simulated robot a tabletop task by filming it once.", no_args_is_help=True
)
console = Console()


@app.callback()
def _main() -> None:
    logging.basicConfig(
        level=get_settings().log_level, format="%(levelname)s %(name)s: %(message)s"
    )


@app.command()
def version() -> None:
    """Print the version."""
    console.print(__version__)


@app.command()
def segment(
    video: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, help="Input clip (mp4/mov).")
    ],
    prompt: Annotated[str, typer.Argument(help='Short noun phrase, e.g. "red block".')],
) -> None:
    """Run SAM 3.1 on a clip and print one row per tracked object."""
    with MetaClient(get_settings()) as client:
        detections = client.segment_video(client.upload_video(video), prompt)
    table = Table(title=f'SAM 3.1: "{prompt}"')
    for column in ("object id", "frames", "first", "last", "mean box area"):
        table.add_column(column)
    for oid, dets in group_by_object(detections).items():
        area = sum(d.box.area for d in dets) / len(dets)
        table.add_row(
            str(oid), str(len(dets)), str(dets[0].frame), str(dets[-1].frame), f"{area:.0f}"
        )
    console.print(table)
