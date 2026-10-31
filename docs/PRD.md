# ShowOnce — Product Requirements Document

Oct 31, 2026 · @Abu Bakar Siddik

## Overview

ShowOnce lets you teach a simulated robot arm a tabletop task by filming yourself doing it once, then the robot repeats it, including from a new layout of the objects. It targets the Meta Global AI Developer Hackathon 2026, indie developer track, theme "Push the Frontier" (robotics and physical systems).

- **Input:** a 5 to 15 second phone video of a person moving 3 or 4 colored blocks or cups.
- **Output:** a simulated Franka Panda arm in PyBullet repeating the task, a reusable task program, and a score comparing the sim result with the video.
- **Meta stack:** SAM 3.1 for object geometry and Muse Spark 1.3 for reading the video into a step plan.
- **Claim:** task-level imitation (what moved where, in what order), not learning of dexterous motor skills.
- **Deadline:** Thursday Nov 5, about 08:00 in Dhaka. This is Wednesday Nov 4, 9pm ET in a participant's notes, so confirm it on the submit page.

## Problem and opportunity

Programming a robot normally takes an expert or a large demonstration set, while showing a task once with a phone is what people expect. ShowOnce tests whether a video-and-language stack can turn one casual demonstration into a reusable robot task.

Why it should compete:

- Past winners pair a one-sentence idea with a live, visible demo. GibberLink at the ElevenLabs London hackathon is the clearest example, and Arto at OpenAI's Agents Everywhere put agents in charge of a simulated Paris Metro line.
- A February sim-first robotics hackathon drew 94 projects with no hardware, but whether Meta's "Push the Frontier" theme accepts a simulation-only project is unconfirmed (see open questions).
- It chains two Meta models in one pipeline, which matches the "use of Meta AI tooling" criterion in a participant's notes on judging (impact, Meta tooling, technical depth, demo; unofficial).
- "Push the Frontier" is probably less crowded than "Build for Your World", though that is an assumption.

Crowding to avoid: at least one public entry already tracks products through bench video with SAM 3.1, and GoferAI turned human demo videos into robot policies at a sim-first robotics hackathon. ShowOnce differs through the replay from a new layout and the closed loop into simulation.

## Goals and non-goals

By the deadline, a stranger should be able to film a simple tabletop task and watch the robot repeat it, twice, from two different layouts. The numeric targets below are proposals to adjust after the first-day tests.

**Goals**

1. Turn a supported phone video into a correct task program in at least 80% of 15 test videos.
2. Execute that program in simulation and reach the correct final layout in at least 70% of runs.
3. Replay a saved program from a shuffled layout, re-finding objects with SAM 3.1, with the same success target.
4. Ship a public repo with a README and a three-minute demo video before the cutoff.

**Non-goals**

- Dexterous or contact-rich manipulation (pouring, rotating, tool use, pushing).
- Real hardware or sim-to-real transfer.
- Arbitrary objects, clutter, deformable items, or a moving camera.
- Training a learned control policy.
- Voice input or output (Meta's speech model only transcribes, and there is no text-to-speech).

## Users and demo scenarios

The primary audience is a hackathon judge who watches a three-minute video and decides within the first minute. A secondary audience is a developer or educator who wants to teach a robot by showing it.

| Time | Beat | What the viewer sees |
| --- | --- | --- |
| 0:00 to 0:20 | Hook | A phone clip of a hand stacking a red cup on a blue cup and moving a green block into a box, with one sentence of narration |
| 0:20 to 1:10 | Pipeline | Video, SAM masks, the plan, and the simulated arm repeating the task, side by side |
| 1:10 to 1:50 | Replay | The blocks are shuffled in simulation, and the robot finds them again and repeats the task |
| 1:50 to 2:30 | Live or recorded second task | A new task is filmed and run, with a pre-recorded fallback if the live run is risky |
| 2:30 to 3:00 | Results and limits | Success-rate table, the stated limits, and the Meta models used |

## Scope

ShowOnce supports pick-and-place style tasks on a plain tabletop with a fixed camera. A video is supported when it meets every condition below.

- **Camera:** fixed, roughly top-down or high-angle, with the whole table visible.
- **Objects:** 3 or 4 distinctly colored blocks or cups, plus at most one box or tray.
- **Length and quality:** 5 to 15 seconds, steady light, one person's hands.
- **Motion:** each object rests still before and after every move, which is what makes hand occlusion tolerable.

Task types by priority:

1. **P0:** move an object into a region or container; stack A on B.
2. **P1:** sort objects by color into zones; stack three.
3. **P2:** undo or reverse a stored task.

## Functional requirements

The pipeline has fourteen requirements, and the P0 items are the minimum for a working demo.

| ID | Requirement | Priority |
| --- | --- | --- |
| FR1 | Accept a phone video (mp4 or mov, up to 15 s) from a local web page or command line, and downsample it to 480p and 10 fps for API calls. | P0 |
| FR2 | Cache every API result by content hash so repeated runs cost nothing. | P0 |
| FR3 | Run SAM 3.1 with one short noun-phrase prompt per object (for example "red block") and store per-frame masks and boxes. | P0 |
| FR4 | Extract each object's resting position before and after every move, ignoring frames where a hand hides it. | P0 |
| FR5 | Merge track fragments when SAM re-finds an object under a new ID. | P1 |
| FR6 | Have Muse Spark 1.3 read the video and return steps in a fixed JSON schema (object, action, target). | P0 |
| FR7 | Cross-check the geometric moves against the Muse Spark steps, and flag the disagreeing step instead of guessing. | P1 |
| FR8 | Compile the steps into a symbolic task program of object names and relations, with no pixel positions. | P0 |
| FR9 | Map image pixels to table coordinates with a four-corner homography. | P0 |
| FR10 | Execute the program in PyBullet with a Panda arm, inverse kinematics and a constraint grasp. | P0 |
| FR11 | Replay a stored program on a shuffled sim layout by re-finding objects with SAM 3.1 on the sim camera frame. | P0 |
| FR12 | Verify the result by running SAM 3.1 on the final sim frame and comparing it with the video's final layout, pass or fail per object. | P1 |
| FR13 | Show video, masks, plan and sim recording side by side in one web view. | P1 |
| FR14 | Save each run (video, masks, plan, sim mp4, score) to disk for the evaluation table. | P1 |

## System architecture

&#91;embedded content: pipeline · 10 steps, 2 lanes\]

SAM 3.1 and Muse Spark read the same clip independently, and the task program is saved once they agree or the disagreement is flagged. Tools: `sam-3.1` through the Responses API, `muse-spark-1.3`, PyBullet, and OpenCV for the homography.

## Technical design

The design rests on one idea: compare resting states, not continuous paths, because the hand hides objects during every move.

**Perception (SAM 3.1).** One short noun-phrase prompt per object runs over the clip through the Responses API, with the clip uploaded once through the Files API. Each object's mask centroid is tracked per frame. An object counts as resting when its centroid moves less than a small threshold for about 0.3 seconds, and a move is a jump between two resting positions larger than a minimum distance. Both thresholds are starting guesses to tune on the test videos. When SAM re-finds an object under a new ID after occlusion, fragments with the same prompt that end and restart close together are merged.

**Semantic plan (Muse Spark 1.3).** The model watches the same clip and returns structured output: a list of steps with object, action (place in, stack on) and target. Stacking is confirmed geometrically when the final centroid sits over the target object's mask. A step that the geometry does not support is flagged on screen, not silently fixed.

**Task program.** Steps compile to object names and relations with no pixel positions, so a program stays valid on any layout. Programs are saved as JSON in a small library.

**Simulation (PyBullet).** A Panda arm, a table, colored blocks and a tray, with a top-down camera that mirrors the phone's viewpoint. A four-corner homography, clicked once on the first video frame, maps pixels to table coordinates. Grasping uses inverse kinematics to hover above the object, descend, add a fixed constraint, lift, move, descend and remove the constraint.

**Replay from a new layout.** The sim camera frame goes to SAM 3.1 with each object's name, and the returned masks give the new positions. Ground-truth sim positions stay available as a development fallback.

**Verification.** SAM 3.1 segments the final sim frame, and each object's position is compared with the final layout from the video. The result is pass or fail per object plus an overall score.

## Success metrics and evaluation

The project succeeds if the pipeline works on videos it has not seen, so the evaluation set is filmed fresh and hand-labeled. The thresholds are proposed targets.

| Metric | Target | How it is measured |
| --- | --- | --- |
| Plan accuracy | At least 80% of 15 videos | The step list matches the hand-labeled steps and order |
| Execution success | At least 70% of runs | Final sim layout matches the labeled end state, read from sim ground truth |
| Replay success | At least 70% of runs | Same check after shuffling the layout and re-finding objects with SAM 3.1 |
| Time to first result | Under 60 s per clip | Wall-clock from upload to the sim starting (an assumption until measured) |
| API cost | Logged per run | Calls and frames counted from the cache log |

**Test set:** 15 videos, made from 5 tasks filmed 3 ways (normal speed, fast hands, different lighting). The README shows the table with failures included.

## Hackathon compliance and submission

The rules below come from a participant's notes and press coverage, not the official rules page, so check them in the participant guide and the Discord rules channel.

- [ ] Start a fresh public repo now, with every commit made between Oct 26 and Nov 4, so the demo shows only work done during the event.
- [ ] Use Meta models only, through the Meta Model API or the open-weight models.
- [ ] Claim the $150 Meta credit through the Discord credit channel, and remember that a spend alert does not stop billing.
- [ ] Keep the API key in a local env file that is never committed.
- [ ] Add every team member on the submission.
- [ ] Write the README: setup, architecture, results table, stated limits, and which Meta model does what.
- [ ] Record the three-minute demo video and add its link.
- [ ] Submit through the submit page by Wednesday evening in Dhaka, leaving the hard cutoff on Thursday Nov 5 at about 08:00 as buffer.

The judging criteria in the same notes give equal weight (0 to 10) to impact, use of Meta AI tooling, technical depth and execution, and the demo. Press coverage says the indie track is judged on creativity, technical ambition and whether the project works.

## Risks and fallbacks

The biggest risk is hand occlusion breaking SAM tracking, so the first-day tests target it directly.

| Risk | Mitigation or fallback | First test |
| --- | --- | --- |
| Hands hide objects and SAM gives a re-found object a new ID, as another entry's repo documents | Compare resting states only, merge fragments, and fall back to Muse Spark's video reading as the primary signal | Film a block-moving clip and check that SAM re-finds each object |
| Video length, resolution and latency limits on the SAM 3.1 API are unknown | Downsample to 480p and 10 fps, trim to 10 s, and cache every result | First real API call on a 10 s clip |
| Simulated grasp is unstable | Constraint grasp, slow motions, fixed object sizes | Script that stacks two blocks 10 times in a row |
| Homography error puts objects in the wrong place | Four corner clicks, plus an overlay that shows the mapped table edges on the video | Overlay check on the test video |
| Muse Spark returns a wrong step list | Fixed JSON schema, geometric cross-check, and the disagreement shown on screen | Compare against hand labels on 5 videos |
| Credit or cost surprise | Cache, per-run cost log, claim the $150 credit early | Check the credit claim in Discord today |
| PyBullet does not install on the machine | conda-forge build, Python 3.10 or 3.11, or switch to MuJoCo | `pip install pybullet` as the first step |
| Overclaiming | Describe it as task-level imitation and show failure cases in the README | Review the demo script |

## Schedule

&#91;embedded content: schedule · 5 work days, 1 cutoff\]

Building ends Monday. Tuesday goes to the 15-video evaluation and README, and Wednesday to the demo video and submission, with Thursday morning kept only as buffer. Each day ends with one check:

- **Saturday:** SAM re-finds objects in a clip where a hand covers them, and the arm stacks two blocks 10 times in a row.
- **Sunday:** one filmed task runs from video to a robot finishing it.
- **Monday:** three tasks, the shuffled-layout replay and verification all run in the web view.
- **Tuesday:** the 15-video results table is in the README.
- **Wednesday:** the demo video is recorded and the submission is sent.

## Open questions

These are unverified assumptions to settle on the first day.

- [ ] Does a simulation-only project count for "Push the Frontier"? Ask the organizers in Discord, since the notes say to ask when an idea's eligibility is unclear.

* [ ] Does the SAM 3.1 API accept a 10 to 15 second phone clip, and how long does one call take?
* [ ] What are the limits on objects per call and prompt length? A ComfyUI guide mentions a 32-token prompt cap in its own integration, which may not apply to Meta's API.
* [ ] Does PyBullet install on the build machine's operating system and Python version?
* [ ] Is the $150 credit claim form live in the Discord credit channel?
* [ ] Is the submission cutoff exactly Wednesday 9pm ET, as one participant's notes say?
* [ ] Is this a solo entry or a team, since every member must be added on the submission?
* [ ] Which task is the hero of the three-minute demo?

## Sources

- [Meta Model API models page](https://dev.meta.ai/docs/models): SAM 3.1 and Muse Spark capabilities, and that Voice Transcribe has no speech synthesis.
- [Meta hackathon coverage (Superpower Daily)](https://superpowerdaily.com/posts/meta-sets-october-26-start-for-1-million-ai-hackathon-capped-at-20-000-builders): dates, tracks, themes, indie judging.
- [Participant repo with rules and Discord notes](https://github.com/sholaola23/meta-hackathon-2026): compliance rules, judging criteria, cutoff time.
- [BeforeTheTape repo](https://github.com/felixbennet/before-the-tape): SAM 3.1 video tracking and the re-found object ID problem.
- [Hackathon guide (GenAI Magazine)](https://thegenaimagazine.com/meta-global-ai-developer-hackathon-ideas-prizes): SAM 3.1 pricing and credits.
- [GibberLink at ElevenLabs](https://showcase.elevenlabs.io/projects/p/gibberlink): the one-sentence-idea example.
- [Agents Everywhere winners](https://pe.linkedin.com/in/yovel-quino): Arto and the simulated Paris Metro line.
- [AI Meets Robotics summary (lablab.ai)](https://lablab.ai/ai-articles/ai-meets-robotics-hackathon-summary): GoferAI and the sim-first format.
- [ComfyUI SAM 3.1 guide](https://docs.comfy.org/tutorials/utility/video-segment-sam3.md): the 32-token prompt limit in that integration.
