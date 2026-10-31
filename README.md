# ShowOnce

Film a tabletop task once. A simulated Franka Panda arm repeats it, including from a new layout of the objects.

Built for the Meta Global AI Developer Hackathon 2026 (indie track, "Push the Frontier").

> Status: work in progress. See [docs/PLAN.md](docs/PLAN.md) for the plan and [docs/PRD.md](docs/PRD.md) for the full spec.

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

## Development

```bash
uv run pytest          # tests (no network needed)
uv run ruff check .    # lint
uv run ruff format .   # format
uv run mypy            # type check
```

## Sample clips

No footage is committed. Generate 8 synthetic clips (mp4 + ground-truth json) with:

```bash
uv run showonce synth   # writes to samples/synthetic/
```

Put real phone clips in `samples/`.

## Layout

```
src/showonce/
  config.py        settings from env / .env
  cache.py         content-hash JSON cache
  cli.py           `showonce` command
  meta/            Meta Model API client and SAM output parser
  perception/      resting-state and move detection
  sim/             MuJoCo scene, controller, executor
  synth/           synthetic top-down demo clips with ground truth
tests/             unit tests
docs/              PRD and delivery plan
```

## License

MIT
