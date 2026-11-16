from actions import safe_path
from agent import interpret_request


def test_safe_path_stays_inside_workspace():
    path = safe_path("notes/example.txt")
    assert "agent_workspace" in str(path)


def test_parent_path_is_rejected():
    try:
        safe_path("../../private.txt")
    except ValueError:
        return
    raise AssertionError("Unsafe parent path was accepted")


def test_demo_interpreter_returns_approved_action(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    command = interpret_request("Create a note about loops")
    assert command.action == "create_note"
