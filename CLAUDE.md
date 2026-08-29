# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SmartTwin — a digital twin for traffic-signal optimization at a 4-way intersection (KMIPN 2026). `simulation/`, `cv/`, `frontend/`, `forecasting/`, and `docs/` have content; `docker/` holds only a README.

`backend/` was empty until 17 August 2026 and now holds **22 Python files** — `app/main.py`, `app/api/routes/` (health, traffic, signal, forecast, recommendation), `app/schemas/`, `app/services/`, `app/core/config.py`, plus `tests/test_api.py`, `requirements.txt`, and `.env.example`. **Not yet verified** whether those endpoints serve real `TrafficState` data or are still stubs, and whether the PostgreSQL schema exists — check before relying on them.

`docs/STATUS-DAN-SISA-KERJA.md` is the **single** plan of record and status tracker — read it before assuming what is in or out of scope, or who owns what. It is deliberately the only status document: on 28 August six overlapping status/task docs (`pembagian-tugas-tahap-akhir.md`, `status-integrasi-diagram-arsitektur.md`, `audit-24-agustus.md`, `pembagian-tugas-24-agustus.md`, `roadmap.md`, `realtime-dashboard.md`) were deleted because they contradicted each other and each other's checklists were mostly complete. **Do not create a new status document** — move finished items into that file's "Sudah Selesai" section instead. `docs/README.md` indexes the remaining docs, split into cara kerja (reference) vs hasil uji (evidence).

## Pipeline architecture

`docs/data-contract.md` is the source of truth for how the modules connect. It is a Pydantic-only file (no logic) that defines the handoff between team members, and every stage consumes the previous stage's model:

1. **CV** (`cv/`) → `VehicleDetection` — per-vehicle, per-frame detections with `track_id`, `vehicle_class`, bbox, and `approach` (north/south/east/west).
2. **Traffic State Builder** (`backend/`) → `TrafficState` — time-windowed aggregation of detections into per-approach volume / queue length / density / avg speed.
3. **Forecast** (`forecasting/`) → `ForecastPoint` — **not active.** See "Status of LSTM and PPO" below. Consumers fall back to flat volume from the last `TrafficState`.
4. **Scenario Generator + Performance Analysis** (`simulation/`) → `ScenarioResult` — runs candidate signal-phase plans through SUMO and reports avg delay, avg queue, throughput.
5. **Decision Engine** → `SignalRecommendation` — picks a scenario; `engine` is `"rule-based"`. The `"ppo"` literal stays in the contract but has no implementation.

When changing a model in `docs/data-contract.md`, treat it as a cross-module contract change — the fields are the interface between people, not just types.

## Status of LSTM and PPO

The two are **not** in the same state — don't collapse them into one "future work" bucket.

**PPO** — **built and trained as of 28 August** (commit `f921ce9`). The only active RL dependency file is `decision_engine/requirements-rl.txt`; do not use or recreate the removed `simulation/requirements-rl.txt`. What exists now: `decision_engine/ppo_env.py` (Gymnasium env over SUMO), `train_ppo.py`, `evaluate_ppo.py`, `ppo_engine.py`, and `engine_factory.py`. Training genuinely converged — `decision_engine/models/training_monitor.csv` shows reward rising monotonically from −3.38 to −1.80 over 8,362 episodes.

Three caveats that matter before quoting any PPO result:
- **The trained checkpoint is NOT in the repo.** `.gitignore` line 20 (`*.zip`) excludes `decision_engine/models/smarttwin_ppo.zip`, so `PPOEngine` always falls back to rule-based on any machine but the trainer's. Commit it with `git add -f`, the same pattern the LSTM artifacts needed. This is also why `pytest` in `backend/` currently reports 1 failure.
- **PPO is opt-in and defaults off.** `create_decision_engine()` returns `RuleBasedEngine` unless `SMARTTWIN_DECISION_ENGINE=ppo`; `PPOEngine` falls back internally (`source="ppo-fallback-rule-based"`) whenever the checkpoint or dependency is missing. PPO cannot break the demo.
- **"PPO beats rule-based" is not yet a supportable claim.** It wins on reward in all 3 evaluation seeds, but reward is its own training objective. On the traffic metrics it wins 4 of 9 comparisons and **never** wins on throughput. The baseline it is compared against (`ppo_env.py::rule_based_action()`) is a simplified proxy, not the real `RuleBasedEngine`. See `docs/STATUS-DAN-SISA-KERJA.md` items P-1a–P-1d.

**LSTM (`forecasting/`)** — three separate experiments with three different statuses. Work stopped 15 August 2026 to fit the 16-day scope, but the results are real and committed:

| Dataset | Status | Headline result |
|---|---|---|
| PeMS04 (Caltrans freeway sensors) | trained + evaluated, **most complete** | R² 0.879 overall, flow 0.933 |
| TMU (UK A174 road sensors) | trained + evaluated | speed MAPE 2.09%, vehicle_count MAPE 25.6% |
| Brisbane (open intersection API) | preprocessed only, **never trained** | no metrics — only 5 rows survived preprocessing vs `sequence_length=16` |

The models work; the problem is transferability. TMU and PeMS04 are both continuous-roadway sensors abroad, not a signalized Indonesian intersection. Do not describe this as "the model failed" — the metrics in `forecasting/outputs/` contradict that.

When quoting these numbers: PeMS04 MAE/RMSE are in **scaled units**, not vehicles/hour; and MAPE is unreliable across this data (TMU `queue_proxy` reports 1,008,321,136% from near-zero division). Prefer MAE/RMSE/R².

**Do not delete or refactor `forecasting/scripts/` or `forecasting/outputs/`** — both are kept as evidence for the technical report. Note that `forecasting/outputs/*` is gitignored, so those files were committed with `git add -f`; the same is needed for any future additions there.

`forecasting/README.md` below its status header still describes a full LSTM → SUMO → PPO pipeline as the intended design. That plan is superseded; the header note is the current status.

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

**There is only one project network: `network/simpang4_pingit.net.xml.gz` (Simpang Pingit, Yogyakarta — origBoundary 110.358–110.364 E, −7.788–−7.778 S, UTM zone 49, TLS id `SIMPANG_CENTER`).** An older `simpang4.net.xml.gz` held a Bandung intersection from before the location change; it was reintroduced by an accidental revert in `050324f` and has since been deleted. If a network file other than `simpang4_pingit` reappears, treat it as a regression, not an asset.

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
