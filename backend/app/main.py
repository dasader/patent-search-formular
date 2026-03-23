import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.services.patent_searcher import init_searchers

logging.basicConfig(level=logging.INFO)
for name in ["httpx", "httpcore", "chromadb"]:
    logging.getLogger(name).setLevel(logging.WARNING)


def create_app() -> FastAPI:
    app = FastAPI(title="Patent Connector API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.on_event("startup")
    async def startup():
        init_searchers()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
