"""
TEI-XML Builder with lxml
"""

import re
from typing import List, Dict, Set, Tuple, Optional
from lxml import etree
from tei_builder.models import WhisperSegment


class TEIBuilder:
    """Builds TEI-XML structure with lxml."""

    NSMAP = {
        None: "http://www.tei-c.org/ns/1.0",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }
    # Regex for punctuation at the end of a word
    PUNCTUATION_PATTERN = re.compile(r"^(.+?)([.,;:!?]+)$")
    # Minimum pause duration in seconds to be marked as <pause>
    PAUSE_THRESHOLD = 2.0

    def __init__(
        self,
        segments: List[WhisperSegment],
        timeline_points: List[float],
        timeline_mapping: Dict[float, str],
        speakers: Set[str],
        source_filename: str = "Whisper Transkription",
    ):
        """
        Initializes the TEI-Builder.

        Args:
            segments: List of WhisperSegments
            timeline_points: Sorted list of timestamps
            timeline_mapping: Dictionary timestamp -> timeline_id
            speakers: Set of speaker IDs
            source_filename: Name of the source file for the title
        """
        self.segments = segments
        self.timeline_points = timeline_points
        self.timeline_mapping = timeline_mapping
        self.speakers = speakers
        self.source_filename = source_filename
        self.annotation_counter = 0
        self.utterance_counter = 0
        self.segment_counter = 0

    def build(self) -> str:
        """
        Builds the complete TEI-XML document.

        Returns:
            str: Pretty-printed XML String
        """
        # Root Element
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI", nsmap=self.NSMAP)
        root.set(
            "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
            "http://www.tei-c.org/ns/1.0 http://www.tei-c.org/release/xml/tei/custom/schema/xsd/tei_all.xsd",
        )

        # Header
        header = self._build_header()
        root.append(header)

        # Text
        text_elem = etree.SubElement(root, "text")
        text_elem.set("{http://www.w3.org/XML/1998/namespace}lang", "de")

        # Timeline
        timeline = self._build_timeline()
        text_elem.append(timeline)

        # Body
        body = etree.SubElement(text_elem, "body")
        for segment in self.segments:
            ab = self._build_annotation_block(segment)
            body.append(ab)

        # To String
        xml_bytes = etree.tostring(
            root, encoding="utf-8", pretty_print=True, xml_declaration=True
        )

        return xml_bytes.decode("utf-8")

    def _build_header(self) -> etree.Element:
        """
        Builds the minimal TEI header.

        Returns:
            etree.Element: teiHeader Element
        """
        header = etree.Element("teiHeader")

        # fileDesc
        file_desc = etree.SubElement(header, "fileDesc")

        # titleStmt
        title_stmt = etree.SubElement(file_desc, "titleStmt")
        title = etree.SubElement(title_stmt, "title")
        title.text = self.source_filename

        # publicationStmt
        pub_stmt = etree.SubElement(file_desc, "publicationStmt")
        p = etree.SubElement(pub_stmt, "p")
        p.text = "Unpublished"

        # sourceDesc
        source_desc = etree.SubElement(file_desc, "sourceDesc")
        p = etree.SubElement(source_desc, "p")
        p.text = "ASR4Memory - Automatic Transcription of Audiovisual Research Data"

        # profileDesc
        profile_desc = etree.SubElement(header, "profileDesc")
        partic_desc = etree.SubElement(profile_desc, "particDesc")

        # Speakers
        for speaker in sorted(self.speakers):
            person = etree.SubElement(partic_desc, "person")
            person.set("{http://www.w3.org/XML/1998/namespace}id", f"p_{speaker}")

        return header

    @staticmethod
    def _split_word_punctuation(word_text: str) -> Tuple[str, Optional[str]]:
        """
        Separates a word from trailing punctuation.

        Args:
            word_text: The word (possibly with punctuation)

        Returns:
            Tuple: (Word without punctuation, punctuation or None)
        """
        match = TEIBuilder.PUNCTUATION_PATTERN.match(word_text)
        if match:
            return match.group(1), match.group(2)
        return word_text, None

    def _build_timeline(self) -> etree.Element:
        """
        Builds the timeline with when elements.

        Returns:
            etree.Element: timeline Element
        """
        timeline = etree.Element("timeline")
        timeline.set("unit", "s")

        for timestamp in self.timeline_points:
            when = etree.SubElement(timeline, "when")
            timeline_id = self.timeline_mapping[timestamp]
            when.set("{http://www.w3.org/XML/1998/namespace}id", timeline_id)
            when.set("interval", f"{timestamp:.3f}")
            when.set("since", "T_START")

        return timeline

    def _build_annotation_block(self, segment: WhisperSegment) -> etree.Element:
        """
        Builds an AnnotationBlock for a segment.

        Args:
            segment: WhisperSegment

        Returns:
            etree.Element: annotationBlock Element
        """
        self.annotation_counter += 1
        self.utterance_counter += 1
        self.segment_counter += 1

        ab_id = f"ab{self.annotation_counter}"
        u_id = f"u{self.utterance_counter}"
        seg_id = f"s{self.segment_counter}"

        # Determine Start/End Timeline-IDs based on segment.start
        # Start = current segment, End = next segment
        current_index = self.segments.index(segment)
        start_timestamp = segment.start
        start_timeline_id = self.timeline_mapping.get(start_timestamp, "T0")

        # End = Start of next segment (if available)
        if current_index < len(self.segments) - 1:
            next_segment = self.segments[current_index + 1]
            end_timestamp = next_segment.start
            end_timeline_id = self.timeline_mapping.get(end_timestamp, "T0")
        else:
            # Last segment: use the end from timeline_points
            if len(self.timeline_points) > current_index + 1:
                end_timestamp = self.timeline_points[current_index + 1]
                end_timeline_id = self.timeline_mapping.get(
                    end_timestamp, f"T{len(self.timeline_points) - 1}"
                )
            else:
                end_timeline_id = start_timeline_id

        # annotationBlock
        ab = etree.Element("annotationBlock")
        ab.set("{http://www.w3.org/XML/1998/namespace}id", ab_id)
        ab.set("who", f"p_{segment.get_speaker()}")
        ab.set("start", start_timeline_id)
        ab.set("end", end_timeline_id)

        # u (utterance)
        u = etree.SubElement(ab, "u")
        u.set("{http://www.w3.org/XML/1998/namespace}id", u_id)

        # seg (segment)
        seg = etree.SubElement(u, "seg")
        seg.set("type", "contribution")
        seg.set("{http://www.w3.org/XML/1998/namespace}id", seg_id)
        seg.set("{http://www.w3.org/XML/1998/namespace}lang", "ger")

        # Start anchor
        anchor_start = etree.SubElement(seg, "anchor")
        anchor_start.set("synch", start_timeline_id)

        # Words - Tokenize words and punctuation
        token_index = 0
        prev_word_end = None

        for word in segment.words:
            # Check for pause before this word
            if prev_word_end is not None:
                pause_duration = word.start - prev_word_end
                if pause_duration >= self.PAUSE_THRESHOLD:
                    pause_elem = etree.SubElement(seg, "pause")
                    pause_elem.set(
                        "{http://www.w3.org/XML/1998/namespace}id",
                        f"{seg_id}_{token_index}",
                    )
                    pause_elem.set("dur", f"PT{pause_duration:.3f}S")
                    token_index += 1

            word_text, punctuation = self._split_word_punctuation(word.word.strip())

            # Word as <w> element
            if word_text:
                w = etree.SubElement(seg, "w")
                w.set(
                    "{http://www.w3.org/XML/1998/namespace}id",
                    f"{seg_id}_{token_index}",
                )
                w.text = word_text
                token_index += 1

            # Punctuation as <pc> element
            if punctuation:
                pc = etree.SubElement(seg, "pc")
                pc.set(
                    "{http://www.w3.org/XML/1998/namespace}id",
                    f"{seg_id}_{token_index}",
                )
                pc.text = punctuation
                token_index += 1

            prev_word_end = word.end

        # End anchor
        anchor_end = etree.SubElement(seg, "anchor")
        anchor_end.set("synch", end_timeline_id)

        # spanGrp original
        span_grp = etree.SubElement(ab, "spanGrp")
        span_grp.set("type", "original")
        span = etree.SubElement(span_grp, "span")
        span.set("from", start_timeline_id)
        span.set("to", end_timeline_id)
        span.text = segment.text

        return ab
