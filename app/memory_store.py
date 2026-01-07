from typing import Dict, List, Optional
import uuid

# session_id -> chat history
_SESSIONS: Dict[str, List[dict]] = {}

# session_id -> pending write request
_PENDING: Dict[str, dict] = {}


def get_history(session_id: str) -> List[dict]:
    return _SESSIONS.get(session_id, []).copy()


def append_message(session_id: str, role: str, content: str):
    _SESSIONS.setdefault(session_id, []).append({"role": role, "content": content})


def clear_history(session_id: str):
    _SESSIONS[session_id] = []
    _PENDING.pop(session_id, None)


def set_pending(session_id: str, user_request: str) -> str:
    action_id = str(uuid.uuid4())
    _PENDING[session_id] = {"action_id": action_id, "user_request": user_request}
    return action_id


def get_pending(session_id: str) -> Optional[dict]:
    return _PENDING.get(session_id)


def clear_pending(session_id: str):
    _PENDING.pop(session_id, None)
