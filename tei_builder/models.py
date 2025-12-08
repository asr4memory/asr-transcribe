"""
Data models for Whisper transcription data.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class WhisperWord:
    """Represents a single word from Whisper output."""
    word: str
    start: float
    end: float
    score: float
    speaker: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'WhisperWord':
        """Creates WhisperWord from dictionary."""
        return cls(
            word=data['word'],
            start=data['start'],
            end=data['end'],
            score=data.get('score', 1.0),
            speaker=data.get('speaker')
        )


@dataclass
class WhisperSegment:
    """Represents a transcription segment from Whisper output."""
    start: float
    end: float
    text: str
    words: List[WhisperWord]
    speaker: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'WhisperSegment':
        """Creates WhisperSegment from dictionary."""
        words = [WhisperWord.from_dict(w) for w in data.get('words', [])]
        return cls(
            start=data['start'],
            end=data['end'],
            text=data['text'],
            words=words,
            speaker=data.get('speaker')
        )

    def get_speaker(self) -> str:
        """
        Determines the speaker for this segment.

        Returns:
            str: Speaker ID (e.g. "SPEAKER_00") or "UNKNOWN_SPEAKER" as fallback
        """
        if self.speaker:
            return self.speaker
        return "UNKNOWN_SPEAKER"
