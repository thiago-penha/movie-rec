from fastapi import APIRouter, FastAPI

# Same idea as the api service: everything under one path prefix (/rec).
app = FastAPI(
    title="CineMatch Recommender",
    docs_url="/rec/docs",
    redoc_url=None,
    openapi_url="/rec/openapi.json",
)

router = APIRouter(prefix="/rec")


@router.get("/health")
def health() -> dict[str, str]:
    # Phase 1 adds "db"; Phase 4 adds "model_loaded".
    return {"status": "ok"}


app.include_router(router)
