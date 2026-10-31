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


@app.command()
def synth(
    out: Annotated[Path, typer.Option(help="Output directory.")] = Path("samples/synthetic"),
) -> None:
    """Render the synthetic demo clips (mp4 + ground-truth json) used for development."""
    from showonce.synth.render import write_clip
    from showonce.synth.scene import SCENARIOS

    for scenario in SCENARIOS:
        console.print(f"rendered {write_clip(scenario, out)}")


@app.command()
def moves(
    video: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    labels: Annotated[list[str], typer.Argument(help='Object prompts, e.g. "red block".')],
) -> None:
    """Detect which objects moved where in a clip."""
    from showonce.perception.pipeline import extract_moves

    with MetaClient(get_settings()) as client:
        found = extract_moves(client, video, labels)
    table = Table(title=f"Moves in {video.name}")
    for column in ("#", "object", "from (px)", "to (px)", "frames"):
        table.add_column(column)
    for i, m in enumerate(found, 1):
        table.add_row(
            str(i),
            m.label,
            f"({m.src[0]:.0f}, {m.src[1]:.0f})",
            f"({m.dst[0]:.0f}, {m.dst[1]:.0f})",
            f"{m.start_frame}-{m.end_frame}",
        )
    console.print(table)


@app.command("eval-moves")
def eval_moves(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path(
        "samples/synthetic"
    ),
) -> None:
    """Score move detection on every clip in a directory that has a ground-truth json."""
    import json
    from dataclasses import asdict, replace

    from showonce.evaluate import load_truth, score_moves
    from showonce.perception.pipeline import extract_moves

    settings = get_settings()
    scores = []
    with MetaClient(settings) as client:
        for truth_path in sorted(directory.glob("*.json")):
            video = truth_path.with_suffix(".mp4")
            truth = load_truth(truth_path)
            prompt_to_name = {p: n for n, p in truth["prompts"].items()}
            found = [
                replace(m, label=prompt_to_name[m.label])
                for m in extract_moves(client, video, list(prompt_to_name))
            ]
            scores.append(score_moves(truth["name"], truth, found))
            console.print(f"scored {truth['name']}")
    table = Table(title="Move detection vs ground truth")
    for column in ("clip", "expected", "detected", "correct", "exact"):
        table.add_column(column)
    for s in scores:
        table.add_row(
            s.clip, str(s.expected), str(s.detected), str(s.correct), "yes" if s.exact else "NO"
        )
    console.print(table)
    passed = sum(s.exact for s in scores)
    console.print(f"{passed}/{len(scores)} clips exact")
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    out = settings.runs_dir / "eval_moves.json"
    out.write_text(json.dumps([asdict(s) for s in scores], indent=2))


@app.command("sim-test")
def sim_test(
    runs: Annotated[int, typer.Option(help="Number of random stacks.")] = 10,
    seed: Annotated[int, typer.Option(help="Random seed for layouts.")] = 0,
) -> None:
    """Stack one block on another from random layouts and report success."""
    from showonce.sim.stack_test import run_stack_test

    results = run_stack_test(runs, seed)
    table = Table(title="MuJoCo Panda stack test")
    for column in ("run", "ok", "xy error (mm)", "z error (mm)", "note"):
        table.add_column(column)
    for r in results:
        table.add_row(
            str(r.run),
            "yes" if r.ok else "NO",
            f"{r.xy_error * 1000:.1f}",
            f"{r.z_error * 1000:.1f}",
            r.note,
        )
    console.print(table)
    console.print(f"{sum(r.ok for r in results)}/{len(results)} stacks succeeded")
    if not all(r.ok for r in results):
        raise typer.Exit(code=1)
