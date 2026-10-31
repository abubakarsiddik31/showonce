from showonce.meta.sam import group_by_object, parse_sam_text

SAMPLE = (
    "<0f>0<|box;x1=10;y1=20;x2=50;y2=60;w=640;h=480|><|mask;x=0;y=0;data=480,640,~abc|>,"
    "2<|box;x1=100;y1=100;x2=140;y2=130;w=640;h=480;c=0.9|><|mask;x=0;y=0;data=480,640,!xyz|>\n"
    "<4f>0<|box;x1=12;y1=22;x2=52;y2=62;w=640;h=480|><|mask;x=0;y=0;data=480,640,~def|>\n"
)


def test_parses_all_records_with_explicit_frames() -> None:
    dets = parse_sam_text(SAMPLE)
    assert [(d.frame, d.object_id) for d in dets] == [(0, 0), (0, 2), (4, 0)]


def test_box_center_and_confidence() -> None:
    dets = parse_sam_text(SAMPLE)
    assert dets[0].box.center == (30.0, 40.0)
    assert dets[0].box.confidence is None
    assert dets[1].box.confidence == 0.9


def test_mask_marker_is_first_char_only() -> None:
    mask = parse_sam_text(SAMPLE)[1].mask
    assert mask is not None
    assert (mask.rows, mask.cols, mask.encoding, mask.payload) == (480, 640, "!", "xyz")


def test_group_by_object_sorts_by_frame() -> None:
    grouped = group_by_object(parse_sam_text(SAMPLE))
    assert list(grouped) == [0, 2]
    assert [d.frame for d in grouped[0]] == [0, 4]


def test_empty_response_yields_nothing() -> None:
    assert parse_sam_text("") == []
