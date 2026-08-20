from pathlib import Path

from app.pipeline.traffic_state_builder import (
    TrafficStateBuilder,
    TrafficStateBuilderConfig,
)
from app.schemas.traffic import TrafficState


class TrafficService:
    """
    Service untuk mengambil traffic state
    yang dihasilkan oleh TrafficStateBuilder.
    """

    def __init__(
        self,
        csv_path: str | Path,
        window_seconds: int = 5,
    ) -> None:
        self.csv_path = Path(csv_path)

        self.builder = TrafficStateBuilder(
            config=TrafficStateBuilderConfig(
                window_seconds=window_seconds
            ),
        )

    def get_latest_state(self) -> TrafficState:
        """
        Mengambil TrafficState terbaru dari CSV CV.
        """
        states = self.builder.build_from_csv(
            self.csv_path
        )

        if not states:
            raise ValueError(
                "Tidak ada TrafficState yang dihasilkan dari CSV."
            )

        return TrafficState.model_validate(states[-1])

    def get_all_states(self) -> list[TrafficState]:
        """
        Mengambil seluruh TrafficState dari CSV.
        """
        states = self.builder.build_from_csv(
            self.csv_path
        )

        return [
            TrafficState.model_validate(state)
            for state in states
        ]