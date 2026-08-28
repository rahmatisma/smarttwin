#!/usr/bin/env bash
set -euo pipefail

TASK_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_REPO_ROOT="$(cd "${TASK_SCRIPT_DIR}/.." && pwd)"
TASK_DATA="${PPO_DATA:-${TASK_REPO_ROOT}/cv/output/crossing_simpang.csv}"
TASK_DENSITY_DATA="${PPO_DENSITY_DATA:-${TASK_REPO_ROOT}/cv/output/snapshot_zona.csv}"
TASK_OUTPUT="${PPO_OUTPUT:-${TASK_REPO_ROOT}/decision_engine/models/smarttwin_ppo}"
TASK_TIMESTEPS="${PPO_TIMESTEPS:-100000}"
TASK_SEED="${PPO_SEED:-42}"
TASK_DEVICE="${PPO_DEVICE:-cpu}"
TASK_RESUME="${PPO_RESUME:-}"

cd "${TASK_REPO_ROOT}"
export PYTHONPATH="${TASK_REPO_ROOT}:${TASK_REPO_ROOT}/backend${PYTHONPATH:+:${PYTHONPATH}}"
export SUMO_HOME="${SUMO_HOME:-/usr/share/sumo}"
export PATH="${PATH}:${SUMO_HOME}/bin"

for TASK_REQUIRED_FILE in "${TASK_DATA}" "${TASK_DENSITY_DATA}"; do
    if [[ ! -f "${TASK_REQUIRED_FILE}" ]]; then
        echo "ERROR: data training tidak ditemukan: ${TASK_REQUIRED_FILE}" >&2
        exit 2
    fi
done

if ! command -v sumo >/dev/null 2>&1; then
    echo "ERROR: executable SUMO tidak ditemukan di PATH." >&2
    exit 2
fi

TASK_ARGS=(
    --timesteps "${TASK_TIMESTEPS}"
    --n-steps 512
    --episode-steps 12
    --decision-seconds 30
    --seed "${TASK_SEED}"
    --device "${TASK_DEVICE}"
    --data "${TASK_DATA}"
    --density-data "${TASK_DENSITY_DATA}"
    --output "${TASK_OUTPUT}"
    --checkpoint-freq 10000
)

if [[ -n "${TASK_RESUME}" ]]; then
    TASK_ARGS+=(--resume "${TASK_RESUME}")
fi

echo "SmartTwin PPO RunPod training"
echo "repo=${TASK_REPO_ROOT}"
echo "timesteps=${TASK_TIMESTEPS} seed=${TASK_SEED} device=${TASK_DEVICE}"
echo "output=${TASK_OUTPUT}"
python -m decision_engine.train_ppo "${TASK_ARGS[@]}"
