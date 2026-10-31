from showonce.objects import (
    MAX_GRASP_WIDTH,
    ObjectProfile,
    fit_to_gripper,
    nearest_color,
    profile_from_description,
    profile_from_name,
    sim_prompt,
    sim_prompts,
)
from showonce.scene_spec import SceneSpec


def test_description_becomes_a_profile_in_meters() -> None:
    profile = profile_from_description(
        {"shape": "cylinder", "width_cm": 7, "depth_cm": 7, "height_cm": 9, "handle": True}
    )
    assert (profile.shape, profile.handle) == ("cylinder", True)
    assert (profile.width, profile.height) == (0.07, 0.09)


def test_objects_wider_than_the_gripper_are_scaled_down() -> None:
    big = fit_to_gripper(
        profile_from_description(
            {"shape": "box", "width_cm": 14, "depth_cm": 7, "height_cm": 10, "handle": False}
        )
    )
    assert big.width <= MAX_GRASP_WIDTH + 1e-9
    assert abs(big.depth / big.width - 0.5) < 1e-9  # proportions kept


def test_a_sphere_is_round_and_a_handle_needs_a_cylinder() -> None:
    ball = profile_from_description(
        {"shape": "sphere", "width_cm": 8, "depth_cm": 8.5, "height_cm": 5.5, "handle": True}
    )
    assert ball.width == ball.depth == ball.height
    assert not ball.handle


def test_only_a_box_can_be_a_sealed_packet() -> None:
    packet = {"shape": "box", "width_cm": 10, "depth_cm": 4, "height_cm": 15, "openable": True}
    assert profile_from_description(packet).openable
    assert not profile_from_description({**packet, "shape": "cylinder"}).openable


def test_names_are_only_a_fallback_guess() -> None:
    assert profile_from_name("red mug").handle
    assert profile_from_name("green apple").shape == "sphere"
    assert profile_from_name("stapler") == ObjectProfile()


def test_sim_prompt_describes_the_stand_in_not_the_real_object() -> None:
    assert sim_prompt("red mug", profile_from_name("red mug")) == "red mug"
    assert sim_prompt("red apple", profile_from_name("red apple")) == "red ball"
    unnamed = ObjectProfile(shape="box", rgb=(0.1, 0.35, 0.8))
    assert sim_prompt("stapler", unnamed) == "blue block"
    assert nearest_color((0.9, 0.8, 0.25)) == "yellow"
    # muted colours sampled from video still get the right name
    assert nearest_color((0.07, 0.27, 0.45)) == "blue"
    assert nearest_color((0.56, 0.21, 0.15)) == "red"
    assert nearest_color((0.84, 0.52, 0.04)) == "orange"


def test_scene_prompts_for_sim_follow_the_profiles() -> None:
    scene = SceneSpec(
        prompts={"red apple": "red apple"},
        profiles={"red apple": ObjectProfile(shape="sphere")},
    )
    assert scene.prompts_for_sim == {"red apple": "red ball"}
    scene = scene.model_copy(update={"sim_prompts": {"red apple": "red thing"}})
    assert scene.prompts_for_sim == {"red apple": "red thing"}


def test_each_object_gets_several_phrases_for_sam_best_first() -> None:
    plate = ObjectProfile(shape="cylinder", width=0.13, depth=0.13, height=0.02)
    assert sim_prompts("white plate", plate) == [
        "white plate",
        "white circle",
        "white round object",
        "round plate",
        "white object",
    ]
    packet = ObjectProfile(openable=True)
    assert sim_prompts("red chips", packet) == ["red packet", "red box", "red object"]
    assert sim_prompts("red mug", profile_from_name("red mug"))[:2] == ["red mug", "red cup"]


def test_pressable_comes_from_the_description() -> None:
    profile = profile_from_description(
        {"shape": "cylinder", "width_cm": 8, "depth_cm": 8, "height_cm": 3, "pressable": True}
    )
    assert profile.pressable


def test_pressable_prompts_lead_with_a_button() -> None:
    profile = ObjectProfile(shape="cylinder", width=0.08, depth=0.08, height=0.03, pressable=True, rgb=(0.9, 0.4, 0.1))
    assert sim_prompts("orange lamp", profile)[0] == "orange button"
