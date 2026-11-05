import asyncio
import uuid

import streamlit as st
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.agent.main import graph_config, run_graph, supervisor_agent
from app.guardrails.bedrock_guardrail import BedrockGuardrail
from app.mcp_sc.mcp_client import get_tools


st.set_page_config(page_title="TravelBuddy", layout="wide")
st.title("TravelBuddy")

if "guardrail" not in st.session_state:
    st.session_state.guardrail = BedrockGuardrail()

if "mcp_tools_ready" not in st.session_state:
    with st.spinner("Connecting to MCP servers..."):
        asyncio.run(get_tools())
    st.session_state.mcp_tools_ready = True

with st.sidebar:
    st.subheader("Session")
    user_id = st.text_input("User ID", value="demo_user")

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = f"{user_id}_{uuid.uuid4().hex[:8]}"

    if st.button("New Thread"):
        st.session_state.thread_id = f"{user_id}_{uuid.uuid4().hex[:8]}"
        st.session_state.pop("latest_result", None)
        st.session_state.pop("waiting_for_approval", None)

    st.caption(f"Thread: {st.session_state.thread_id}")


query = st.text_area(
    "Travel request",
    placeholder=(
        "Plan a 7-day Japan trip under Rs. 2 lakh. "
        "I prefer budget hotels and no overnight flights."
    ),
    height=110,
)

config = graph_config(st.session_state.thread_id)

if st.button("Create Draft Plan", type="primary"):
    if not query.strip():
        st.warning("Enter a travel request first.")
    else:
        try:
            # STEP 1: Guardrail check
            with st.spinner("Checking query with Bedrock Guardrails..."):
                guardrail_result = st.session_state.guardrail.check(
                    query=query,
                    source="INPUT",
                )

            # STEP 2: Stop if blocked
            if guardrail_result["blocked"]:
                st.session_state.pop("latest_result", None)
                st.session_state.waiting_for_approval = False
                fallback_message = (
                    guardrail_result["outputs"][0]["text"]
                    if guardrail_result["outputs"]
                    else "Your request was blocked by the TravelBuddy safety policy."
                )
                st.error(fallback_message)
            else:
                # Use anonymized query if PII was detected.
                checked_query = guardrail_result["checked_query"]

                # STEP 3: Supervisor
                with st.spinner("Supervisor is selecting agents..."):
                    supervisor_plan = asyncio.run(
                        supervisor_agent(checked_query)
                    )

                with st.spinner("Agents are planning..."):
                    result = run_graph(
                        {
                            "messages": [HumanMessage(content=checked_query)],
                            "user_id": user_id,
                            "user_query": checked_query,
                            "selected_agents": supervisor_plan["selected_agents"],
                            "trip_constraints": supervisor_plan["trip_constraints"],
                            "supervisor_reasoning": supervisor_plan[
                                "supervisor_reasoning"
                            ],
                            "llm_calls": supervisor_plan.get("llm_calls", 0),
                        },
                        config,
                    )

                st.session_state.latest_result = result
                st.session_state.waiting_for_approval = "__interrupt__" in result
        except Exception as exc:
            st.session_state.pop("latest_result", None)
            st.session_state.waiting_for_approval = False
            st.error(f"Unable to process your request safely: {exc}")


result = st.session_state.get("latest_result")

if result:
    st.subheader("Supervisor Plan")
    st.write(result.get("supervisor_reasoning", ""))
    st.write("Selected agents:", result.get("selected_agents", []))

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Flight")
        st.markdown(result.get("flight_results", ""))
        st.subheader("Weather")
        st.markdown(result.get("weather_results", ""))
    with col2:
        st.subheader("Hotels")
        st.markdown(result.get("hotel_results", ""))
        st.subheader("Budget")
        st.markdown(result.get("budget_results", ""))

    st.subheader("Draft Itinerary")
    if "__interrupt__" in result:
        draft = result["__interrupt__"][0].value.get("draft_itinerary", "")
    else:
        draft = result.get("itinerary", "")
    st.markdown(draft)


if st.session_state.get("waiting_for_approval"):
    st.divider()
    st.subheader("Human Approval")

    approved = st.radio(
        "Approve this draft?",
        ["Yes", "No, revise it"],
        horizontal=True,
    )
    feedback = st.text_area("Feedback", disabled=approved == "Yes")

    if st.button("Submit Approval"):
        with st.spinner("Creating final response..."):
            final_result = run_graph(
                Command(
                    resume={
                        "approved": approved == "Yes",
                        "feedback": feedback,
                    }
                ),
                config,
            )

        st.session_state.latest_result = final_result
        st.session_state.waiting_for_approval = False
        st.rerun()


final_result = st.session_state.get("latest_result")
if final_result and final_result.get("final_response"):
    st.divider()
    st.subheader("Final Travel Plan")
    st.markdown(final_result["final_response"])
