"""MuJoCo tabletop scene: Franka Panda, table, colored blocks and a top-down camera."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mujoco
import numpy as np
from numpy.typing import NDArray

DEFAULT_ASSET_DIR = Path("assets/mujoco_menagerie/franka_emika_panda")
BLOCK_HALF = 0.02  # 4 cm cubes
TCP_OFFSET = 0.1034  # fingertip center along the hand z axis
CAMERA_NAME = "top"


@dataclass(frozen=True, slots=True)
class BlockDef:
    name: str
    rgba: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class ZoneDef:
    """A flat, non-colliding target area drawn on the table."""

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
        spec.visual.headlight.ambient = [0.25, 0.25, 0.25]
        spec.visual.headlight.diffuse = [0.3, 0.3, 0.3]
        spec.visual.headlight.specular = [0.0, 0.0, 0.0]
        world.add_light(
            pos=[0.4, 0, 1.5],
            dir=[0, 0, -1],
            type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL,
            diffuse=[0.45, 0.45, 0.45],
            specular=[0.0, 0.0, 0.0],
        )
        table = world.add_geom(
            name="table",
            type=mujoco.mjtGeom.mjGEOM_BOX,
            pos=[0.45, 0.0, -0.025],
            size=[0.5, 0.55, 0.025],
            rgba=[0.62, 0.66, 0.72, 1],
            friction=[1.0, 0.005, 0.0001],
        )
        assert table is not None
        for zone in zones:
            world.add_geom(
                name=f"zone_{zone.name}",
                type=mujoco.mjtGeom.mjGEOM_BOX,
                pos=[zone.center[0], zone.center[1], 0.0005],
                size=[zone.size[0] / 2, zone.size[1] / 2, 0.0005],
                rgba=list(zone.rgba),
                contype=0,
                conaffinity=0,
            )
        spec.body("hand").add_site(
            name="tcp", pos=[0, 0, TCP_OFFSET], size=[0.004, 0.004, 0.004], rgba=[1, 0, 0, 0.3]
        )
        for i, block in enumerate(blocks):
            body = world.add_body(name=block.name, pos=[0.4, -0.3 + 0.1 * i, BLOCK_HALF])
            body.add_freejoint()
            body.add_geom(
                name=f"{block.name}_geom",
                type=mujoco.mjtGeom.mjGEOM_BOX,
                size=[BLOCK_HALF] * 3,
                rgba=list(block.rgba),
                mass=0.05,
                friction=[1.2, 0.01, 0.0005],
                condim=4,
            )
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
            pos=[0.45, 0.0, 1.0],
            xyaxes=[1, 0, 0, 0, 1, 0],
            fovy=50,
        )

    # -- state ---------------------------------------------------------------------------

    def reset(self) -> None:
        mujoco.mj_resetDataKeyframe(self.model, self.data, 0)
        mujoco.mj_forward(self.model, self.data)

    def set_block(self, name: str, xy: tuple[float, float], z: float = BLOCK_HALF) -> None:
        """Teleport a block (identity orientation, zero velocity)."""
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
