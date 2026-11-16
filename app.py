"""Streamlit interface for the Safe Student Productivity Agent."""

from __future__ import annotations

import os
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from actions import execute_action
from agent import interpret_request
from models import AgentCommand

load_dotenv()

st.set_page_config(
    page_title="Safe Student Productivity Agent",
    page_icon="📚",
    layout="centered",
)


def initialize_state() -> None:
    if "pending_command" not in st.session_state:
        st.session_state.pending_command = None
    if "last_command" not in st.session_state:
        st.session_state.last_command = None
    if "last_result" not in st.session_state:
        st.session_state.last_result = None


def show_command(command: AgentCommand) -> None:
    st.subheader("Interpreted action")
    st.write(f"**Action:** `{command.action}`")
    st.write(f"**Explanation:** {command.explanation}")
    st.write(f"**Requires confirmation:** {command.requires_confirmation}")
    if command.parameters:
        st.json(command.parameters)


def show_result(result: dict[str, Any]) -> None:
    if result.get("success"):
        st.success(result.get("message", "Action completed."))
        if result.get("data") is not None:
            st.write(result["data"])
    else:
        st.error(result.get("message", "The action could not be completed."))


initialize_state()

st.title("Safe Student Productivity Agent")
st.caption(
    "Enter a request in plain English. The agent interprets it, validates the action, "
    "and safely performs the requested task."
)

if not os.getenv("GEMINI_API_KEY"):
    st.info(
        "Demo mode is active because GEMINI_API_KEY is not set. "
        "Add the key to .env to use the live LLM."
    )

with st.expander("Example requests"):
    st.markdown(
        """
        - Create a note named recursion.txt explaining recursion.
        - List the files in my project.
        - Read recursion.txt.
        - Add a task called Study programming paradigms.
        - Show all of my tasks.
        - Create a folder named exam_notes.
        - Summarize this text: Static typing checks types before execution.
        """
    )

request = st.text_area(
    "What would you like the agent to do?",
    height=120,
    placeholder="Example: Create a note named loops.txt explaining Python loops.",
)

if st.button("Interpret and execute", type="primary"):
    if not request.strip():
        st.warning("Enter a request first.")
    else:
        try:
            command = interpret_request(request.strip())
            st.session_state.last_command = command
            st.session_state.last_result = None
            if command.requires_confirmation:
                st.session_state.pending_command = command
                st.warning("This action requires your confirmation before it can run.")
            else:
                st.session_state.last_result = execute_action(command)
        except Exception as exc:
            st.session_state.pending_command = None
            st.session_state.last_result = {
                "success": False,
                "message": f"Agent error: {exc}",
                "data": None,
            }

if st.session_state.last_command is not None:
    show_command(st.session_state.last_command)

pending = st.session_state.pending_command
if pending is not None:
    st.warning("Review the action above before confirming it.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirm action"):
            st.session_state.last_result = execute_action(pending, confirmed=True)
            st.session_state.pending_command = None
            st.rerun()
    with col2:
        if st.button("Cancel action"):
            st.session_state.pending_command = None
            st.session_state.last_result = {
                "success": False,
                "message": "Action cancelled by the user.",
                "data": None,
            }
            st.rerun()

if st.session_state.last_result is not None:
    st.subheader("Execution result")
    show_result(st.session_state.last_result)

st.divider()
st.caption("Actions are restricted to the approved allowlist and recorded in action_log.txt.")
