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
from showonce.verify import FixReport

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
        found = extract_moves(client, video, {label: label for label in labels})
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
    from dataclasses import asdict

    from showonce.evaluate import load_truth, score_moves
    from showonce.perception.pipeline import extract_moves

    settings = get_settings()
    scores = []
    with MetaClient(settings) as client:
        for truth_path in sorted(directory.glob("*.json")):
            video = truth_path.with_suffix(".mp4")
            truth = load_truth(truth_path)
            found = extract_moves(client, video, truth["prompts"])
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


@app.command()
def demo(
    video: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Demo clip.")],
    scene: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="Scene json.")],
    out: Annotated[Path | None, typer.Option(help="Output folder (default runs/<name>).")] = None,
    repair: Annotated[bool, typer.Option(help="Retry a failed step with Muse advice.")] = False,
) -> None:
    """Learn a task from a clip, then have the simulated Panda do it."""
    from showonce.demo import learn_from_video, run_in_sim
    from showonce.scene_spec import SceneSpec

    settings = get_settings()
    spec = SceneSpec.load(scene)
    folder = out or settings.runs_dir / spec.name
    with MetaClient(settings) as client:
        learned = learn_from_video(client, video, spec)
        console.print(f"[bold]Learned program[/bold] (from {learned.source})")
        for i, step in enumerate(learned.program.steps, 1):
            console.print(f"  {i}. {step}")
        if learned.semantic is None:
            console.print("[yellow]Muse Spark did not answer, so there is no cross-check.[/yellow]")
        elif learned.discrepancies:
            console.print("[yellow]Muse Spark disagrees:[/yellow]")
            for problem in learned.discrepancies:
                console.print(f"  - {problem}")
        else:
            console.print("[green]Muse Spark read the same steps.[/green]")
        learned.program.save(folder / "program.json")
        if learned.scene is not None:
            (folder / "scene.json").write_text(learned.scene.model_dump_json(indent=2))
        result = run_in_sim(
            learned.program, learned.layout, folder / "sim.mp4", repair=repair, client=client
        )
    table = Table(title="Robot result (simulator ground truth)")
    for column in ("step", "ok", "detail"):
        table.add_column(column)
    for check in result.checks:
        table.add_row(check.step, "yes" if check.ok else "NO", check.detail)
    console.print(table)
    console.print(f"saved {folder / 'program.json'} and {folder / 'sim.mp4'}")
    if not result.success:
        raise typer.Exit(code=1)


@app.command("eval-demo")
def eval_demo(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("samples"),
) -> None:
    """Run video -> program -> robot on every clip with a ground-truth json and score it."""
    import json
    from dataclasses import asdict, dataclass

    from showonce.demo import learn_from_video, run_in_sim
    from showonce.evaluate import load_truth
    from showonce.learn import LearnError
    from showonce.scene_spec import SceneSpec
    from showonce.sim.perceive import NotFoundError

    @dataclass
    class Row:
        clip: str
        program_ok: bool
        robot_ok: bool
        muse_agrees: bool | None = None
        note: str = ""

    settings = get_settings()
    rows: list[Row] = []
    with MetaClient(settings) as client:
        for truth_path in sorted(directory.glob("*.json")):
            truth = load_truth(truth_path)
            spec = SceneSpec.load(truth_path)
            try:
                learned = learn_from_video(client, truth_path.with_suffix(".mp4"), spec)
            except (LearnError, NotFoundError) as exc:
                rows.append(Row(truth["name"], False, False, note=str(exc)))
                continue
            expected = [(s["object"], s["action"], s["target"]) for s in truth["steps"]]
            got = [(s.object, s.action, s.target) for s in learned.program.steps]
            result = run_in_sim(learned.program, learned.layout)
            rows.append(
                Row(
                    truth["name"],
                    got == expected,
                    result.success,
                    None if learned.semantic is None else not learned.discrepancies,
                )
            )
            console.print(f"ran {truth['name']}")
    table = Table(title="Video to robot, all clips")
    for column in ("clip", "program correct", "robot succeeded", "Muse Spark agrees", "note"):
        table.add_column(column)
    for r in rows:
        muse = "n/a" if r.muse_agrees is None else ("yes" if r.muse_agrees else "NO")
        table.add_row(
            r.clip, "yes" if r.program_ok else "NO", "yes" if r.robot_ok else "NO", muse, r.note
        )
    console.print(table)
    console.print(
        f"program {sum(r.program_ok for r in rows)}/{len(rows)}, "
        f"robot {sum(r.robot_ok for r in rows)}/{len(rows)}"
    )
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    (settings.runs_dir / "eval_demo.json").write_text(
        json.dumps([asdict(r) for r in rows], indent=2)
    )


@app.command()
def replay(
    program: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="program.json")],
    scene: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="Scene json.")],
    seed: Annotated[int, typer.Option(help="Seed for the shuffled layout.")] = 1,
    out: Annotated[Path | None, typer.Option(help="Where to save the sim video.")] = None,
    oracle: Annotated[bool, typer.Option(help="Use true sim positions, not SAM.")] = False,
    sam_verify: Annotated[
        bool, typer.Option(help="Check the finished table with SAM and fix a miss once.")
    ] = False,
    slip: Annotated[
        str | None,
        typer.Option(help="Drop this object on open table after the run (a staged miss)."),
    ] = None,
) -> None:
    """Replay a saved program on a shuffled layout, finding objects with SAM 3.1."""
    from showonce.program import TaskProgram
    from showonce.replay import replay as run_replay
    from showonce.scene_spec import SceneSpec

    spec = SceneSpec.load(scene)
    task = TaskProgram.load(program)
    with MetaClient(get_settings()) as client:
        result = run_replay(
            client, task, spec, seed, record_to=out, oracle=oracle, sam_verify=sam_verify, slip=slip
        )
    if result.fixes is not None:
        _print_fixes(result.fixes)
    if result.perception_error_mm:
        console.print(
            "SAM position error (mm): "
            + ", ".join(f"{n} {e:.0f}" for n, e in result.perception_error_mm.items())
        )
    table = Table(title=f"Replay on shuffled layout (seed {seed})")
    for column in ("step", "ok", "detail"):
        table.add_column(column)
    for check in result.checks:
        table.add_row(check.step, "yes" if check.ok else "NO", check.detail)
    console.print(table)
    if not result.success:
        raise typer.Exit(code=1)


def _print_fixes(fixes: FixReport) -> None:
    """What SAM saw at the end of a run and what the robot did about it."""
    table = Table(title="SAM's check of the finished table")
    for column in ("step", "before", "after", "detail"):
        table.add_column(column)
    for before, after in zip(fixes.before, fixes.after, strict=True):
        table.add_row(
            before.step,
            "ok" if before.ok else "MISSED",
            "ok" if after.ok else "MISSED",
            after.detail,
        )
    console.print(table)
    if fixes.retried:
        verdict = "fixed" if fixes.fixed else f"not fixed ({fixes.error or 'still off'})"
        console.print(f"Ran again: {', '.join(fixes.retried)} -> {verdict}")


@app.command()
def tidy(
    scene: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, help="Scene json, e.g. samples/tidy_table.json"
        ),
    ],
    seed: Annotated[int, typer.Option(help="Seed for the messy layout.")] = 1,
    goal: Annotated[str, typer.Option(help="What tidy means.")] = "",
    out: Annotated[Path | None, typer.Option(help="Where to save the sim video.")] = None,
    oracle: Annotated[bool, typer.Option(help="Use true sim positions, not SAM.")] = False,
    slip: Annotated[
        str | None,
        typer.Option(help="Drop this object on open table after the run (a staged miss)."),
    ] = None,
) -> None:
    """Scatter a scene's objects, then see, plan and tidy them with no demo to learn from."""
    from showonce.scene_spec import SceneSpec
    from showonce.tidy import DEFAULT_GOAL, run_tidy

    spec = SceneSpec.load(scene)
    with MetaClient(get_settings()) as client:
        result = run_tidy(
            client,
            spec,
            seed,
            goal=goal or DEFAULT_GOAL,
            record_to=out,
            oracle=oracle,
            slip=slip,
        )
    console.print("Plan: " + "; ".join(str(s) for s in result.program.steps))
    for note in result.dropped:
        console.print(f"[yellow]Skipped:[/yellow] {note}")
    if result.fixes is not None:
        _print_fixes(result.fixes)
    table = Table(title=f"Tidy {spec.name} (seed {seed})")
    for column in ("step", "ok", "detail"):
        table.add_column(column)
    for check in result.checks:
        table.add_row(check.step, "yes" if check.ok else "NO", check.detail)
    console.print(table)
    if not result.success:
        raise typer.Exit(code=1)


@app.command("eval-replay")
def eval_replay(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("samples"),
    layouts: Annotated[int, typer.Option(help="Shuffled layouts per clip.")] = 3,
) -> None:
    """Learn each clip, then replay it on shuffled layouts and score the result."""
    import json

    from showonce.demo import learn_from_video
    from showonce.replay import replay as run_replay
    from showonce.scene_spec import SceneSpec

    settings = get_settings()
    rows: list[dict[str, object]] = []
    with MetaClient(settings) as client:
        for truth_path in sorted(directory.glob("*.json")):
            spec = SceneSpec.load(truth_path)
            learned = learn_from_video(client, truth_path.with_suffix(".mp4"), spec)
            passed = 0
            errors: list[float] = []
            for seed in range(1, layouts + 1):
                result = run_replay(client, learned.program, learned.scene or spec, seed)
                passed += result.success
                errors.extend(result.perception_error_mm.values())
            rows.append(
                {
                    "clip": spec.name,
                    "passed": passed,
                    "layouts": layouts,
                    "mean_sam_error_mm": round(sum(errors) / max(1, len(errors)), 1),
                    "max_sam_error_mm": round(max(errors, default=0.0), 1),
                }
            )
            console.print(f"replayed {spec.name}: {passed}/{layouts}")
    table = Table(title="Replay on shuffled layouts")
    for column in ("clip", "passed", "mean SAM error (mm)", "max SAM error (mm)"):
        table.add_column(column)
    for r in rows:
        table.add_row(
            str(r["clip"]),
            f"{r['passed']}/{r['layouts']}",
            str(r["mean_sam_error_mm"]),
            str(r["max_sam_error_mm"]),
        )
    console.print(table)
    total = sum(int(str(r["passed"])) for r in rows)
    console.print(f"{total}/{layouts * len(rows)} replays succeeded")
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    (settings.runs_dir / "eval_replay.json").write_text(json.dumps(rows, indent=2))


@app.command()
def ui(
    host: Annotated[str, typer.Option(help="Interface to listen on.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to listen on.")] = 8000,
) -> None:
    """Serve the web app: teach a task from a clip, then watch the arm do it."""
    import uvicorn

    from showonce.api.app import create_app

    uvicorn.run(create_app(), host=host, port=port, log_level="info")
