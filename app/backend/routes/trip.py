import logging

from fastapi import APIRouter, Path, Request
from fastapi.responses import JSONResponse

from app.backend.schemas.trip import (
    ApprovalRequest,
    ErrorResponse,
    HealthResponse,
    TripDraftResponse,
    TripFinalResponse,
    TripRequest,
)
from app.backend.services.trip_service import (
    TripServiceError,
    generate_trip_draft,
    resume_trip,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Travel planning"])


def _error_response(status_code: int, detail: str, status: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(detail=detail, status=status).model_dump(),
    )


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="healthy", service="TravelBuddy API")


@router.post(
    "/trips/draft",
    response_model=TripDraftResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def create_trip_draft(
    payload: TripRequest,
    request: Request,
) -> TripDraftResponse | JSONResponse:
    try:
        return await generate_trip_draft(
            request.app,
            user_id=payload.user_id,
            thread_id=payload.thread_id,
            query=payload.query,
        )
    except TripServiceError as exc:
        return _error_response(exc.status_code, str(exc), exc.status)
    except Exception:
        logger.exception("Trip draft generation failed")
        return _error_response(
            500,
            "Unable to generate a trip draft.",
            "error",
        )


@router.post(
    "/trips/{thread_id}/approval",
    response_model=TripFinalResponse,
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def approve_trip(
    payload: ApprovalRequest,
    request: Request,
    thread_id: str = Path(min_length=1),
) -> TripFinalResponse | JSONResponse:
    try:
        return await resume_trip(
            request.app,
            thread_id=thread_id,
            approved=payload.approved,
            feedback=payload.feedback,
        )
    except TripServiceError as exc:
        return _error_response(exc.status_code, str(exc), exc.status)
    except Exception:
        logger.exception("Trip approval failed for thread %s", thread_id)
        return _error_response(
            500,
            "Unable to resume the trip plan.",
            "error",
        )
