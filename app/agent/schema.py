from typing import Annotated, Any, Literal, Required, TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
import operator


class TravelState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str
    user_query: str

    trip_constraints: Required[dict[str, Any]]
    selected_agents: Required[list[str]]
    supervisor_reasoning: str

    flight_results: str
    hotel_results: str
    weather_results: str
    budget_results: str
    itinerary: str

    final_response: str
    llm_calls: Annotated[int, operator.add]
    approval_request: str
    approved: bool
    human_feedback: str



class TripConstraints(BaseModel):
    destination: str = ""
    origin: str = ""
    duration: str = ""
    budget: str = ""
    travel_style: str = ""
    special_preferences: list[str] = Field(default_factory=list)


class SupervisorOutput(BaseModel):
    selected_agents: list[
        Literal[
            "flight_agent",
            "hotel_agent",
            "weather_agent",
            "budget_agent",
            "itinerary_agent",
        ]
    ]
    trip_constraints: TripConstraints
    reasoning: str


class ApprovalFeedback(BaseModel):
    approved: bool
    feedback: str = ""
