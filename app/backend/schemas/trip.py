from pydantic import BaseModel, Field, field_validator


class TripRequest(BaseModel):
    user_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    query: str = Field(min_length=1)

    @field_validator("user_id", "thread_id", "query")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value


class ApprovalRequest(BaseModel):
    approved: bool
    feedback: str = ""


class TripDraftResponse(BaseModel):
    thread_id: str
    status: str
    supervisor_reasoning: str = ""
    selected_agents: list[str] = Field(default_factory=list)
    draft_itinerary: str = ""
    flight_results: str = ""
    hotel_results: str = ""
    weather_results: str = ""
    budget_results: str = ""


class TripFinalResponse(BaseModel):
    thread_id: str
    status: str
    final_response: str = ""


class ErrorResponse(BaseModel):
    detail: str
    status: str


class HealthResponse(BaseModel):
    status: str
    service: str
