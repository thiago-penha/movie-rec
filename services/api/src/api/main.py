from fastapi import APIRouter, FastAPI

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
def health() -> dict[str, str]:
    # Phase 1 adds a database check ({"status": ..., "db": ...}).
    return {"status": "ok"}


app.include_router(router)
