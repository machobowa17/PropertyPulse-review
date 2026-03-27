from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import resolve, area

app = FastAPI(
    title="UK Property Portal API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resolve.router, prefix="/api/v1")
app.include_router(area.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
