import os
from typing import Optional

import httpx
from fastapi import Depends, Header, HTTPException


def get_optional_authenticated_user_id(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    if not authorization:
        return None

    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Token de autenticación inválido")

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise HTTPException(
            status_code=503,
            detail="La autenticación de Supabase no está configurada",
        )

    try:
        response = httpx.get(
            f"{supabase_url.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {token.strip()}",
            },
            timeout=5.0,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail="No fue posible verificar la sesión de Supabase",
        ) from exc

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Sesión inválida o vencida")

    try:
        user_id = response.json().get("id")
    except (ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Respuesta de autenticación inválida",
        ) from exc

    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=401, detail="Sesión sin usuario válido")

    return user_id


def get_authenticated_user_id(
    user_id: Optional[str] = Depends(get_optional_authenticated_user_id),
) -> str:
    if user_id is None:
        raise HTTPException(status_code=401, detail="Debes iniciar sesión")
    return user_id
