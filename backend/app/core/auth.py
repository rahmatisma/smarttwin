from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.services.supabase_client import get_supabase


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    role: str
    email: str | None = None


def _read_value(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def _user_from_response(response: Any) -> AuthenticatedUser:
    user = _read_value(response, "user")
    if user is None:
        data = _read_value(response, "data")
        user = _read_value(data, "user") if data is not None else None
    if user is None:
        raise ValueError("User tidak ditemukan pada respons autentikasi.")

    app_metadata = _read_value(user, "app_metadata", {}) or {}
    role = str(_read_value(app_metadata, "role", "authenticated"))
    return AuthenticatedUser(
        id=str(_read_value(user, "id", "")),
        email=_read_value(user, "email"),
        role=role,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    """Validasi access token Supabase ketika proteksi backend diaktifkan."""
    if not settings.auth_required:
        return AuthenticatedUser(id="local-development", role="operator")

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token diperlukan.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = get_supabase().auth.get_user(credentials.credentials)
        return _user_from_response(response)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token tidak valid atau sudah kedaluwarsa.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_operator(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    allowed_roles = settings.operator_roles_list
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role pengguna tidak diizinkan menjalankan operasi ini.",
        )
    return user
