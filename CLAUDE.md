# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SmartTwin — a digital twin for traffic-signal optimization at a 4-way intersection (KMIPN 2026). The repo is an early-stage monorepo skeleton: only `simulation/` and `docs/` have content so far; `backend/`, `cv/`, `frontend/`, and `docker/` are empty placeholders.

## Pipeline architecture

`docs/data-contract.md` is the source of truth for how the modules connect. It is a Pydantic-only file (no logic) that defines the handoff between team members, and every stage consumes the previous stage's model:

1. **CV** (`cv/`) → `VehicleDetection` — per-vehicle, per-frame detections with `track_id`, `vehicle_class`, bbox, and `approach` (north/south/east/west).
2. **Traffic State Builder** (`backend/`) → `TrafficState` — time-windowed aggregation of detections into per-approach volume / queue length / density / avg speed.
3. **Forecast** (optional, gated on a Week-3 checkpoint) → `ForecastPoint` — LSTM predicted volume per approach per horizon.
4. **Scenario Generator + Performance Analysis** (`simulation/`) → `ScenarioResult` — runs candidate signal-phase plans through SUMO and reports avg delay, avg queue, throughput.
5. **Decision Engine** → `SignalRecommendation` — picks a scenario; `engine` is `"rule-based"` now, `"ppo"` later.

When changing a model in `docs/data-contract.md`, treat it as a cross-module contract change — the fields are the interface between people, not just types.

## SUMO / TraCI setup

SUMO is installed **as a pip package inside the simulation venv** (`eclipse_sumo`, `traci`, `sumolib` 1.27.1), not as a system install. The scripts hard-fail if `SUMO_HOME` is unset, so it must be exported to the venv's SUMO directory before running anything:

```powershell
cd simulation
.\.venv\Scripts\Activate.ps1
$env:SUMO_HOME = "$PWD\.venv\Lib\site-packages\sumo"
```

Both scripts do `sys.path.append($SUMO_HOME/tools)` before `import traci` — keep that prologue in any new TraCI script.

## Simulation commands

Run from the `simulation/` directory (paths in the scripts are relative):

```powershell
python test_traci.py          # smoke test against SUMO's bundled cross.net.xml
python run_intersection.py    # same checks against network/simpang4_pingit.net.xml.gz
```

Both connect via `traci.start(["sumo", ...])` (headless). Use `"sumo-gui"` instead to watch a run.

## Menjalankan simulasi

Lihat simulation/README.md untuk tutorial lengkap. Catatan penting: SUMO_HOME
saja tidak cukup — PATH juga harus menyertakan $SUMO_HOME/bin (tempat
sumo.exe, netconvert.exe berada), atau traci.start()/subprocess call ke
binary SUMO gagal dengan WinError 2 meski SUMO_HOME sudah benar.

## SUMO scenario directories

`osmWebWizard.py` exports each scenario into a timestamped directory (`simulation/2026-08-10-23-25-25/`). **These are gitignored** via `simulation/20*-*-*-*/` and treated as scratch — the only artifact promoted out of them is the network itself, `simulation/network/simpang4_pingit.net.xml.gz`, which is what `run_intersection.py` loads.

So when working with a wizard export:

- Keep it disposable. Copy anything worth keeping into a tracked location (`simulation/network/` for nets) rather than committing the export directory.
- Write run artifacts to `simulation/outputs/` (also gitignored) instead of back into the export directory, since a re-run **overwrites** `tripinfos.xml`, `stats.xml`, and `edgeData.xml` in place.

The first such export was committed and later removed. Its `build.bat` is still the reference for how the trip files were generated — one `randomTrips.py` call per vehicle class (bus/motorcycle/passenger/truck), fixed seeds 42–45, 1-hour horizon — and its `osm.netccfg` records how the net was built from OSM (`lefthand=true`, `tls.default-type=actuated`, junction/TLS joining on). Recover either from history when needed:

```powershell
git checkout 7429bcd -- simulation/2026-08-10-23-25-25/build.bat
```

## Conventions

Code comments and commit messages are written in Indonesian; match the surrounding style.
