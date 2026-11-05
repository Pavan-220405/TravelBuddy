import os
import uuid

import requests
import streamlit as st


API_BASE_URL = os.getenv("TRAVELBUDDY_API_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT_SECONDS = 300


def _new_thread_id(user_id: str) -> str:
    return f"{user_id}_{uuid.uuid4().hex[:8]}"


def _clear_thread_results() -> None:
    for key in (
        "draft_result",
        "final_result",
        "api_error",
        "approval_choice",
        "approval_feedback",
    ):
        st.session_state.pop(key, None)


def _display_api_error(response: requests.Response) -> None:
    try:
        payload = response.json()
        detail = payload.get("detail", response.text)
    except ValueError:
        detail = response.text or "The TravelBuddy API returned an error."
    st.error(f"{detail} (status: {response.status_code})")


st.set_page_config(page_title="TravelBuddy", layout="wide")
st.title("TravelBuddy")

if "user_id" not in st.session_state:
    st.session_state.user_id = "demo_user"

with st.sidebar:
    st.subheader("Session")
    user_id = st.text_input("User ID", key="user_id")

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = _new_thread_id(user_id)
        st.session_state.thread_user_id = user_id

    if st.session_state.get("thread_user_id") != user_id:
        st.session_state.thread_id = _new_thread_id(user_id)
        st.session_state.thread_user_id = user_id
        _clear_thread_results()

    if st.button("New Thread"):
        st.session_state.thread_id = _new_thread_id(user_id)
        st.session_state.thread_user_id = user_id
        _clear_thread_results()
        st.rerun()

    st.caption(f"Thread: {st.session_state.thread_id}")
    st.caption(f"Backend: {API_BASE_URL}")


query = st.text_area(
    "Travel request",
    key="query",
    placeholder=(
        "Plan a 7-day Japan trip under Rs. 2 lakh. "
        "I prefer budget hotels and no overnight flights."
    ),
    height=110,
)

if st.button("Create Draft Plan", type="primary"):
    if not query.strip():
        st.warning("Enter a travel request first.")
    else:
        with st.spinner("TravelBuddy is preparing your draft..."):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/api/trips/draft",
                    json={
                        "user_id": user_id,
                        "thread_id": st.session_state.thread_id,
                        "query": query,
                    },
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            except requests.RequestException as exc:
                st.error(f"Could not reach the TravelBuddy API: {exc}")
            else:
                if response.ok:
                    st.session_state.draft_result = response.json()
                    st.session_state.pop("final_result", None)
                else:
                    _display_api_error(response)


draft = st.session_state.get("draft_result")
if draft:
    st.subheader("Supervisor Plan")
    st.write(draft.get("supervisor_reasoning", ""))
    st.write("Selected agents:", draft.get("selected_agents", []))

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Flight")
        st.markdown(draft.get("flight_results", ""))
        st.subheader("Weather")
        st.markdown(draft.get("weather_results", ""))
    with col2:
        st.subheader("Hotels")
        st.markdown(draft.get("hotel_results", ""))
        st.subheader("Budget")
        st.markdown(draft.get("budget_results", ""))

    st.subheader("Draft Itinerary")
    st.markdown(draft.get("draft_itinerary", ""))

    if draft.get("status") == "awaiting_approval":
        st.divider()
        st.subheader("Human Approval")
        approval_choice = st.radio(
            "Approve this draft?",
            ["Yes", "No, revise it"],
            key="approval_choice",
            horizontal=True,
        )
        feedback = st.text_area(
            "Feedback",
            key="approval_feedback",
            disabled=approval_choice == "Yes",
        )

        if st.button("Submit Approval"):
            with st.spinner("Creating final travel plan..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/api/trips/"
                        f"{st.session_state.thread_id}/approval",
                        json={
                            "approved": approval_choice == "Yes",
                            "feedback": feedback,
                        },
                        timeout=REQUEST_TIMEOUT_SECONDS,
                    )
                except requests.RequestException as exc:
                    st.error(f"Could not reach the TravelBuddy API: {exc}")
                else:
                    if response.ok:
                        st.session_state.final_result = response.json()
                    else:
                        _display_api_error(response)


final_result = st.session_state.get("final_result")
if final_result and final_result.get("final_response"):
    st.divider()
    st.subheader("Final Travel Plan")
    st.markdown(final_result["final_response"])
