"""The real object's picture, cut from the clip and laid on the simulated one."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from showonce.objects import ObjectProfile
from showonce.perception.profiles import (
    footprint_from_picture,
    save_texture,
    sim_picture,
    sim_texture_path,
    texture_path,
)
from showonce.sim.scene import DEFAULT_ASSET_DIR

needs_panda = pytest.mark.skipif(
    not (DEFAULT_ASSET_DIR / "panda.xml").exists(), reason="Panda model missing"
)


def labelled_frame() -> np.ndarray:
    """A 100 x 200 picture: blue in the top-left corner, red in the bottom-right."""
    frame = np.full((100, 200, 3), 255, np.uint8)
    frame[:30, :50] = (255, 0, 0)  # BGR blue, top-left
    frame[70:, 150:] = (0, 0, 255)  # BGR red, bottom-right
    return frame


def test_a_crop_is_saved_twice_once_for_people_and_once_turned_for_the_simulator(
    tmp_path: Path,
) -> None:
    frame = labelled_frame()
    path = texture_path(tmp_path, "Red Chips!")
    assert path.name == "red-chips.png"
    assert save_texture(frame, (0, 0, 200, 100), path) == (200, 100)
    plain = cv2.imread(str(path))
    turned = cv2.imread(str(sim_texture_path(path)))
    assert plain.shape == (100, 200, 3) and turned.shape == (200, 100, 3)  # a quarter turn
    assert tuple(plain[0, 0]) == (255, 0, 0)  # top-left is still blue for anyone looking
    assert tuple(turned[0, 99]) == (255, 0, 0)  # the same corner after turning clockwise


def test_a_round_picture_is_also_flipped() -> None:
    crop = labelled_frame()
    assert np.array_equal(
        sim_picture(crop, round_=True), np.flipud(sim_picture(crop, round_=False))
    )


@pytest.mark.parametrize("box", [(0, 0, 4, 4), (10, 10, 12, 90), (0, 0, 190, 20)])
def test_tiny_or_extremely_thin_detections_are_not_used_as_pictures(
    tmp_path: Path, box: tuple[int, int, int, int]
) -> None:
    assert save_texture(labelled_frame(), box, tmp_path / "x.png") is None
    assert not (tmp_path / "x.png").exists()


def test_a_box_takes_the_proportions_of_its_picture_and_keeps_the_longer_side() -> None:
    # A bag taller than wide in the picture: x (up the picture) is the long side.
    assert footprint_from_picture(0.16, 0.16, (283, 372)) == pytest.approx((0.16, 0.16 * 283 / 372))
    # A phone lying wider than tall: y (across the picture) is the long side.
    assert footprint_from_picture(0.1, 0.1, (300, 150)) == pytest.approx((0.05, 0.1))


@needs_panda
@pytest.mark.parametrize(
    ("shape", "expect"),
    [("box", "blue near the top left"), ("cylinder", "blue near the top left")],
)
def test_the_simulated_object_shows_its_picture_upright_to_the_top_camera(
    tmp_path: Path, shape: str, expect: str
) -> None:
    from showonce.sim.controller import PandaController
    from showonce.sim.executor import Layout, build_world
    from showonce.sim.record import top_view

    round_ = shape == "cylinder"
    frame = np.full((120, 120, 3), 255, np.uint8)
    frame[:40, :40] = (255, 0, 0)  # BGR blue in the top-left of the picture
    path = tmp_path / "thing.png"
    save_texture(frame, (0, 0, 120, 120), path, round_=round_)
    profile = ObjectProfile(shape=shape, width=0.12, depth=0.12, height=0.03, texture=str(path))  # type: ignore[arg-type]
    world = build_world(Layout({"thing": (0.465, 0.0)}, [], {"thing": profile}))
    PandaController(world).park()
    image = top_view(world)  # RGB, up is +x, right is -y
    h, w = image.shape[:2]
    quad = {
        "top-left": image[h // 2 - 120 : h // 2 - 50, w // 2 - 120 : w // 2 - 50],
        "bottom-right": image[h // 2 + 50 : h // 2 + 120, w // 2 + 50 : w // 2 + 120],
    }
    blue = lambda a: float(np.mean((a[..., 2] > 180) & (a[..., 0] < 80)))  # noqa: E731
    assert blue(quad["top-left"]) > 0.3, expect
    assert blue(quad["bottom-right"]) < 0.05


def renderer_released(recorder: object) -> bool:
    return bool(recorder.closed) and getattr(recorder.renderer, "_gl_context", None) is None  # type: ignore[attr-defined]


@needs_panda
def test_a_finished_run_releases_its_renderer(tmp_path: Path) -> None:
    """The simulator process runs clip after clip. A renderer left open keeps the last model's
    drawing state, and one clip's pictures once showed up on the next clip's objects."""
    from showonce.sim.executor import Layout, build_world
    from showonce.sim.record import SimRecorder

    recorder = SimRecorder(build_world(Layout({"red block": (0.45, 0.0)}, [])), 64, 36)
    recorder.capture()
    assert not renderer_released(recorder)
    recorder.save(tmp_path / "run.mp4")  # the end of a run
    assert renderer_released(recorder)
    recorder.close()  # closing twice is harmless


@needs_panda
def test_a_run_that_fails_still_releases_its_renderer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from showonce import replay as replay_module
    from showonce.program import Step, TaskProgram
    from showonce.scene_spec import SceneSpec
    from showonce.sim.executor import ExecutionError
    from showonce.sim.record import SimRecorder

    made: list[SimRecorder] = []

    class Spy(SimRecorder):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)  # type: ignore[arg-type]
            made.append(self)

    monkeypatch.setattr(replay_module, "SimRecorder", Spy)
    scene = SceneSpec(prompts={"red block": "red block"}, size=(1280, 720))
    program = TaskProgram(
        name="t", steps=[Step(object="ghost", action="place_in", target="nowhere")]
    )
    with pytest.raises(ExecutionError):
        replay_module.replay(None, program, scene, 1, record_to=tmp_path / "r.mp4", oracle=True)
    assert len(made) == 1 and renderer_released(made[0])
