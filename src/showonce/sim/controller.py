"""Cartesian pick-and-place for the Panda: damped least-squares IK plus a weld grasp."""

from __future__ import annotations

from collections.abc import Callable

import mujoco
import numpy as np
from numpy.typing import NDArray

from showonce.sim.scene import SimWorld

Vec = NDArray[np.float64]

HOVER = 0.14  # height of the gripper center above the grasp/place height while travelling
OPEN, CLOSED = 255.0, 0.0
Q_PARK = np.array([1.6, -0.2, 0.0, -2.2, 0.0, 2.0, 0.8])  # arm folded to the side, off the table


class IKError(RuntimeError):
    """Raised when inverse kinematics cannot reach a target."""


class PandaController:
    """Moves the Panda's tool center point with a top-down gripper and carries objects."""

    def __init__(
        self,
        world: SimWorld,
        *,
        waypoint_step: float = 0.01,
        sim_steps_per_waypoint: int = 10,
        on_step: Callable[[], None] | None = None,
        callback_every: int = 10,
    ) -> None:
        self.world = world
        self.waypoint_step = waypoint_step
        self.sim_steps = sim_steps_per_waypoint
        self.on_step = on_step
        self.callback_every = callback_every
        self._scratch = mujoco.MjData(world.model)
        self._counter = 0
        self.q_home = np.array(world.model.key_qpos[0][:7], dtype=np.float64)
        self._rot_down = self._site_rotation(self.q_home)
        self._jnt_range = world.model.jnt_range[:7].copy()

    # -- kinematics ----------------------------------------------------------------------

    def _site_rotation(self, q: Vec) -> Vec:
        d = self._scratch
        d.qpos[:7] = q
        mujoco.mj_kinematics(self.world.model, d)
        return np.array(d.site_xmat[self.world.tcp_site]).reshape(3, 3)

    def solve_ik(self, target: Vec, q0: Vec, *, tol: float = 5e-4, max_iter: int = 150) -> Vec:
        """Find joint angles that put the TCP at ``target`` with the gripper pointing down."""
        model, d = self.world.model, self._scratch
        q = q0.copy()
        quat_des = np.zeros(4)
        mujoco.mju_mat2Quat(quat_des, self._rot_down.flatten())
        jacp, jacr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
        for _ in range(max_iter):
            d.qpos[:7] = q
            mujoco.mj_kinematics(model, d)
            mujoco.mj_comPos(model, d)
            pos_err = target - d.site_xpos[self.world.tcp_site]
            quat_cur, quat_inv, quat_err = np.zeros(4), np.zeros(4), np.zeros(4)
            mujoco.mju_mat2Quat(quat_cur, d.site_xmat[self.world.tcp_site])
            mujoco.mju_negQuat(quat_inv, quat_cur)
            mujoco.mju_mulQuat(quat_err, quat_des, quat_inv)
            rot_err = np.zeros(3)
            mujoco.mju_quat2Vel(rot_err, quat_err, 1.0)
            if np.linalg.norm(pos_err) < tol and np.linalg.norm(rot_err) < 5e-3:
                return q
            mujoco.mj_jacSite(model, d, jacp, jacr, self.world.tcp_site)
            jac = np.vstack([jacp[:, :7], jacr[:, :7]])
            err = np.concatenate([pos_err, rot_err])
            dq = jac.T @ np.linalg.solve(jac @ jac.T + 1e-4 * np.eye(6), err)
            q = np.clip(q + np.clip(dq, -0.2, 0.2), self._jnt_range[:, 0], self._jnt_range[:, 1])
        raise IKError(f"IK did not converge for target {np.round(target, 3).tolist()}")

    # -- motion --------------------------------------------------------------------------

    def _advance(self, n: int) -> None:
        for _ in range(n):
            self.world.step(1)
            self._counter += 1
            if self.on_step is not None and self._counter % self.callback_every == 0:
                self.on_step()

    def _current_q(self) -> Vec:
        return np.array(self.world.data.qpos[:7])

    def move_to(self, target: Vec, on_waypoint: Callable[[], None] | None = None) -> None:
        """Move the TCP in a straight line to ``target`` (world meters).

        ``on_waypoint`` is called after every small step along the way.
        """
        start = self.world.tcp_pos()
        n = max(1, int(np.ceil(np.linalg.norm(target - start) / self.waypoint_step)))
        q = self._current_q()
        for i in range(1, n + 1):
            q = self.solve_ik(start + (target - start) * (i / n), q)
            self.world.data.ctrl[:7] = q
            self._advance(self.sim_steps)
            if on_waypoint is not None:
                on_waypoint()
        self._settle(q)

    def _settle(self, q: Vec, max_steps: int = 400) -> None:
        for _ in range(max_steps // 20):
            self._advance(20)
            if np.max(np.abs(self._current_q() - q)) < 2e-3:
                return

    def set_gripper(self, value: float, steps: int = 150) -> None:
        self.world.data.ctrl[7] = value
        self._advance(steps)

    def _move_joints(self, q_target: Vec, steps: int = 150) -> None:
        """Smooth joint-space move, for large repositioning that is not a Cartesian path."""
        q_start = self._current_q()
        for i in range(1, steps + 1):
            self.world.data.ctrl[:7] = q_start + (q_target - q_start) * (i / steps)
            self._advance(10)
        self._settle(q_target, max_steps=2000)

    def go_home(self) -> None:
        self._move_joints(self.q_home)

    def reset_to_home(self) -> None:
        """Put the arm straight back in its home pose, without moving (nothing is recorded)."""
        data = self.world.data
        data.qpos[:7] = self.q_home
        data.qvel[:7] = 0.0
        data.ctrl[:7] = self.q_home
        mujoco.mj_forward(self.world.model, data)

    def park(self) -> None:
        """Swing the arm out of the top camera's view."""
        self._move_joints(Q_PARK)

    # -- grasping ------------------------------------------------------------------------

    def _set_weld(self, name: str, active: bool) -> None:
        model, data = self.world.model, self.world.data
        eq = model.equality(f"grasp_{name}").id
        if active:
            hand, block = self.world.hand_body, model.body(name).id
            r_hand = np.array(data.xmat[hand]).reshape(3, 3)
            rel_pos = r_hand.T @ (data.xpos[block] - data.xpos[hand])
            rel_rot = r_hand.T @ np.array(data.xmat[block]).reshape(3, 3)
            rel_quat = np.zeros(4)
            mujoco.mju_mat2Quat(rel_quat, rel_rot.flatten())
            model.eq_data[eq, 0:3] = 0.0
            model.eq_data[eq, 3:6] = rel_pos
            model.eq_data[eq, 6:10] = rel_quat
        data.eq_active[eq] = 1 if active else 0

    def grasp(self, body: str, at: Vec) -> None:
        """Close the gripper on ``body`` with the fingertips at ``at``, then lift clear."""
        hover = np.array([at[0], at[1], at[2] + HOVER])
        self.set_gripper(OPEN, steps=60)
        self.move_to(hover)
        self.move_to(at.copy())
        self.set_gripper(CLOSED, steps=150)
        self._set_weld(body, True)
        self.move_to(hover)

    def release(self, body: str, at: Vec) -> None:
        """Lower to ``at``, let go of ``body`` and back off. The gripper's z is the held point."""
        hover = np.array([at[0], at[1], at[2] + HOVER])
        self.move_to(hover)
        self.move_to(at.copy())
        self._set_weld(body, False)
        self.set_gripper(OPEN, steps=120)
        self.move_to(hover)
        self._advance(150)  # let it settle

    def pick_place(
        self,
        name: str,
        target_xy: tuple[float, float],
        surface_z: float = 0.0,
        pick_at: Vec | None = None,
    ) -> None:
        """Pick object ``name`` and set it down at ``target_xy`` with its bottom on ``surface_z``.

        For stacking, pass the top of the object underneath as ``surface_z``. ``pick_at`` is the
        believed object center; by default the simulator's ground truth is used.
        """
        pick = self.world.block_pos(name) if pick_at is None else pick_at
        self.grasp(name, pick)
        place_z = surface_z + self.world.half_height(name) + 0.002
        self.release(name, np.array([target_xy[0], target_xy[1], place_z]))

    def sweep(
        self, path: list[tuple[float, float]], z: float, on_waypoint: Callable[[], None]
    ) -> None:
        """Drag what is held along ``path`` at height ``z``; ``on_waypoint`` runs along the way."""
        for x, y in path:
            self.move_to(np.array([x, y, z]), on_waypoint)

    def pull_off(self, lid: str, tab: Vec, drop_at: Vec) -> None:
        """Pinch the lid's pull tab, lift the lid off the bag and put it down at ``drop_at``."""
        self.grasp(lid, tab)
        hover = np.array([drop_at[0], drop_at[1], tab[2] + HOVER])
        self.move_to(hover)
        self.release(lid, drop_at)
