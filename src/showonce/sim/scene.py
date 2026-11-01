"""MuJoCo tabletop scene: Franka Panda, table, colored objects, trays and a top-down camera."""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping
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
# A packet lies flat. Its seal is a thin strip along the +x (top) edge, longer than the bag so
# the ends stick out like a crimped seam: that is where the gripper takes hold and tears it off.
STRIP_HALF = (0.01, 0.0, 0.004)  # half width along x and half thickness; length follows the bag
STRIP_TAIL = 0.03  # how far the strip sticks out past each side of the bag
DIRT_SPOTS = 14
DIRT_RADIUS = 0.012
PARK_Z = -0.4  # where cut-away bodies wait, each at its own depth below this
CONTENTS_RGBA = (0.55, 0.42, 0.2, 1.0)  # dry cereal-brown: contents are an abstraction, not a fluid
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
    openable: bool = False  # a sealed packet: its seal strip is a separate body
    pressable: bool = False  # a button or pump: press it straight down

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
        # SAM outlines the bag but not its pale seal strip, which lies along the +x edge.
        return (-STRIP_HALF[0] if self.openable else 0.0, self.handle / 2)


def shape_of(profile: ObjectProfile) -> Shape:
    half = (profile.width / 2, profile.depth / 2, profile.height / 2)
    handle = 0.5 * half[0] if profile.handle else 0.0
    return Shape(profile.shape, half, handle, profile.openable, profile.pressable)


@dataclass(frozen=True, slots=True)
class BlockDef:
    name: str
    rgba: tuple[float, float, float, float]
    shape: Shape
    texture: str | None = None  # a picture of the real thing, laid on top (boxes, round dishes)


def lid_name(name: str) -> str:
    return f"{name}_lid"


def strip_offset(shape: Shape) -> tuple[float, float]:
    """Where a packet's seal strip sits relative to the bag's center: (x, z)."""
    return shape.half[0] - STRIP_HALF[0], shape.half[2] + STRIP_HALF[2]


def block_def(name: str, profile: ObjectProfile | None = None) -> BlockDef:
    """Build an object from its profile; without one, guess from the name."""
    profile = profile or profile_from_name(name)
    return BlockDef(name, (*color_of(name, profile), 1.0), shape_of(profile), profile.texture)


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
        dirty: Collection[str] = (),
        contents: Collection[str] = (),
        pour_targets: Collection[str] = (),
    ) -> None:
        panda_xml = asset_dir / "panda.xml"
        if not panda_xml.exists():
            raise FileNotFoundError(f"{panda_xml} not found. Run scripts/fetch_assets.sh first.")
        self.block_names = [b.name for b in blocks]
        self._shapes = {b.name: b.shape for b in blocks}
        self._rgb = {b.name: b.rgba[:3] for b in blocks}
        self._zones = {z.name: z for z in zones or []}
        spec = mujoco.MjSpec.from_file(str(panda_xml))
        self._build_scene(spec, blocks, zones or [], set(dirty), set(contents), set(pour_targets))
        self.model = spec.compile()
        self.data = mujoco.MjData(self.model)
        # Cancel gravity on the arm so position actuators do not sag; objects keep gravity.
        free = {
            mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, n)
            for n in [
                *self.block_names,
                *(lid_name(b) for b in self.block_names if self._shapes[b].openable),
            ]
        }
        self._dirt = {
            surface: [
                mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, f"dirt_{surface}_{i}")
                for i in range(DIRT_SPOTS)
            ]
            for surface in dirty
        }
        self._contents: dict[str, str | None] = {name: "full" for name in contents}
        self._mixed: set[str] = set()
        self._content_geoms = {
            name: mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, f"contents_{name}")
            for name in (*contents, *pour_targets)
        }
        for name in pour_targets:
            self.model.geom_rgba[self._content_geoms[name], 3] = 0.0  # empty until poured into
        names = set(self.block_names)
        self._halves = {
            b.name: (f"{b.name} half a", f"{b.name} half b")
            for b in blocks
            if f"{b.name} half a" in names and f"{b.name} half b" in names
        }
        self._pressed: set[str] = set()
        for body_id in range(1, self.model.nbody):
            self.model.body_gravcomp[body_id] = 0.0 if body_id in free else 1.0
        self.tcp_site = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "tcp")
        self.hand_body = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "hand")
        for pair in self._halves.values():
            for half in pair:
                body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, half)
                self.model.body_gravcomp[body_id] = 1.0  # frozen while parked
        self.reset()

    @staticmethod
    def _build_scene(
        spec: mujoco.MjSpec,
        blocks: list[BlockDef],
        zones: list[ZoneDef],
        dirty: set[str],
        contents: set[str],
        pour_targets: set[str],
    ) -> None:
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
            if zone.name in dirty:
                half = (zone.size[0] / 2 - RIM_THICKNESS, zone.size[1] / 2 - RIM_THICKNESS)
                SimWorld._add_dirt(world, zone.name, (*zone.center, TRAY_FLOOR), half)
            if zone.name in contents or zone.name in pour_targets:
                half = (zone.size[0] / 2 - RIM_THICKNESS, zone.size[1] / 2 - RIM_THICKNESS)
                SimWorld._add_contents(world, zone.name, (*zone.center, TRAY_FLOOR), half)
        spec.body("hand").add_site(
            name="tcp", pos=[0, 0, TCP_OFFSET], size=[0.004, 0.004, 0.004], rgba=[1, 0, 0, 0.3]
        )
        for i, block in enumerate(blocks):
            start = [0.4, -0.3 + 0.1 * i, block.shape.half_height]
            body = world.add_body(name=block.name, pos=start)
            body.add_freejoint()
            SimWorld._add_object_geoms(body, block)
            SimWorld._add_picture(spec, body, block)
            if block.name in dirty:
                hx, hy, hz = block.shape.half
                SimWorld._add_dirt(body, block.name, (0.0, 0.0, hz), (hx, hy))
            if block.name in contents or block.name in pour_targets:
                hx, hy, hz = block.shape.half
                SimWorld._add_contents(body, block.name, (0.0, 0.0, hz), (hx, hy))
            graspable = [block.name]
            if block.shape.openable:
                SimWorld._add_lid(world, block, start)
                graspable.append(lid_name(block.name))
            for body_name in graspable:
                eq = spec.add_equality(
                    name=f"grasp_{body_name}",
                    type=mujoco.mjtEq.mjEQ_WELD,
                    name1="hand",
                    name2=body_name,
                    objtype=mujoco.mjtObj.mjOBJ_BODY,
                )
                eq.active = False
        index = {b.name: i for i, b in enumerate(blocks)}
        for block in blocks:
            if f"{block.name} half a" in index:
                for half in (f"{block.name} half a", f"{block.name} half b"):
                    body = spec.body(half)
                    body.pos = [0.0, 0.0, PARK_Z - 0.05 * index[half]]  # one depth each
                    # Set before compiling: MuJoCo skips gravity compensation altogether if no
                    # body asks for it at that point, and a parked half would fall for ever.
                    body.gravcomp = 1.0
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
        # Flat dishes weigh enough to stay put when something brushes past them.
        mass = (
            max(0.05, 600 * math.prod(2 * h for h in shape.half))
            if hz < 0.3 * min(hx, hy)
            else 0.05
        )
        physics = {"mass": mass, "friction": [1.2, 0.01, 0.0005], "condim": 4, "conaffinity": 3}
        if shape.openable:
            SimWorld._add_packet_body(body, block, physics)
            return
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
    def _add_picture(spec: mujoco.MjSpec, body: mujoco.MjsBody, block: BlockDef) -> None:
        """Lay the picture of the real object on top of a box or dish, so the sim looks like it.

        It is a decal: a sheet a fraction of a millimetre thick that neither collides nor weighs
        anything. The picture is the sim-oriented copy written when the clip was learned.
        """
        if block.texture is None or block.shape.kind not in ("box", "cylinder"):
            return
        picture = Path(block.texture)
        picture = picture.with_name(f"{picture.stem}.sim.png")
        if not picture.is_file():
            return
        hx, hy, hz = block.shape.half
        texture = spec.add_texture(
            name=f"picture {block.name}",
            type=mujoco.mjtTexture.mjTEXTURE_2D,
            file=str(picture.resolve()),
        )
        assert texture is not None
        material = spec.add_material(name=f"picture {block.name}")
        material.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = texture.name
        round_ = block.shape.kind == "cylinder"
        body.add_geom(
            name=f"{block.name}_picture",
            type=mujoco.mjtGeom.mjGEOM_CYLINDER if round_ else mujoco.mjtGeom.mjGEOM_BOX,
            pos=[0, 0, hz + 0.0003],  # just under a packet's slit, so that still shows
            size=[hx, 0.0002, 0] if round_ else [hx, hy, 0.0002],
            material=material.name,
            contype=0,
            conaffinity=0,
            mass=0.001,
        )

    @staticmethod
    def _add_packet_body(
        body: mujoco.MjsBody, block: BlockDef, physics: Mapping[str, object]
    ) -> None:
        """A bag lying flat, with a dark slit along its top edge that shows once the seal is off."""
        hx, hy, hz = block.shape.half
        body.add_geom(
            name=f"{block.name}_geom",
            type=mujoco.mjtGeom.mjGEOM_BOX,
            size=[hx, hy, hz],
            rgba=list(block.rgba),
            **physics,
        )
        body.add_geom(
            name=f"{block.name}_slit",
            type=mujoco.mjtGeom.mjGEOM_BOX,
            pos=[hx - STRIP_HALF[0], 0, hz + 0.0005],
            size=[STRIP_HALF[0], hy, 0.0005],
            rgba=[0.12, 0.05, 0.05, 1],
            contype=0,
            conaffinity=0,
            mass=0.001,
        )

    @staticmethod
    def _add_lid(world: mujoco.MjsBody, block: BlockDef, start: list[float]) -> None:
        """The seal strip, resting on the bag's top edge. It is the part that gets torn off."""
        _, hy, hz = block.shape.half
        dx, dz = strip_offset(block.shape)
        body = world.add_body(name=lid_name(block.name), pos=[start[0] + dx, start[1], dz + hz])
        body.add_freejoint()
        light = [min(1.0, 0.45 + 0.55 * c) for c in block.rgba[:3]] + [1.0]  # foil, a lighter shade
        body.add_geom(
            name=f"{block.name}_lid",
            type=mujoco.mjtGeom.mjGEOM_BOX,
            size=[STRIP_HALF[0], hy + STRIP_TAIL, STRIP_HALF[2]],
            rgba=light,
            mass=0.01,
            friction=[1.5, 0.01, 0.0005],
            conaffinity=3,
        )

    @staticmethod
    def _add_dirt(
        body: mujoco.MjsBody,
        surface: str,
        top: tuple[float, float, float],
        half: tuple[float, float],
    ) -> None:
        """Stains on a surface, spread evenly. ``top`` is the surface center and height."""
        cx, cy, z = top
        for i in range(DIRT_SPOTS):
            radial = math.sqrt((i + 0.5) / DIRT_SPOTS)
            angle = i * 2.39996  # golden angle spreads the spots without clumping
            body.add_geom(
                name=f"dirt_{surface}_{i}",
                type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                pos=[
                    cx + 0.7 * half[0] * radial * math.cos(angle),
                    cy + 0.7 * half[1] * radial * math.sin(angle),
                    z + 0.0004,
                ],
                size=[DIRT_RADIUS, 0.0004, 0],
                rgba=[0.3, 0.18, 0.06, 1],
                contype=0,
                conaffinity=0,
                mass=0.0001,
            )

    @staticmethod
    def _add_contents(
        body: mujoco.MjsBody, name: str, top: tuple[float, float, float], half: tuple[float, float]
    ) -> None:
        """A flat disc of contents, drawn only (no collisions): what a pour moves around."""
        cx, cy, z = top
        body.add_geom(
            name=f"contents_{name}",
            type=mujoco.mjtGeom.mjGEOM_CYLINDER,
            pos=[cx, cy, z + 0.0008],
            size=[min(half) * 0.7, 0.0008, 0],
            rgba=list(CONTENTS_RGBA),
            contype=0,
            conaffinity=0,
            mass=0.0001,
        )

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

    def color(self, name: str) -> tuple[float, float, float]:
        return (self._rgb[name][0], self._rgb[name][1], self._rgb[name][2])

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
        if self._shapes[name].openable:  # the lid goes back on top of the bag
            lid = self.model.joint(int(self.model.body(lid_name(name)).jntadr[0]))
            lid_adr = int(lid.qposadr[0])
            dx, dz = strip_offset(self._shapes[name])
            self.data.qpos[lid_adr : lid_adr + 7] = [xy[0] + dx, xy[1], z + dz, 1, 0, 0, 0]
            self.data.qvel[int(lid.dofadr[0]) : int(lid.dofadr[0]) + 6] = 0
        mujoco.mj_forward(self.model, self.data)

    def block_pos(self, name: str) -> NDArray[np.float64]:
        return np.array(self.data.xpos[self.model.body(name).id])

    def lid_pos(self, name: str) -> NDArray[np.float64]:
        return np.array(self.data.xpos[self.model.body(lid_name(name)).id])

    def is_open(self, name: str) -> bool:
        """The seal strip has been torn off and laid clear of the bag."""
        hx, hy, _ = self._shapes[name].half
        dx, dy = np.abs(self.lid_pos(name)[:2] - self.block_pos(name)[:2])
        return bool(dx > hx + 0.01 or dy > hy + STRIP_TAIL + 0.03)

    def halves_of(self, name: str) -> tuple[str, str]:
        """The two bodies a cut replaces ``name`` with."""
        return self._halves[name]

    def split(self, name: str) -> None:
        """Replace a box with its two halves, lying side by side where it stood."""
        if name not in self._halves:
            raise ValueError(f"'{name}' is not something that can be cut in two")
        pos = self.block_pos(name)
        hx = self._shapes[name].half[0]
        for sign, half in zip((1.0, -1.0), self._halves[name], strict=True):
            self.set_block(half, (float(pos[0]) + sign * (hx / 2 + 0.008), float(pos[1])))
            body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, half)
            self.model.body_gravcomp[body_id] = 0.0  # a real object again
        self._park(name)

    def is_split(self, name: str) -> bool:
        if name not in self._halves:
            return False
        gone = self.block_pos(name)[2] < 0.0
        on_table = all(self.block_pos(h)[2] > 0.0 for h in self._halves[name])
        return gone and on_table

    def press(self, name: str) -> None:
        """Press a pressable object: it latches down and darkens."""
        if name not in self._pressed:  # latched: a second press changes nothing
            geom = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, f"{name}_geom")
            self.model.geom_rgba[geom, :3] *= 0.6
            self._pressed.add(name)

    def is_pressed(self, name: str) -> bool:
        return name in self._pressed

    def _park(self, name: str) -> None:
        """Teleport a body far under the table and freeze it, out of the scene."""
        joint = self.model.joint(int(self.model.body(name).jntadr[0]))
        adr = int(joint.qposadr[0])
        z = PARK_Z - 0.05 * self.block_names.index(name)  # its own depth slot, like at build time
        self.data.qpos[adr : adr + 7] = [0.0, 0.0, z, 1, 0, 0, 0]
        self.data.qvel[int(joint.dofadr[0]) : int(joint.dofadr[0]) + 6] = 0
        self.model.body_gravcomp[self.model.body(name).id] = 1.0
        mujoco.mj_forward(self.model, self.data)

    def surface_top(self, name: str) -> float:
        """Height of the top of an object or container tray."""
        if name in self._zones:
            return TRAY_FLOOR
        return float(self.block_pos(name)[2] + self.half_height(name))

    def scrub(self, surface: str, xy: tuple[float, float], half: tuple[float, float]) -> None:
        """Wipe away any stains under a rectangle (a sponge) centred at ``xy``."""
        for geom in self._dirt.get(surface, []):
            spot = self.data.geom_xpos[geom]
            if abs(spot[0] - xy[0]) <= half[0] and abs(spot[1] - xy[1]) <= half[1]:
                self.model.geom_rgba[geom, 3] = 0.0

    def dirt_left(self, surface: str) -> tuple[int, int]:
        """(stains still showing, stains it started with)."""
        geoms = self._dirt.get(surface, [])
        return sum(1 for g in geoms if self.model.geom_rgba[g, 3] > 0), len(geoms)

    def pour_into(self, source: str, target: str) -> None:
        """Everything in ``source`` ends up in ``target``: the disc moves, no drops, no amounts."""
        if self._contents.get(source) is None:
            raise ValueError(f"'{source}' has nothing to pour")
        self._contents[source] = None
        self._contents[target] = "poured"
        self.model.geom_rgba[self._content_geoms[source], 3] = 0.0
        self.model.geom_rgba[self._content_geoms[target], 3] = 1.0

    def contents_of(self, name: str) -> str | None:
        return self._contents.get(name)

    def stir(self, name: str) -> None:
        self._mixed.add(name)

    def is_mixed(self, name: str) -> bool:
        return name in self._mixed

    def tcp_pos(self) -> NDArray[np.float64]:
        return np.array(self.data.site_xpos[self.tcp_site])

    def step(self, n: int = 1) -> None:
        mujoco.mj_step(self.model, self.data, nstep=n)
