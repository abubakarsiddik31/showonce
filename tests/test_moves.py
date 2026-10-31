from showonce.meta.sam import Box, Detection
from showonce.perception.moves import best_per_frame, find_rests, moves_from_rests

FPS = 30.0


def det(frame: int, cx: float, cy: float, size: float = 76.0, oid: int = 0) -> Detection:
    h = size / 2
    return Detection(frame, oid, Box(cx - h, cy - h, cx + h, cy + h, 1280, 720), None)


def clip(*segments: tuple[int, float, float, float]) -> list[Detection]:
    """Each segment is (n_frames, cx, cy, size); frames are numbered consecutively."""
    out: list[Detection] = []
    frame = 0
    for n, cx, cy, size in segments:
        for _ in range(n):
            out.append(det(frame, cx, cy, size))
            frame += 1
    return out


def test_single_rest_means_no_moves() -> None:
    series = best_per_frame(clip((90, 400, 300, 76)))
    rests = find_rests(series, FPS)
    assert len(rests) == 1
    assert moves_from_rests("red block", rests) == []


def test_move_between_two_rests_with_occlusion_in_between() -> None:
    # Rest, then a hand-covered stretch (small box drifting), then rest elsewhere.
    detections = clip((30, 400, 300, 76), (40, 600, 320, 25), (30, 900, 300, 76))
    rests = find_rests(best_per_frame(detections), FPS)
    moves = moves_from_rests("red block", rests)
    assert len(rests) == 2
    assert len(moves) == 1
    assert moves[0].src == (400.0, 300.0)
    assert moves[0].dst == (900.0, 300.0)
    assert moves[0].start_frame < moves[0].end_frame


def test_occluded_but_stationary_frames_are_not_a_rest() -> None:
    # A small, still box (hand covering the object) must not count as a resting position.
    detections = clip((30, 400, 300, 76), (30, 420, 330, 20), (30, 900, 300, 76))
    rests = find_rests(best_per_frame(detections), FPS)
    assert [round(r.center[0]) for r in rests] == [400, 900]


def test_jitter_inside_tolerance_stays_one_rest() -> None:
    detections = [det(f, 400 + (f % 3), 300 - (f % 2)) for f in range(60)]
    assert len(find_rests(best_per_frame(detections), FPS)) == 1


def test_best_per_frame_ignores_track_ids() -> None:
    a, b = det(0, 100, 100, 30, oid=0), det(0, 200, 200, 76, oid=5)
    assert best_per_frame([a, b])[0] is b


def test_empty_series() -> None:
    assert find_rests({}, FPS) == []
