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
| fruit_into_bowl | 3 of 3 correct | motion | 3/3 steps | 3/3 steps |
| toys_into_bin | 3 of 3 correct | Muse Spark (motion could not explain a move) | 3/3 steps | 3/3 steps |
| dishes_wash | 2 of 2 correct (wipe each plate) | Muse Spark (a wipe is not visible to tracking) | 2/2 steps, 28 of 28 stains | 2/2 steps, 28 of 28 stains |
| chips_open | 1 of 1 correct (open the red bag) | Muse Spark | lid off | lid off |

SAM position error: 0.1 to 3.3 mm across all five clips. The dish-wash clip also passed on seeds
2, 5 and 11, and the chips clip on 11.

## How objects are modelled

Any object in a clip is reduced to a box, cylinder or sphere with a real size, a colour and an
optional handle (`src/showonce/objects.py`). When learning, Muse Spark looks at the first frame
and describes each object (shape, width, depth, height, handle), and the pixels give the colour
of anything whose name has no colour word. The profile is saved with the scene, so the simulator
rebuilds a mug as a mug, an apple as a ball and a book as a flat box, whatever it is called.
Names are only a fallback guess when Muse Spark cannot answer.

- Containers are shallow rimmed trays sized from the box SAM found around them in the clip.
- The sim gripper opens 8 cm, so wider objects are scaled down to fit. Stacking on a ball is
  refused with a clear error.
- SAM finds each object in the sim by a phrase built from its profile ("red mug", "orange
  ball"), so two objects with the same colour and shape would be confused.

## Skills

A learned step is one of four actions, each with its own motion in the simulator and a check
against simulator ground truth (`src/showonce/sim/skills.py`, `executor.py`):

| Action | Meaning | In the sim |
|---|---|---|
| `place_in` | put an object in a container | pick, carry, set down inside the tray's rim |
| `stack_on` | put an object on another | same, onto the top of the one below |
| `wipe` | clean a dish or surface with a sponge or cloth | pick up the tool, sweep a back-and-forth raster over the whole surface; every stain it passes over is cleared |
| `open` | tear open a bag, packet or box | pinch the lid's pull tab, lift the lid off and set it aside; the contents show |

Where things ended up cannot show a wipe or a tear, so when Muse Spark reads either one in the
clip, its reading is used instead of the motion tracking. These are simulator abstractions:
there is no fluid or cloth physics, and a "tear" is a lid coming off, not a bag ripping.
Nothing here has been tested on real footage yet.

## Development

```bash
uv run pytest          # tests (no network needed)
uv run ruff check .    # lint
uv run ruff format .   # format
uv run mypy            # type check
```

## Sample clips

`samples/` holds five test clips of a tabletop task, each with a scene file naming the
objects and containers: `toys_into_bin`, `dishes_into_rack` and `fruit_into_bowl` (30 s,
put-and-place), `dishes_wash` (20 s, scrubbing two stained plates with a sponge) and
`chips_open` (10 s, tearing open a bag of chips next to an untouched packet). They are
AI-generated test footage (see `scripts/generate_videos.py`, a development tool that is not part
of the product), not real recordings. Put real phone clips next to them with a scene file of
the same shape.

Eight synthetic clips with pixel-level ground truth, used for the move-detection eval, are
rebuilt locally with `uv run showonce synth` (written to the git-ignored `samples/synthetic/`).
