from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
import models  # noqa: F401 -- ensures models are registered before create_all
from routers import auth_router, upload_router, costs_router, insights_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FinOps AI",
    description="AI-powered cloud cost optimization platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(upload_router.router)
app.include_router(costs_router.router)
app.include_router(insights_router.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "FinOps AI backend", "docs": "/docs"}
