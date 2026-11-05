import asyncio
import selectors
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agent.prompts import (
    BUDGET_SYSTEM_PROMPT,
    FINAL_RESPONSE_SYSTEM_PROMPT,
    ITINERARY_SYSTEM_PROMPT,
    SUPERVISOR_SYSTEM_PROMPT,
    approval_request_prompt,
    approved_final_prompt,
    budget_prompt,
    hotel_search_query,
    itinerary_prompt,
    revision_final_prompt,
    supervisor_prompt,
    weather_result_prompt,
)
from app.agent.schema import ApprovalFeedback, SupervisorOutput, TravelState
from app.config import settings
from app.mcp_sc.mcp_client import (
    current_weather,
    forecast,
    list_airlines,
    list_airports,
    tavily_search,
)

load_dotenv()

llm = ChatGroq(model=settings.medium_model)


def graph_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


async def supervisor_agent(user_query: str) -> dict[str, Any]:
    result = await llm.with_structured_output(SupervisorOutput).ainvoke(
        [
            SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
            HumanMessage(content=supervisor_prompt(user_query)),
        ]
    )

    selected_agents = list(
        dict.fromkeys([*result.selected_agents, "itinerary_agent"])
    )

    return {
        "selected_agents": selected_agents,
        "trip_constraints": result.trip_constraints.model_dump(),
        "supervisor_reasoning": result.reasoning,
        "messages": [AIMessage(content="Supervisor created the agent plan.")],
        "llm_calls": 1,
    }


async def flight_agent(state: TravelState) -> dict[str, Any]:
    if "flight_agent" not in state["selected_agents"]:
        return {}

    constraints = state["trip_constraints"]
    airports, airlines = await asyncio.gather(
        list_airports(constraints["destination"], limit=10),
        list_airlines("", limit=10),
    )
    return {
        "flight_results": (
            f"Airport MCP data:\n{airports}\n\n"
            f"Airline MCP data:\n{airlines}"
        ),
        "messages": [AIMessage(content="Flight data retrieval completed.")],
    }


async def hotel_agent(state: TravelState) -> dict[str, Any]:
    if "hotel_agent" not in state["selected_agents"]:
        return {}

    result = await tavily_search(hotel_search_query(state["user_query"]))
    return {
        "hotel_results": str(result),
        "messages": [AIMessage(content="Hotel agent completed.")],
    }


async def weather_agent(state: TravelState) -> dict[str, Any]:
    if "weather_agent" not in state["selected_agents"]:
        return {}

    destination = state["trip_constraints"]["destination"]
    weather_data, forecast_data = await asyncio.gather(
        current_weather(destination),
        forecast(destination),
    )
    return {
        "weather_results": weather_result_prompt(weather_data, forecast_data),
        "messages": [AIMessage(content="Weather agent completed.")],
    }


async def budget_agent(state: TravelState) -> dict[str, Any]:
    if "budget_agent" not in state["selected_agents"]:
        return {}

    response = await llm.ainvoke(
        [
            SystemMessage(content=BUDGET_SYSTEM_PROMPT),
            HumanMessage(content=budget_prompt(state)),
        ]
    )
    return {
        "budget_results": response.content,
        "messages": [AIMessage(content="Budget agent completed.")],
        "llm_calls": 1,
    }


async def itinerary_agent(state: TravelState) -> dict[str, Any]:
    if "itinerary_agent" not in state["selected_agents"]:
        return {}

    response = await llm.ainvoke(
        [
            SystemMessage(content=ITINERARY_SYSTEM_PROMPT),
            HumanMessage(content=itinerary_prompt(state)),
        ]
    )
    return {
        "itinerary": response.content,
        "approval_request": approval_request_prompt(response.content),
        "messages": [AIMessage(content="Draft itinerary created for human review.")],
        "llm_calls": 1,
    }


def human_approval_agent(state: TravelState) -> dict[str, Any]:
    feedback = ApprovalFeedback.model_validate(
        interrupt(
            {
                "question": "Do you approve this itinerary?",
                "draft_itinerary": state.get("itinerary", ""),
                "approval_request": state.get("approval_request", ""),
            }
        )
    )
    return {
        "approved": feedback.approved,
        "human_feedback": feedback.feedback,
        "messages": [AIMessage(content="Human approval step completed.")],
    }


async def final_response_agent(state: TravelState) -> dict[str, Any]:
    if state["approved"]:
        prompt = approved_final_prompt(
            state["itinerary"],
            state.get("budget_results", ""),
        )
    else:
        prompt = revision_final_prompt(
            state["user_query"],
            state["itinerary"],
            state["human_feedback"],
            state.get("budget_results", ""),
        )

    response = await llm.ainvoke(
        [
            SystemMessage(content=FINAL_RESPONSE_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
    )
    return {
        "final_response": response.content,
        "messages": [AIMessage(content=response.content)],
        "llm_calls": 1,
    }


def join_agent_results(state: TravelState) -> dict[str, Any]:
    result_fields = {
        "flight_agent": "flight_results",
        "hotel_agent": "hotel_results",
        "weather_agent": "weather_results",
    }

    for agent_name in state["selected_agents"]:
        result_field = result_fields.get(agent_name)
        if result_field is None:
            continue

        result = state.get(result_field, "")
        if not result or not str(result).strip():
            raise ValueError(
                f"Selected agent '{agent_name}' did not produce a result in "
                f"state['{result_field}']."
            )

    return {}


def route_after_join(state: TravelState) -> str:
    if "budget_agent" in state["selected_agents"]:
        return "budget"
    return "itinerary"


def build_graph(checkpointer: AsyncPostgresSaver):
    workflow = StateGraph(TravelState)
    workflow.add_node("flight", flight_agent)
    workflow.add_node("hotel", hotel_agent)
    workflow.add_node("weather", weather_agent)
    workflow.add_node("budget", budget_agent)
    workflow.add_node("join", join_agent_results)
    workflow.add_node("itinerary", itinerary_agent)
    workflow.add_node("human_approval", human_approval_agent)
    workflow.add_node("final_response", final_response_agent)

    workflow.add_edge(START, "flight")
    workflow.add_edge(START, "hotel")
    workflow.add_edge(START, "weather")
    workflow.add_edge(["flight", "hotel", "weather"], "join")
    workflow.add_conditional_edges("join", route_after_join)
    workflow.add_edge("budget", "itinerary")
    workflow.add_edge("itinerary", "human_approval")
    workflow.add_edge("human_approval", "final_response")
    workflow.add_edge("final_response", END)

    return workflow.compile(checkpointer=checkpointer)


async def _run_graph(
    input_data: dict[str, Any] | Any,
    config: dict[str, Any],
) -> dict[str, Any]:
    # The graph contains async nodes, so its checkpointer must also implement
    # the async checkpoint API. Keep the connection and graph in the same
    # event loop and close the database connection after each invocation.
    async with AsyncPostgresSaver.from_conn_string(
        str(settings.database_url)
    ) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(checkpointer)
        return await graph.ainvoke(input_data, config=config)


def run_graph(
    input_data: dict[str, Any] | Any,
    config: dict[str, Any],
) -> dict[str, Any]:
    # Psycopg's async driver does not support Windows' default
    # ProactorEventLoop. Use a selector loop for the graph invocation.
    def selector_loop() -> asyncio.AbstractEventLoop:
        return asyncio.SelectorEventLoop(selectors.SelectSelector())

    return asyncio.run(
        _run_graph(input_data, config),
        loop_factory=selector_loop,
    )
