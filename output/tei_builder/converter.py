"""
Main converter: Whisper-JSON → TEI-XML
"""

import json
from pathlib import Path
from typing import Optional, Union, List, Dict, Set
from output.tei_builder.models import WhisperSegment
from output.tei_builder.tei_builder import TEIBuilder


class WhisperToTEIConverter:
    """Converts Whisper transcription JSON to TEI-XML."""

    def __init__(self):
        self.timeline_mapping: Dict[float, str] = {}  # timestamp -> timeline_id
        self.word_timeline_mapping: Dict[float, str] = {}  # word timestamp -> wT id
        self.speakers: Set[str] = set()

    def convert(
        self,
        input_data: dict,
        source_filename: str,
        summaries: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Converts Whisper data to TEI-XML.

        Args:
            input_data: Path to JSON file or dictionary with Whisper data

        Returns:
            str: TEI-XML as pretty-printed string
        """
        # # Extract filename for the title
        # if isinstance(input_data, (str, Path)):
        #     source_filename = Path(input_data).stem
        # else:
        #     source_filename = "Whisper Transkription"

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
            word_timeline_mapping=self.word_timeline_mapping,
            speakers=self.speakers,
            source_filename=source_filename,
            summaries=summaries,
        )

        return builder.build()

    def _parse_input(
        self, input_data: Union[str, Path, dict, list]
    ) -> List[WhisperSegment]:
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
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

        segments = [WhisperSegment.from_dict(seg) for seg in data]

        return segments

    def _build_timeline(self, segments: List[WhisperSegment]) -> List[float]:
        """
        Collects all time points from segment and word timecodes and creates
        both segment and word timeline mappings.

        Args:
            segments: List of WhisperSegments

        Returns:
            List[float]: Sorted list of unique timestamps (segment + word combined)
        """
        segment_timestamps = set()
        word_timestamps = set()

        # Always add 0.0 as start
        segment_timestamps.add(0.0)

        # Collect all segment.start timestamps
        for segment in segments:
            segment_timestamps.add(segment.start)
            # Collect all word timestamps
            for word in segment.words:
                word_timestamps.add(word.start)
                word_timestamps.add(word.end)

        # Add the end of the last segment
        if segments:
            last_segment = segments[-1]
            if last_segment.words:
                segment_timestamps.add(last_segment.words[-1].end)
            else:
                segment_timestamps.add(last_segment.end)

        # Sort segment timestamps chronologically
        sorted_segment_timestamps = sorted(segment_timestamps)

        # Create segment mapping: timestamp -> timeline_id
        # T_START for 0.0, then T0, T1, T2, ...
        for i, ts in enumerate(sorted_segment_timestamps):
            if ts == 0.0:
                self.timeline_mapping[ts] = "T_START"
            else:
                # i-1 because 0.0 is already at index 0
                self.timeline_mapping[ts] = f"T{i - 1}"

        # Create word mapping: timestamp -> wT id
        # Word timestamps sorted and numbered independently
        sorted_word_timestamps = sorted(word_timestamps)
        for i, ts in enumerate(sorted_word_timestamps):
            self.word_timeline_mapping[ts] = f"wT{i}"

        # Combine all timestamps for the full timeline
        all_timestamps = segment_timestamps | word_timestamps
        return sorted(all_timestamps)

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
