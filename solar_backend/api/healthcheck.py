from fastapi import APIRouter

router = APIRouter(
    prefix="/healthcheck",
    tags=["healthcheck"],
)

@router.get("")
async def healthcheck() -> dict[str, str]:
    """Serve healthcheck API request."""
    return {"FastAPI": "OK"}