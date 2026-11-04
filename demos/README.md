# Demo pairs

Each folder holds one demonstration and what the robot did with it.

| File | What it is |
|---|---|
| `human.mp4` | The clip ShowOnce watched (a copy of `samples/<name>.mp4`, 1280 px wide) |
| `robot.mp4` | The Panda arm repeating the learned task in the simulator |
| `robot_shuffled.mp4` | The same program on a shuffled table (seed 7), with objects found again by SAM |
| `program.json` | The program learned from the clip |

Clips: `toys_into_bin`, `dishes_into_rack`, `lamp_press` (AI-generated) and `pexels_fruit_basket`, `pexels_cut_carrots`, `pexels_sugar_mix` (real Pexels footage).
Rebuild with `uv run showonce demo samples/<name>.mp4 --scene samples/<name>.json --repair`.

`tidy_table` is different: there is no human clip. Muse Spark plans the tidy-up from a picture of the scattered table and the robot carries it out, then SAM checks the result (`uv run showonce tidy samples/tidy_table.json --seed 1 --out demos/tidy_table/robot.mp4`). It holds only `robot.mp4`.
