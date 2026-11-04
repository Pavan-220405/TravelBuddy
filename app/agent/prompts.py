from typing import Any


SUPERVISOR_SYSTEM_PROMPT = (
    "You route work to specialist agents for a real-world travel planning system."
)
BUDGET_SYSTEM_PROMPT = "You are a practical travel budget analyst."
ITINERARY_SYSTEM_PROMPT = "You are an expert itinerary planner."
FINAL_RESPONSE_SYSTEM_PROMPT = "You produce final user-ready travel plans."


def supervisor_prompt(query: str) -> str:
    return f"""
Decide which specialist agents are needed for this user request.

Available agents:
- flight_agent: use when flights, airports, airlines, routes, or airfare guidance are needed
- hotel_agent: use when hotels, stays, neighborhoods, or accommodation are needed
- weather_agent: use when weather, climate, season, packing, or forecast is useful
- budget_agent: use when budget, affordability, cost, or price constraints are mentioned
- itinerary_agent: almost always needed to produce the travel plan

User request:
{query}
"""


def hotel_search_query(user_query: str) -> str:
    return f"Best hotels and areas to stay for: {user_query}"


def weather_result_prompt(weather_data: Any, forecast_data: Any) -> str:
    return f"""
Current weather:
{weather_data}

Forecast:
{forecast_data}
"""


def budget_prompt(state: dict[str, Any]) -> str:
    return f"""
Analyze whether this trip plan is realistic for the user's budget.

User request:
{state["user_query"]}

Constraints:
{state.get("trip_constraints", {})}

Flight results:
{state.get("flight_results", "")}

Hotel results:
{state.get("hotel_results", "")}

Return a concise budget assessment with:
1. estimated cost categories
2. risk areas
3. money-saving suggestions
4. whether the plan seems feasible
"""


def itinerary_prompt(state: dict[str, Any]) -> str:
    return f"""
Create a clear draft travel itinerary.

User request:
{state["user_query"]}

Trip constraints:
{state.get("trip_constraints", {})}

Flight results:
{state.get("flight_results", "")}

Hotel results:
{state.get("hotel_results", "")}

Weather results:
{state.get("weather_results", "")}

Budget results:
{state.get("budget_results", "")}

Make the output structured, practical, and ready for human review.
"""


def approval_request_prompt(itinerary: str) -> str:
    return f"""
Please review this draft travel plan.

{itinerary}

Reply with approval or feedback.
"""


def approved_final_prompt(itinerary: str, budget_results: str) -> str:
    return f"""
The human approved this draft itinerary.

Produce the final polished travel plan.

Draft itinerary:
{itinerary}

Budget notes:
{budget_results}
"""


def revision_final_prompt(
    user_query: str,
    itinerary: str,
    human_feedback: str,
    budget_results: str,
) -> str:
    return f"""
The human did not approve the draft.

Original user request:
{user_query}

Draft itinerary:
{itinerary}

Human feedback:
{human_feedback}

Budget notes:
{budget_results}
"""
