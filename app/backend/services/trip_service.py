import json
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.types import Command
from starlette.concurrency import run_in_threadpool

from app.agent.main import _run_graph, graph_config, supervisor_agent
from app.agent.schema import TravelState 


class TripServiceError(Exception):
    """Base class for errors that can be returned safely by the API."""

    status_code = 400
    status = "error"


class BlockedQueryError(TripServiceError):
    """Raised when the Bedrock guardrail blocks a user query."""

    status = "blocked"


class CheckpointNotFoundError(TripServiceError):
    """Raised when a thread does not have a resumable graph checkpoint."""

    status_code = 404
    status = "checkpoint_error"


def _require_startup_resources(application: Any) -> tuple[Any, Any]:
    state = application.state

    try:
        guardrail = state.guardrail
        mcp_tools = state.mcp_tools
    except AttributeError as exc:
        raise RuntimeError(
            "TravelBuddy startup resources are not initialized"
        ) from exc

    return guardrail, mcp_tools


def _text_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return str(value)


def _interrupt_payload(result: dict[str, Any]) -> dict[str, Any]:
    interrupts = result.get("__interrupt__") or []
    if not interrupts:
        return {}

    interrupt = interrupts[0]
    payload = getattr(interrupt, "value", interrupt)
    return payload if isinstance(payload, dict) else {}


def _blocked_message(guardrail_result: dict[str, Any]) -> str:
    outputs = guardrail_result.get("outputs") or []
    for output in outputs:
        if isinstance(output, dict) and output.get("text"):
            return _text_value(output["text"])

    reason = guardrail_result.get("action_reason")
    if reason:
        return _text_value(reason)

    return "The travel request was blocked by the safety guardrail."


async def generate_trip_draft(
    application: Any,
    *,
    user_id: str,
    thread_id: str,
    query: str,
) -> dict[str, Any]:
    """Run the existing supervisor and graph until human approval."""

    guardrail, _mcp_tools = _require_startup_resources(application)

    guardrail_result = await run_in_threadpool(
        guardrail.check,
        query=query,
        source="INPUT",
    )

    if not guardrail_result.get("allowed", not guardrail_result.get("blocked")):
        raise BlockedQueryError(_blocked_message(guardrail_result))

    checked_query = guardrail_result.get("checked_query") or query
    supervisor_plan = await supervisor_agent(checked_query)

    graph_input: TravelState = {
        "messages": [HumanMessage(content=checked_query)],
        "user_id": user_id,
        "user_query": checked_query,
        "selected_agents": supervisor_plan["selected_agents"],
        "trip_constraints": supervisor_plan["trip_constraints"],
        "supervisor_reasoning": supervisor_plan["supervisor_reasoning"],
        "llm_calls": supervisor_plan.get("llm_calls", 0),
    }

    result = await _run_graph(graph_input, graph_config(thread_id))
    interrupt = _interrupt_payload(result)

    return {
        "thread_id": thread_id,
        "status": "awaiting_approval" if interrupt else "completed",
        "supervisor_reasoning": _text_value(
            result.get(
                "supervisor_reasoning",
                supervisor_plan.get("supervisor_reasoning", ""),
            )
        ),
        "selected_agents": result.get(
            "selected_agents", supervisor_plan.get("selected_agents", [])
        ),
        "draft_itinerary": _text_value(
            interrupt.get("draft_itinerary") or result.get("itinerary", "")
        ),
        "flight_results": _text_value(result.get("flight_results", "")),
        "hotel_results": _text_value(result.get("hotel_results", "")),
        "weather_results": _text_value(result.get("weather_results", "")),
        "budget_results": _text_value(result.get("budget_results", "")),
    }


async def resume_trip(
    application: Any,
    *,
    thread_id: str,
    approved: bool,
    feedback: str = "",
) -> dict[str, Any]:
    """Resume an existing checkpointed graph after human feedback."""

    _require_startup_resources(application)
    command = Command(
        resume={
            "approved": approved,
            "feedback": feedback,
        }
    )

    try:
        final_result = await _run_graph(command, graph_config(thread_id))
    except (KeyError, ValueError) as exc:
        raise CheckpointNotFoundError(
            "No resumable trip draft was found for this thread."
        ) from exc

    return {
        "thread_id": thread_id,
        "status": (
            "awaiting_approval"
            if _interrupt_payload(final_result)
            else "completed"
        ),
        "final_response": _text_value(final_result.get("final_response", "")),
    }
