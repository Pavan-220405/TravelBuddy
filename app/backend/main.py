import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.backend.routes.trip import router as trip_router
from app.guardrails.bedrock_guardrail import BedrockGuardrail
from app.mcp_sc.mcp_client import get_tools


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Initialize shared external resources once for the app lifetime."""

    try:
        mcp_tools = await get_tools()
        guardrail = BedrockGuardrail()
    except Exception:
        logger.exception("TravelBuddy startup failed")
        raise

    application.state.mcp_tools = mcp_tools
    application.state.guardrail = guardrail

    yield


app = FastAPI(
    title="TravelBuddy API",
    description="FastAPI backend for the TravelBuddy travel planning graph.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trip_router)
