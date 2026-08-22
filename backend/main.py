from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base, run_migrations
import models  # noqa: F401 -- ensures models are registered before create_all
from routers import auth_router, upload_router, costs_router, insights_router
from routers import budgets_router


# Create database tables
Base.metadata.create_all(bind=engine)

# Safely add new columns to existing tables without losing data
run_migrations()


app = FastAPI(
    title="FinOps AI",
    description=(
        "AI-powered multi-cloud cost optimization platform. "
        "Supports AWS, Azure, and GCP billing data."
    ),
    version="2.0.0",
)


# ---------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "https://finops-ai-frontend.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Routers
# ---------------------------------------------------------
app.include_router(auth_router.router)
app.include_router(upload_router.router)
app.include_router(costs_router.router)
app.include_router(insights_router.router)
app.include_router(budgets_router.router)


# ---------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------
@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "FinOps AI backend",
        "version": "2.0.0",
        "docs": "/docs",
    }