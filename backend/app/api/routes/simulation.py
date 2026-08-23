from fastapi import APIRouter, HTTPException

from app.schemas.simulation import SimulationRequest, SimulationResult
from app.services.simulation_service import (
	SimulationServiceError,
	simulation_service,
)


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
