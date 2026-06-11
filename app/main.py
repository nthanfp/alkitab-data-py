import json
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from app.api.v1.routes import router as v1_router
from app.core.config import settings


def sanitize_json_body(body: str) -> str:
    """Replace literal newlines inside JSON string values with spaces."""
    result = []
    in_string = False
    escape = False
    for ch in body:
        if escape:
            result.append(ch)
            escape = False
            continue
        if ch == '\\':
            result.append(ch)
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if in_string and ch in ('\n', '\r'):
            result.append(' ')
            continue
        result.append(ch)
    return ''.join(result)


SANITIZE_PATHS = {"/api/v1/resolve-verse", "/api/v1/generate-verse-image"}


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


@app.middleware("http")
async def sanitize_newline_middleware(request: Request, call_next):
    if request.method == "POST" and request.url.path in SANITIZE_PATHS:
        body = await request.body()
        text = body.decode("utf-8")
        sanitized = sanitize_json_body(text)
        if sanitized != text:
            async def receive():
                return {"type": "http.request", "body": sanitized.encode("utf-8")}
            request._receive = receive
    response = await call_next(request)
    return response


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
