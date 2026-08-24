from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.schemas.simulation import SimulationRequest, SimulationResult
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
def stop_simulation():
	try:
		return simulation_service.stop()
	except SimulationServiceError as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/pause")
def pause_simulation():
	try:
		return simulation_service.pause()
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/resume")
def resume_simulation():
	try:
		return simulation_service.resume()
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/state")
def get_simulation_state():
	try:
		return simulation_service.get_simulation_state()
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/stream")
def get_simulation_stream():
	return StreamingResponse(
		stream_simulation(fps=10),
		media_type="multipart/x-mixed-replace; boundary=frame"
	)

