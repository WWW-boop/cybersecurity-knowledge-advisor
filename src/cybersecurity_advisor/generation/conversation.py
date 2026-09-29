"""Short-lived, process-local conversation context."""

from threading import Lock
from time import monotonic

type ConversationTurn = tuple[str, str]


class ConversationStore:
    """Keep a bounded number of recent question-answer pairs per session."""

    def __init__(self) -> None:
        self._sessions: dict[str, tuple[float, tuple[ConversationTurn, ...]]] = {}
        self._lock = Lock()

    def get(self, session_key: str) -> tuple[ConversationTurn, ...]:
        with self._lock:
            entry = self._sessions.get(session_key)
            if entry is None:
                return ()
            if monotonic() - entry[0] >= 1800:
                self._sessions.pop(session_key, None)
                return ()
            return entry[1]

    def add(self, session_key: str, question: str, answer: str) -> None:
        with self._lock:
            now = monotonic()
            entry = self._sessions.pop(session_key, None)
            turns = entry[1] if entry is not None and now - entry[0] < 1800 else ()
            turns = (*turns, (question[:300], answer[:600]))[-3:]
            self._sessions[session_key] = (now, turns)
            if len(self._sessions) > 1000:
                self._sessions.pop(next(iter(self._sessions)))

    def clear(self, session_key: str) -> None:
        with self._lock:
            self._sessions.pop(session_key, None)
