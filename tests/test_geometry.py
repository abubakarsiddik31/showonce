import math

from showonce.geometry import Calibration


def test_round_trip_pixel_table_pixel() -> None:
    cal = Calibration.for_frame(1280, 720)
    for pixel in [(0.0, 0.0), (640.0, 360.0), (1000.0, 200.0)]:
        back = cal.to_pixel(cal.to_table(pixel))
        assert math.dist(back, pixel) < 1e-2


def test_image_right_is_world_negative_y_and_down_is_smaller_x() -> None:
    cal = Calibration.for_frame(1280, 720)
    left, right = cal.to_table((100, 360)), cal.to_table((1100, 360))
    top, bottom = cal.to_table((640, 100)), cal.to_table((640, 600))
    assert right[1] < left[1]
    assert bottom[0] < top[0]


def test_frame_center_maps_to_work_center() -> None:
    x, y = Calibration.for_frame(1280, 720).to_table((640, 360))
    assert abs(x - 0.465) < 1e-4 and abs(y) < 1e-4


def test_rect_to_table_returns_bounding_box() -> None:
    cal = Calibration.for_frame(1280, 720)
    center, size = cal.rect_to_table((640, 360), (128, 72))
    assert abs(center[0] - 0.465) < 1e-4
    assert abs(size[1] - 0.052) < 1e-3
