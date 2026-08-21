"""
Connection manager untuk push realtime ke dashboard.

Dipakai sebagai pengganti Supabase Realtime, yang terbukti tidak
mem-broadcast postgres_changes di project ini meski publication,
RLS, dan status service semuanya sudah benar (diverifikasi manual
lewat websocket langsung, termasuk dengan service_role key yang
bypass RLS -- tetap nol event). Jalur ini murni event-driven, tidak
ada polling di mana pun: cv/process_uploaded_video.py memanggil
POST /api/v1/traffic/notify PERSIS setelah satu window berhasil
ditulis ke Supabase, lalu di sini langsung di-broadcast ke seluruh
browser yang terhubung ke WebSocket -- delay-nya cuma seukuran satu
HTTP request + satu WS frame, bukan interval polling.
"""

from __future__ import annotations

from fastapi import WebSocket


class TrafficWsManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        stale: list[WebSocket] = []

        for connection in self._connections:
            try:
                await connection.send_json(message)
            except Exception:  # noqa: BLE001
                stale.append(connection)

        for connection in stale:
            self.disconnect(connection)


traffic_ws_manager = TrafficWsManager()
