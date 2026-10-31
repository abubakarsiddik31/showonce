"""MuJoCo tabletop scene: Franka Panda, table, colored objects, trays and a top-down camera."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import mujoco
import numpy as np
from numpy.typing import NDArray

from showonce.geometry import WORK_CENTER_X, WORK_WIDTH_Y
from showonce.objects import ObjectProfile, ShapeKind, color_of, profile_from_name

DEFAULT_ASSET_DIR = Path("assets/mujoco_menagerie/franka_emika_panda")
BLOCK_HALF = 0.02  # half the edge of a default 4 cm cube
TRAY_FLOOR = 0.004  # thickness of a container's floor
RIM_THICKNESS = 0.006
RIM_HEIGHT = 0.012  # low enough that a mug handle clears it
TCP_OFFSET = 0.1034  # fingertip center along the hand z axis
CAMERA_NAME = "top"
CAMERA_HEIGHT = 0.9
CAMERA_ASPECT = 16 / 9  # render size must keep this aspect for the calibration to hold
CAMERA_FOVY_DEG = math.degrees(2 * math.atan(WORK_WIDTH_Y / 2 / CAMERA_ASPECT / CAMERA_HEIGHT))


@dataclass(frozen=True, slots=True)
class Shape:
    """An object's physical primitive, in meters."""

    kind: ShapeKind
    half: tuple[float, float, float]  # half extents along x, y, z
    handle: float = 0.0  # how far a handle sticks out along +y; the gripper closes along x

    @property
    def half_height(self) -> float:
        """Center height above the surface the object rests on."""
        return self.half[2]

    @property
    def radius(self) -> float:
        """Footprint radius of the body alone."""
        return max(self.half[0], self.half[1])

    @property
    def footprint(self) -> float:
        """Footprint radius including any handle."""
        return self.radius + self.handle

    @property
    def grasp_width(self) -> float:
        return 2 * self.half[0]

    @property
    def bbox_offset(self) -> tuple[float, float]:
        """Where the top camera's box center sits relative to the body center."""
        return (0.0, self.handle / 2)


def shape_of(profile: ObjectProfile) -> Shape:
    half = (profile.width / 2, profile.depth / 2, profile.height / 2)
    handle = 0.5 * half[0] if profile.handle else 0.0
    return Shape(profile.shape, half, handle)


@dataclass(frozen=True, slots=True)
class BlockDef:
    name: str
    rgba: tuple[float, float, float, float]
    shape: Shape


def block_def(name: str, profile: ObjectProfile | None = None) -> BlockDef:
    """Build an object from its profile; without one, guess from the name."""
    profile = profile or profile_from_name(name)
    return BlockDef(name, (*color_of(name, profile), 1.0), shape_of(profile))


@dataclass(frozen=True, slots=True)
class ZoneDef:
    """A container on the table: a shallow tray with a low rim."""

    name: str
    center: tuple[float, float]
    size: tuple[float, float]
    rgba: tuple[float, float, float, float] = (0.35, 0.28, 0.2, 1.0)


class SimWorld:
    """Owns the MuJoCo model and data and exposes simple pose queries."""

    def __init__(
        self,
        blocks: list[BlockDef],
        zones: list[ZoneDef] | None = None,
        asset_dir: Path = DEFAULT_ASSET_DIR,
    ) -> None:
        panda_xml = asset_dir / "panda.xml"
        if not panda_xml.exists():
            raise FileNotFoundError(f"{panda_xml} not found. Run scripts/fetch_assets.sh first.")
        self.block_names = [b.name for b in blocks]
        self._shapes = {b.name: b.shape for b in blocks}
        spec = mujoco.MjSpec.from_file(str(panda_xml))
        self._build_scene(spec, blocks, zones or [])
        self.model = spec.compile()
        self.data = mujoco.MjData(self.model)
        # Cancel gravity on the arm so position actuators do not sag; blocks keep gravity.
        free = {
            mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, n) for n in self.block_names
        }
        for body_id in range(1, self.model.nbody):
            self.model.body_gravcomp[body_id] = 0.0 if body_id in free else 1.0
        self.tcp_site = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "tcp")
        self.hand_body = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "hand")
        self.reset()

    @staticmethod
    def _build_scene(spec: mujoco.MjSpec, blocks: list[BlockDef], zones: list[ZoneDef]) -> None:
        world = spec.worldbody
        spec.visual.global_.offwidth = 1920
        spec.visual.global_.offheight = 1080
        spec.visual.headlight.ambient = [0.2, 0.2, 0.2]
        spec.visual.headlight.diffuse = [0.15, 0.15, 0.15]
        spec.visual.headlight.specular = [0.0, 0.0, 0.0]
        world.add_light(
            pos=[0.4, 0, 1.5],
            dir=[0, 0, -1],
            type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL,
            diffuse=[0.35, 0.35, 0.35],
            specular=[0.0, 0.0, 0.0],
        )
        table = world.add_geom(
            name="table",
            type=mujoco.mjtGeom.mjGEOM_BOX,
            pos=[0.45, 0.0, -0.025],
            size=[0.5, 0.55, 0.025],
            rgba=[0.74, 0.64, 0.52, 1],
            friction=[1.0, 0.005, 0.0001],
        )
        assert table is not None
        for zone in zones:
            SimWorld._add_tray(world, zone)
        spec.body("hand").add_site(
            name="tcp", pos=[0, 0, TCP_OFFSET], size=[0.004, 0.004, 0.004], rgba=[1, 0, 0, 0.3]
        )
        for i, block in enumerate(blocks):
            start = [0.4, -0.3 + 0.1 * i, block.shape.half_height]
            body = world.add_body(name=block.name, pos=start)
            body.add_freejoint()
            SimWorld._add_object_geoms(body, block)
            eq = spec.add_equality(
                name=f"grasp_{block.name}",
                type=mujoco.mjtEq.mjEQ_WELD,
                name1="hand",
                name2=block.name,
                objtype=mujoco.mjtObj.mjOBJ_BODY,
            )
            eq.active = False
        world.add_camera(
            name=CAMERA_NAME,
            pos=[WORK_CENTER_X, 0.0, CAMERA_HEIGHT],
            xyaxes=[0, -1, 0, 1, 0, 0],  # image right is world -y, image up is world +x
            fovy=CAMERA_FOVY_DEG,
        )

    @staticmethod
    def _add_tray(world: mujoco.MjsBody, zone: ZoneDef) -> None:
        """A floor plus a low rim. They collide with objects only, never with the arm."""
        (cx, cy), (sx, sy) = zone.center, zone.size
        rim_rgba = [min(1.0, c * 1.3) for c in zone.rgba[:3]] + [1.0]
        common = {"type": mujoco.mjtGeom.mjGEOM_BOX, "contype": 2, "conaffinity": 0}
        world.add_geom(
            name=f"zone_{zone.name}",
            pos=[cx, cy, TRAY_FLOOR / 2],
            size=[sx / 2, sy / 2, TRAY_FLOOR / 2],
            rgba=list(zone.rgba),
            **common,
        )
        t, h = RIM_THICKNESS, RIM_HEIGHT
        walls = (
            ((cx + sx / 2 - t / 2, cy), (t / 2, sy / 2, h / 2)),
            ((cx - sx / 2 + t / 2, cy), (t / 2, sy / 2, h / 2)),
            ((cx, cy + sy / 2 - t / 2), (sx / 2 - t, t / 2, h / 2)),
            ((cx, cy - sy / 2 + t / 2), (sx / 2 - t, t / 2, h / 2)),
        )
        for i, ((wx, wy), half) in enumerate(walls):
            world.add_geom(
                name=f"zone_{zone.name}_rim{i}",
                pos=[wx, wy, TRAY_FLOOR + h / 2],
                size=list(half),
                rgba=rim_rgba,
                **common,
            )

    @staticmethod
    def _add_object_geoms(body: mujoco.MjsBody, block: BlockDef) -> None:
        shape, rgba = block.shape, list(block.rgba)
        hx, hy, hz = shape.half
        # Objects collide with the table (bit 1) and with trays (bit 2).
        physics = {"mass": 0.05, "friction": [1.2, 0.01, 0.0005], "condim": 4, "conaffinity": 3}
        kind, size = {
            "box": (mujoco.mjtGeom.mjGEOM_BOX, [hx, hy, hz]),
            "cylinder": (mujoco.mjtGeom.mjGEOM_CYLINDER, [hx, hz, 0]),
            "sphere": (mujoco.mjtGeom.mjGEOM_SPHERE, [hx, 0, 0]),
        }[shape.kind]
        if shape.kind == "sphere":  # rolling friction, so a released ball settles
            physics |= {"condim": 6, "friction": [1.2, 0.01, 0.01]}
        body.add_geom(name=f"{block.name}_geom", type=kind, size=size, rgba=rgba, **physics)
        if shape.handle > 0:
            SimWorld._add_handle(body, block)

    @staticmethod
    def _add_handle(body: mujoco.MjsBody, block: BlockDef) -> None:
        """A glazed interior and a handle on +y, drawn only (no collisions)."""
        shape, rgba = block.shape, list(block.rgba)
        r, hz, reach = shape.half[0], shape.half[2], shape.handle
        visual = {"contype": 0, "conaffinity": 0, "mass": 0.001}
        body.add_geom(
            name=f"{block.name}_opening",
            type=mujoco.mjtGeom.mjGEOM_CYLINDER,
            pos=[0, 0, hz],
            size=[r - 0.004, 0.0008, 0],
            rgba=[c * 0.6 for c in rgba[:3]] + [1.0],  # a shade darker than the outside
            **visual,
        )
        arm_z = hz * 0.55
        parts = (  # one upright bar and two short stubs
            ((0, r + reach - 0.004, 0), (0.004, 0.004, arm_z)),
            ((0, r + reach / 2 - 0.002, arm_z), (0.004, reach / 2 + 0.002, 0.004)),
            ((0, r + reach / 2 - 0.002, -arm_z), (0.004, reach / 2 + 0.002, 0.004)),
        )
        for i, (pos, half) in enumerate(parts):
            body.add_geom(
                name=f"{block.name}_handle{i}",
                type=mujoco.mjtGeom.mjGEOM_BOX,
                pos=list(pos),
                size=list(half),
                rgba=rgba,
                **visual,
            )

    # -- state ---------------------------------------------------------------------------

    def reset(self) -> None:
        mujoco.mj_resetDataKeyframe(self.model, self.data, 0)
        mujoco.mj_forward(self.model, self.data)

    def shape(self, name: str) -> Shape:
        return self._shapes[name]

    def half_height(self, name: str) -> float:
        return self._shapes[name].half_height

    def set_block(self, name: str, xy: tuple[float, float], z: float | None = None) -> None:
        """Teleport an object upright onto the table (zero velocity); ``z`` is its center."""
        z = self.half_height(name) if z is None else z
        joint = self.model.joint(int(self.model.body(name).jntadr[0]))
        adr = int(joint.qposadr[0])
        self.data.qpos[adr : adr + 7] = [xy[0], xy[1], z, 1, 0, 0, 0]
        dof = int(joint.dofadr[0])
        self.data.qvel[dof : dof + 6] = 0
        mujoco.mj_forward(self.model, self.data)

    def block_pos(self, name: str) -> NDArray[np.float64]:
        return np.array(self.data.xpos[self.model.body(name).id])

    def tcp_pos(self) -> NDArray[np.float64]:
        return np.array(self.data.site_xpos[self.tcp_site])

    def step(self, n: int = 1) -> None:
        mujoco.mj_step(self.model, self.data, nstep=n)
