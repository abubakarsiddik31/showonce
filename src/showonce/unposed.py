"""A default table arrangement for clips whose camera was never calibrated.

An angled close-up has no overhead pixel-to-table mapping, so SAM resting
positions would place objects in nonsense spots. This lays the named objects
out with the same free-space search replay uses, and parks each named
container as a fixed zone on the right side of the table.
"""

from __future__ import annotations

from showonce.objects import ObjectProfile
from showonce.program import TaskProgram
from showonce.sim.executor import XY, Layout, Region

ZONE_SIZE: XY = (0.16, 0.16)
ZONE_X = 0.48  # right side, inside arm reach (X_EDGE is 0.34 to 0.60)


def unposed_layout(
    program: TaskProgram,
    profiles: dict[str, ObjectProfile],
    containers: list[str],
    seed: int = 0,
) -> Layout:
    """Arrange the program's objects somewhere real, without video positions."""
    # Imported here, not at top: replay imports demo, demo imports this module.
    from showonce.replay import shuffled_layout

    objects = {s.object for s in program.steps}
    objects |= {s.target for s in program.steps if s.target not in containers}
    regions = [
        Region(name, (ZONE_X, -0.12 + 0.24 * i), ZONE_SIZE) for i, name in enumerate(containers)
    ]
    return Layout(shuffled_layout(sorted(objects), regions, seed, profiles), regions, profiles)
