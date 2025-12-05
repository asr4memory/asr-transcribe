"""
Main converter: Whisper-JSON → TEI-XML
"""

import json
from pathlib import Path
from typing import Union, List, Dict, Set
from tei_builder.models import WhisperSegment
from tei_builder.tei_builder import TEIBuilder


class WhisperToTEIConverter:
    """Converts Whisper transcription JSON to TEI-XML."""

    def __init__(self):
        self.timeline_mapping: Dict[float, str] = {}  # timestamp -> timeline_id
        self.speakers: Set[str] = set()

    def convert(self, input_data: Union[str, Path, dict]) -> str:
        """
        Converts Whisper data to TEI-XML.

        Args:
            input_data: Path to JSON file or dictionary with Whisper data

        Returns:
            str: TEI-XML as pretty-printed string
        """
        # Extract filename for the title
        if isinstance(input_data, (str, Path)):
            source_filename = Path(input_data).stem
        else:
            source_filename = "Whisper Transkription"

        # Parse Input
        segments = self._parse_input(input_data)

        # Collect timeline points and speakers
        timeline_points = self._build_timeline(segments)
        self._collect_speakers(segments)

        # Generate TEI-XML
        builder = TEIBuilder(
            segments=segments,
            timeline_points=timeline_points,
            timeline_mapping=self.timeline_mapping,
            speakers=self.speakers,
            source_filename=source_filename
        )

        return builder.build()

    def _parse_input(self, input_data: Union[str, Path, dict, list]) -> List[WhisperSegment]:
        """
        Reads and parses Whisper JSON data.

        Args:
            input_data: Path to JSON file, dictionary, or list of segments

        Returns:
            List[WhisperSegment]: List of segments
        """
        if isinstance(input_data, (list)):
            data = input_data
        else:
            # Treat as path
            path = Path(input_data)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

        segments = [WhisperSegment.from_dict(seg) for seg in data]

        return segments

    def _build_timeline(self, segments: List[WhisperSegment]) -> List[float]:
        """
        Collects all time points from word timecodes and creates timeline mapping.

        Args:
            segments: List of WhisperSegments

        Returns:
            List[float]: Sorted list of unique timestamps
        """
        timestamps = set()

        # Always add 0.0 as start
        timestamps.add(0.0)

        # Collect all segment.start timestamps
        for segment in segments:
            timestamps.add(segment.start)

        # Add the end of the last segment
        if segments:
            last_segment = segments[-1]
            if last_segment.words:
                timestamps.add(last_segment.words[-1].end)
            else:
                timestamps.add(last_segment.end)

        # Sort chronologically
        sorted_timestamps = sorted(timestamps)

        # Create mapping: timestamp -> timeline_id
        # T_START for 0.0, then T0, T1, T2, ...
        for i, ts in enumerate(sorted_timestamps):
            if ts == 0.0:
                self.timeline_mapping[ts] = "T_START"
            else:
                # i-1 because 0.0 is already at index 0
                self.timeline_mapping[ts] = f"T{i-1}"

        return sorted_timestamps

    def _collect_speakers(self, segments: List[WhisperSegment]) -> None:
        """
        Collects all unique speakers from the segments.

        Args:
            segments: List of WhisperSegments
        """
        for segment in segments:
            speaker = segment.get_speaker()
            self.speakers.add(speaker)

    def get_timeline_id(self, timestamp: float) -> str:
        """
        Returns the timeline ID for a given timestamp.

        Args:
            timestamp: Timestamp in seconds

        Returns:
            str: Timeline ID (e.g. "T1", "T_START")
        """
        return self.timeline_mapping.get(timestamp, "T_START")

    @staticmethod
    def speaker_to_person_id(speaker: str) -> str:
        """
        Converts speaker ID to person ID for TEI.

        Args:
            speaker: Speaker ID (e.g. "SPEAKER_00")

        Returns:
            str: Person ID (e.g. "p_SPEAKER_00")
        """
        return f"p_{speaker}"
