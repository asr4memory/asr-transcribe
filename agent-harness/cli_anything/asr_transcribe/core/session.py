"""Session state management for REPL mode."""

import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Session:
    """Maintains state across REPL commands."""

    project_root: Path | None = None
    last_json_path: str | None = None
    last_audio_path: str | None = None
    last_output_dir: str | None = None
    history: list = field(default_factory=list)

    def record(self, command: str, result: dict | None = None):
        """Record a command in the session history."""
        entry = {"command": command}
        if result and isinstance(result, dict):
            entry["status"] = result.get("status", result.get("message", "ok"))
        self.history.append(entry)

    def to_dict(self) -> dict:
        """Serialize session to dict."""
        return {
            "project_root": str(self.project_root) if self.project_root else None,
            "last_json_path": self.last_json_path,
            "last_audio_path": self.last_audio_path,
            "last_output_dir": self.last_output_dir,
            "history_count": len(self.history),
        }
