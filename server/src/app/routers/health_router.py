from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get("/health")
async def health() -> HealthResponse:
    """Unauthenticated on purpose -- container/load-balancer probes have no token."""
    return HealthResponse(status="ok")
