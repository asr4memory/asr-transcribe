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

    @classmethod
    def from_dict(cls, data: dict) -> 'WhisperSegment':
        """Creates WhisperSegment from dictionary."""
        words = [WhisperWord.from_dict(w) for w in data.get('words', [])]
        return cls(
            start=data['start'],
            end=data['end'],
            text=data['text'],
            words=words
        )

    def get_speaker(self) -> str:
        """
        Determines the speaker for this segment.

        Returns:
            str: Speaker ID (e.g. "SPEAKER_00") or "SPEAKER_00" as fallback
        """
        if self.words and self.words[0].speaker:
            return self.words[0].speaker
        return "SPEAKER_00"
