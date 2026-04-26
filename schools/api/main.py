"""School Intelligence API — serves school data from Hetzner."""

from fastapi import FastAPI
from api.routers import schools, nurseries

app = FastAPI(title="PropertyPulse School API", version="1.0.0")
app.include_router(schools.router, prefix="/schools", tags=["schools"])
app.include_router(nurseries.router, prefix="/nurseries", tags=["nurseries"])


@app.get("/health")
def health():
    return {"status": "ok"}
