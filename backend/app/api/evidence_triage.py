import os

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app import security
from app.database import SessionLocal
from app.services.triage_signal_bridge import safe_record_paid_triage

router = APIRouter(
    prefix="/evidence-triage",
    tags=["evidence-triage"],
)

TRIAGE_URL = os.getenv(
    "EVIDENCE_TRIAGE_URL",
    "http://evidence-triage:8787",
)

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


@router.post("/triage")
async def triage(request: Request):
    security.require_owner_api_key(request)
    body = await request.body()

    if len(body) > 12 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Payload too large",
        )

    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be application/json",
        )

    forward_headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP
        and key.lower() != "host"
    }

    forward_headers["x-forwarded-host"] = request.headers.get(
        "host",
        "127.0.0.1:8000",
    )
    forward_headers["x-forwarded-proto"] = request.url.scheme

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{TRIAGE_URL}/triage",
                content=body,
                headers=forward_headers,
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Evidence triage service unavailable",
        )

    response_headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in HOP_BY_HOP
        and key.lower() != "content-length"
    }

    if response.status_code == 200:
        db = SessionLocal()
        try:
            safe_record_paid_triage(db, body, response.content, response.status_code)
        finally:
            db.close()

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response_headers,
    )
