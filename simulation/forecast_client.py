"""Client forecast untuk jalur batch SUMO SmartTwin.

Alur modul ini:
    output Traffic State Builder yang tersimpan di Supabase
    -> backend traffic API -> 12 TrafficState berurutan -> forecast API
    -> forecast per-approach untuk ScenarioEngine.

Client tidak membaca YOLO atau CSV secara langsung. Ia juga belum otomatis
dipanggil ``run_tls_simulation.py``; integrasi runner dilakukan terpisah agar
fallback SUMO dapat diuji sebelum mengubah jalur batch yang sudah stabil.

Modul sengaja memakai ``urllib`` dari standard library agar environment
simulation tidak perlu membawa dependency HTTP tambahan. Kegagalan jaringan,
histori yang belum cukup, atau respons yang tidak valid dikembalikan sebagai
``None`` oleh ``get_live_forecast`` sehingga runner SUMO dapat memakai
TrafficState saat ini sebagai fallback.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


APPROACHES = ("west", "south", "east", "north")
REQUIRED_HISTORY_STEPS = 12
INTERVAL_SECONDS = 5
ZONE_CAPACITY = 33.0
DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_INTERSECTION_ID = "simpang4-pingit"

JsonDict = dict[str, Any]
Transport = Callable[[str, str, JsonDict | None, float], JsonDict]


class ForecastClientError(RuntimeError):
    """Kesalahan terkontrol saat mengambil atau memvalidasi forecast."""


@dataclass(frozen=True)
class ForecastClientConfig:
    backend_url: str = DEFAULT_BACKEND_URL
    intersection_id: str = DEFAULT_INTERSECTION_ID
    history_limit: int = 24
    timeout_seconds: float = 10.0

    @classmethod
    def from_environment(cls) -> "ForecastClientConfig":
        return cls(
            backend_url=os.getenv("SMARTTWIN_BACKEND_URL", DEFAULT_BACKEND_URL),
            intersection_id=os.getenv(
                "SMARTTWIN_INTERSECTION_ID", DEFAULT_INTERSECTION_ID
            ),
            history_limit=int(os.getenv("FORECAST_HISTORY_LIMIT", "24")),
            timeout_seconds=float(os.getenv("FORECAST_TIMEOUT_SECONDS", "10")),
        )


def _default_transport(
    method: str,
    url: str,
    payload: JsonDict | None,
    timeout: float,
) -> JsonDict:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url=url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ForecastClientError(
            f"Backend mengembalikan HTTP {exc.code} untuk {url}: {detail}"
        ) from exc
    except URLError as exc:
        raise ForecastClientError(f"Backend tidak dapat dihubungi: {exc.reason}") from exc

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ForecastClientError("Respons backend bukan JSON yang valid.") from exc
    if not isinstance(result, dict):
        raise ForecastClientError("Respons backend harus berupa object JSON.")
    return result


class ForecastClient:
    def __init__(
        self,
        config: ForecastClientConfig | None = None,
        transport: Transport | None = None,
    ) -> None:
        self.config = config or ForecastClientConfig.from_environment()
        self.transport = transport or _default_transport
        self.last_error: str | None = None

        if self.config.history_limit < REQUIRED_HISTORY_STEPS:
            raise ValueError(
                f"history_limit minimal {REQUIRED_HISTORY_STEPS}, "
                f"diterima {self.config.history_limit}."
            )
        if self.config.timeout_seconds <= 0:
            raise ValueError("timeout_seconds harus lebih besar dari nol.")

    def _url(self, path: str) -> str:
        return f"{self.config.backend_url.rstrip('/')}{path}"

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if not value:
            raise ForecastClientError("TrafficState tidak mempunyai timestamp.")
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ForecastClientError(f"Timestamp TrafficState tidak valid: {value}") from exc

    @staticmethod
    def _normalize_state(record: JsonDict) -> tuple[datetime, JsonDict] | None:
        state = record.get("trafficState")
        approach_rows = record.get("approaches")
        if not isinstance(state, dict) or not isinstance(approach_rows, list):
            return None

        timestamp_value = state.get("windowEnd") or state.get("windowStart")
        timestamp = ForecastClient._parse_timestamp(timestamp_value)
        rows = {
            str(row.get("approach", "")).lower(): row
            for row in approach_rows
            if isinstance(row, dict)
        }
        if not all(approach in rows for approach in APPROACHES):
            return None

        normalized_approaches = []
        for approach in APPROACHES:
            row = rows[approach]
            normalized_approaches.append(
                {
                    "approach": approach,
                    "vehicleCount": max(0.0, float(row.get("volume", 0) or 0)),
                    "queueLengthVeh": max(
                        0.0, float(row.get("queueLengthVeh", 0) or 0)
                    ),
                    "queueLengthMEst": max(
                        0.0, float(row.get("queueLengthMEst", 0) or 0)
                    ),
                    "densityIndex": min(
                        1.0,
                        max(
                            0.0,
                            float(row.get("densityIndex", 0) or 0)
                            / ZONE_CAPACITY,
                        ),
                    ),
                }
            )

        return timestamp, {
            "timestamp": timestamp.isoformat(),
            "approaches": normalized_approaches,
        }

    @classmethod
    def build_forecast_records(cls, traffic_records: list[JsonDict]) -> list[JsonDict]:
        normalized = []
        for record in traffic_records:
            parsed = cls._normalize_state(record)
            if parsed is not None:
                normalized.append(parsed)
        normalized.sort(key=lambda item: item[0])

        # Cari blok paling baru yang lengkap dan berinterval tepat lima detik.
        for end in range(len(normalized), REQUIRED_HISTORY_STEPS - 1, -1):
            window = normalized[end - REQUIRED_HISTORY_STEPS : end]
            contiguous = all(
                (window[index][0] - window[index - 1][0]).total_seconds()
                == INTERVAL_SECONDS
                for index in range(1, len(window))
            )
            if contiguous:
                return [item[1] for item in window]

        raise ForecastClientError(
            "Dibutuhkan 12 TrafficState lengkap dengan empat approach "
            "dan interval tepat lima detik."
        )

    def fetch_traffic_history(self) -> list[JsonDict]:
        intersection = quote(self.config.intersection_id, safe="")
        query = urlencode({"limit": self.config.history_limit})
        response = self.transport(
            "GET",
            self._url(f"/api/v1/traffic/{intersection}?{query}"),
            None,
            self.config.timeout_seconds,
        )
        if response.get("success") is not True:
            raise ForecastClientError("Backend gagal mengembalikan histori traffic.")
        data = response.get("data")
        if not isinstance(data, list):
            raise ForecastClientError("Field data histori traffic harus berupa list.")
        return data

    @staticmethod
    def validate_forecast(result: JsonDict) -> JsonDict:
        horizons = result.get("approachForecasts")
        if not isinstance(horizons, list) or len(horizons) != 12:
            raise ForecastClientError("Forecast harus mempunyai tepat 12 horizon.")

        for expected_step, horizon in enumerate(horizons, start=1):
            if not isinstance(horizon, dict):
                raise ForecastClientError("Setiap horizon forecast harus berupa object.")
            if horizon.get("secondsAhead") != expected_step * INTERVAL_SECONDS:
                raise ForecastClientError("Urutan secondsAhead forecast tidak valid.")
            rows = horizon.get("approaches")
            if not isinstance(rows, list):
                raise ForecastClientError("Horizon forecast tidak mempunyai approaches.")
            names = {
                str(row.get("approach", "")).lower()
                for row in rows
                if isinstance(row, dict)
            }
            if names != set(APPROACHES):
                raise ForecastClientError(
                    "Setiap horizon harus mempunyai west, south, east, dan north."
                )
        return result

    def request_forecast(self, records: list[JsonDict]) -> JsonDict:
        result = self.transport(
            "POST",
            self._url("/api/forecast/approaches"),
            {"records": records},
            self.config.timeout_seconds,
        )
        return self.validate_forecast(result)

    def get_live_forecast(self) -> JsonDict | None:
        """Kembalikan forecast valid atau None agar SUMO tetap bisa berjalan."""
        try:
            history = self.fetch_traffic_history()
            records = self.build_forecast_records(history)
            result = self.request_forecast(records)
            self.last_error = None
            return result
        except (ForecastClientError, ValueError, TypeError, OSError) as exc:
            self.last_error = str(exc)
            return None


def get_live_forecast(
    config: ForecastClientConfig | None = None,
) -> JsonDict | None:
    """Convenience function untuk dipanggil dari run_tls_simulation.py."""
    return ForecastClient(config=config).get_live_forecast()


__all__ = [
    "APPROACHES",
    "ForecastClient",
    "ForecastClientConfig",
    "ForecastClientError",
    "get_live_forecast",
]
