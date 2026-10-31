# ShowOnce

Film a tabletop task once. A simulated Franka Panda arm repeats it, including from a new layout of the objects.

Built for the Meta Global AI Developer Hackathon 2026 (indie track, "Push the Frontier").

> Status: work in progress.

## How it works

1. **SAM 3.1** tracks each colored object in the clip. Because hands hide objects during a move, only the resting positions before and after each move are compared.
2. **Muse Spark 1.3** watches the same clip and returns the steps as structured JSON.
3. The steps compile into a symbolic task program (object names and relations, no pixel positions).
4. A **MuJoCo** Panda arm executes the program. A stored program can be replayed on a shuffled layout, with SAM re-finding the objects.

ShowOnce claims task-level imitation (what moved where, in what order). It does not learn dexterous motor skills.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env   # then add your MODEL_API_KEY
uv run showonce --help
```

## Try it

```bash
./scripts/fetch_assets.sh                  # downloads the Panda model
uv run showonce demo samples/toys_into_bin.mp4 --scene samples/toys_into_bin.json
uv run showonce eval-demo                  # score video -> program -> robot on samples/
uv run showonce replay runs/toys_into_bin/program.json \
    --scene runs/toys_into_bin/scene.json --seed 3   # shuffled layout, SAM finds the blocks
uv run showonce eval-replay                # every sample x 3 shuffled layouts
uv run showonce sim-test                   # 10 random block stacks, no API needed
uv run showonce ui                         # the web app (see below)
```

## Web app

`uv run showonce ui` serves the app at http://127.0.0.1:8000. Teach: pick a sample clip (or
upload your own) and learn the task. Task program: edit the steps, and answer a question if the
two readings of the demo disagree. Do: run the steps on a shuffled table in the simulator.

The frontend is React, TypeScript and Tailwind in `web/`:

```bash
cd web && pnpm install
pnpm dev        # http://localhost:5173, proxies /api to the Python server
pnpm build      # writes web/dist, which `showonce ui` serves
pnpm test && pnpm typecheck && pnpm lint
```

## Results on the sample clips

Learn from the clip, then run on shuffled tables (seeds 3 and 7) with SAM finding the objects
in the simulator. These are AI-generated test clips, not real footage.

| Clip | Steps learned | Read by | Seed 3 | Seed 7 |
|---|---|---|---|---|
| dishes_into_rack | 3 of 3 correct | motion | 3/3 steps | 3/3 steps |
| fruit_into_bowl | 3 of 3 correct | motion | failed: SAM found no "orange block" | 3/3 steps |
| toys_into_bin | 3 of 3 correct | Muse Spark (motion could not explain a move) | 3/3 steps | 3/3 steps |

SAM position error where it ran: 0.2 to 1.3 mm. Known weakness: the orange cube on the beige
table is sometimes not found.

## Development

```bash
uv run pytest          # tests (no network needed)
uv run ruff check .    # lint
uv run ruff format .   # format
uv run mypy            # type check
```

## Sample clips

`samples/` holds three 30 s test clips of a tabletop task, each with a scene file naming the
objects and containers: `toys_into_bin`, `dishes_into_rack` and `fruit_into_bowl`. They are
AI-generated test footage (see `scripts/generate_videos.py`, a development tool that is not part
of the product), not real recordings. Put real phone clips next to them with a scene file of
the same shape.

Eight synthetic clips with pixel-level ground truth, used for the move-detection eval, are
rebuilt locally with `uv run showonce synth` (written to the git-ignored `samples/synthetic/`).
