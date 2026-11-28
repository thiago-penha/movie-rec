from fastapi import APIRouter, FastAPI, Response

from common.db import ping

# Every route lives under /api, so Caddy (prod) and the Vite proxy (dev) can route
# by path prefix without rewriting URLs. Docs are moved under the prefix too.
app = FastAPI(
    title="CineMatch API",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

router = APIRouter(prefix="/api")


@router.get("/health")
def health(response: Response) -> dict[str, str]:
    # 503 when the database is down, so the Docker healthcheck marks the container
    # unhealthy and the frontend shows the service as unreachable.
    db_ok = ping()
    if not db_ok:
        response.status_code = 503
    return {"status": "ok" if db_ok else "error", "db": "ok" if db_ok else "error"}


app.include_router(router)
