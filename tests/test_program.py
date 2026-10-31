from showonce.program import SEMANTIC_ACTIONS, Step


def test_step_text_for_the_new_actions() -> None:
    assert (
        str(Step(object="red block", action="place_near", target="blue block"))
        == "put red block next to blue block"
    )
    assert (
        str(Step(object="red block", action="place_near", target="blue block", relation="left_of"))
        == "put red block left of blue block"
    )
    assert str(Step(object="green book", action="push", target="bin")) == "push green book into bin"
    assert (
        str(Step(object="green book", action="push", target="red block", relation="behind"))
        == "push green book behind red block"
    )
    assert str(Step(object="red cup", action="pour", target="bowl")) == "pour red cup into bowl"
    assert (
        str(Step(object="yellow spoon", action="stir", target="bowl"))
        == "stir bowl with yellow spoon"
    )
    assert (
        str(Step(object="gray knife", action="cut", target="white bar"))
        == "cut white bar with gray knife"
    )
    assert (
        str(Step(object="orange lamp", action="press", target="orange lamp")) == "press orange lamp"
    )


def test_relation_defaults_to_none_so_old_programs_still_parse() -> None:
    step = Step.model_validate_json('{"object": "a", "action": "place_in", "target": "bin"}')
    assert step.relation is None


def test_semantic_actions_cover_the_invisible_processes() -> None:
    assert frozenset({"wipe", "open", "pour", "stir", "cut", "press"}) == SEMANTIC_ACTIONS


def test_relation_unit_points_the_way_the_camera_sees() -> None:
    from showonce.geometry import RELATION_UNIT

    assert RELATION_UNIT["left_of"] == (0.0, 1.0)
    assert RELATION_UNIT["right_of"] == (0.0, -1.0)
    assert RELATION_UNIT["in_front_of"] == (-1.0, 0.0)
    assert RELATION_UNIT["behind"] == (1.0, 0.0)
    assert RELATION_UNIT["next_to"] == (0.0, 0.0)
