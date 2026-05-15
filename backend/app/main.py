"""
yourDIU Backend API
===================
FastAPI application — entry point.

Run locally:
    cd backend
    uvicorn app.main:app --reload --port 8000

Docs (no frontend needed):
    http://localhost:8000/docs
"""

import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("yourDIU")


def _print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║    ██╗   ██╗ ██████╗ ██╗   ██╗██████╗ ██████╗ ██╗██╗   ██╗  ║
║    ╚██╗ ██╔╝██╔═══██╗██║   ██║██╔══██╗██╔══██╗██║██║   ██║  ║
║     ╚████╔╝ ██║   ██║██║   ██║██████╔╝██║  ██║██║██║   ██║  ║
║      ╚██╔╝  ██║   ██║██║   ██║██╔══██╗██║  ██║██║██║   ██║  ║
║       ██║   ╚██████╔╝╚██████╔╝██║  ██║██████╔╝██║╚██████╔╝  ║
║       ╚═╝    ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚═╝ ╚═════╝   ║
║                                                              ║
║          Daffodil International University Assistant         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _print_banner()
    logger.info("=" * 60)
    logger.info("yourDIU API starting — env: %s", settings.app_env)
    logger.info("Docs available at: http://localhost:%d/docs", settings.app_port)
    logger.info("=" * 60)
    yield
    logger.info("yourDIU API shutting down. Bye!")


app = FastAPI(
    title="yourDIU API",
    description=(
        "Virtual assistant backend for Daffodil International University. "
        "Teachers and students can chat, read notices, and join the community."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root():
    return {
        "name": "yourDIU API",
        "version": "0.1.0",
        "status": "online",
        "docs": "/docs",
        "env": settings.app_env,
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


def run():
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=not settings.is_production,
    )


if __name__ == "__main__":
    run()
