from collections import deque
from typing import Deque, Dict, List

class CommandHistory:
    def __init__(self, max_history: int = 5):
        self._max_history = max_history
        self._history: Dict[int, Deque[str]] = {}

    def record(self, user_id: int, command_name: str) -> None:
        history = self._history.setdefault(user_id, deque(maxlen=self._max_history))
        history.append(command_name)

    def get_last_commands(self, user_id: int, count: int = 5) -> List[str]:
        history = self._history.get(user_id)
        if not history:
            return []
        window = min(count, self._max_history)
        return list(history)[-window:]

    def clear_user(self, user_id: int) -> None:
        self._history.pop(user_id, None)

    def clear_all(self) -> None:
        self._history.clear()

command_history = CommandHistory()