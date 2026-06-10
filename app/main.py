from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.routes import router as v1_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    yield



app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
    description="Alkitab Data API: Scraping, searching, and resolving Bible verses using LLM.",
    summary="API untuk scraping Alkitab dari Sabda.org, searching ayat, dan resolving referensi menggunakan BLIP-Text LLM.",
    contact={
        "name": "Alkitab Data API",
        "url": "https://github.com/anomalyco/alkitab-data-py",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix=settings.API_V1_PREFIX)

output_dir = Path(__file__).parent.parent / "output"
output_dir.mkdir(exist_ok=True)
app.mount("/output", StaticFiles(directory=output_dir), name="output")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}
