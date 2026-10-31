#!/usr/bin/env bash
# Fetch the Franka Panda MuJoCo model (Apache-2.0) from DeepMind's mujoco_menagerie.
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=assets/mujoco_menagerie
if [ -d "$DEST/franka_emika_panda" ]; then
  echo "Panda model already present in $DEST"
  exit 0
fi
mkdir -p assets
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/google-deepmind/mujoco_menagerie.git "$DEST"
git -C "$DEST" sparse-checkout set franka_emika_panda
echo "Fetched Panda model to $DEST/franka_emika_panda"
