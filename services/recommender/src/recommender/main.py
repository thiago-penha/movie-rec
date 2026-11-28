from fastapi import APIRouter, FastAPI, Response

from common.db import ping

# Same idea as the api service: everything under one path prefix (/rec).
app = FastAPI(
    title="CineMatch Recommender",
    docs_url="/rec/docs",
    redoc_url=None,
    openapi_url="/rec/openapi.json",
)

router = APIRouter(prefix="/rec")


@router.get("/health")
def health(response: Response) -> dict[str, str]:
    # Same contract as /api/health. Phase 4 adds "model_loaded".
    db_ok = ping()
    if not db_ok:
        response.status_code = 503
    return {"status": "ok" if db_ok else "error", "db": "ok" if db_ok else "error"}


app.include_router(router)
