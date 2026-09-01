from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pathlib import Path
from app.schemas.simulation import (
	SimulationClockRequest,
	SimulationRequest,
	SimulationResult,
	SimulationScenarioRequest,
)
from app.services.simulation_service import (
	SimulationServiceError,
	simulation_service,
)
from app.services.simulation_stream_service import stream_simulation


router = APIRouter(
	prefix="/api/v1/simulation",
	tags=["Simulation"],
)


@router.post("/run", response_model=SimulationResult)
def run_simulation(request: SimulationRequest) -> SimulationResult:
	try:
		return simulation_service.run(request)
	except SimulationServiceError as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stop")
def stop_simulation(context: str = "default"):
	try:
		return simulation_service.stop(context)
	except SimulationServiceError as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/pause")
def pause_simulation(context: str = "default"):
	try:
		return simulation_service.pause(context)
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/resume")
def resume_simulation(context: str = "default"):
	try:
		return simulation_service.resume(context)
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/state")
def get_simulation_state(context: str = "default"):
	try:
		return simulation_service.get_simulation_state(context)
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sync-clock")
def sync_simulation_clock(request: SimulationClockRequest):
	# Sinkronisasi bersifat best-effort. Saat video lebih dulu siap daripada
	# SUMO, respons tetap 200 dengan synced=false dan event berikutnya mencoba lagi.
	return simulation_service.sync_clock(request.videoTimeSeconds, request.context)


@router.post("/scenario")
def apply_simulation_scenario(request: SimulationScenarioRequest):
	"""Ganti program TLS pada sesi aktif tanpa build TrafficState/restart SUMO."""
	try:
		return simulation_service.apply_scenario(
			request.scenario,
			request.cyclePlan.model_dump(),
			request.context,
		)
	except SimulationServiceError as exc:
		raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/stream")
def get_simulation_stream(context: str = "default"):
	return StreamingResponse(
		stream_simulation(fps=10, context=context),
		media_type="multipart/x-mixed-replace; boundary=frame"
	)


@router.get("/frame")
def get_simulation_frame(context: str = "default"):
	"""Satu frame SUMO; request finite supaya shutdown Ctrl+C bersih."""
	frame_path = Path(__file__).resolve().parents[4] / "cache" / "simulation" / f"frame_{context}.jpg"
	if not frame_path.exists():
		raise HTTPException(status_code=404, detail="Frame SUMO belum tersedia.")
	try:
		# Ambil snapshot byte lengkap sebelum membuat Content-Length. FileResponse
		# dapat membaca ukuran lama lalu mengirim isi baru ketika renderer sedang
		# mengganti frame, yang menghasilkan content-length mismatch.
		frame_data = frame_path.read_bytes()
	except OSError as exc:
		raise HTTPException(status_code=503, detail="Frame SUMO sedang diperbarui.") from exc
	return Response(
		content=frame_data,
		media_type="image/jpeg",
		headers={"Cache-Control": "no-store"},
	)

