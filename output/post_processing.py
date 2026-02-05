"""
Custom post-processing of whisperx segments.
Customized segments have a different structure than input (whisperx) segments.
"""

import re
from config.app_config import get_config

# Define set of titles and abbreviations that should not be treated as
# sentence endings.

TITLES = {
    # -------------------------------
    # German Titles and Abbreviations
    # -------------------------------
    "Dr",  # Doktor
    "Prof",  # Professor
    "Hr",  # Herr
    "Fr",  # Frau
    "Dipl.-Ing",  # Diplom-Ingenieur
    "Mag",  # Magister
    "Lic",  # Lizentiat
    "Dr.-Ing",  # Doktor-Ingenieur
    "Dr. med",  # Doktor der Medizin
    "Dr. rer. nat",  # Doktor der Naturwissenschaften
    "Dr. phil",  # Doktor der Philosophie
    "Dr. h.c",  # Ehren-Doktor
    "Prof. Dr",  # Professor Doktor
    # Common German abbreviations
    "usw",  # und so weiter (etc.)
    "bzw",  # beziehungsweise (respectively)
    "resp",  # respektive (respectively)
    "ca",  # circa (approximately)
    "z. B",  # zum Beispiel (for example)
    "z.B.",  # zum Beispiel (for example)
    "d. h",  # das heißt (that means)
    "d.h.",  # das heißt (that means)
    "u. a",  # unter anderem (among others)
    "u.a.",  # unter anderem (among others)
    "u. ä",  # und ähnliche (and similar)
    "u.Ä.",  # und ähnliche (and similar)
    "ggf",  # gegebenenfalls (if applicable)
    "vgl",  # vergleiche (see, compare)
    "Abb",  # Abbildung (figure)
    "Nr",  # Nummer (number)
    "evtl",  # eventuell (possibly)
    "etc",  # et cetera
    "inkl",  # inklusive (including)
    "zzgl",  # zuzüglich (plus, in addition)
    "o. Ä",  # oder Ähnliches (or similar)
    "o.Ä.",  # oder Ähnliches (or similar)
    "Mio",  # Million
    "Mrd",  # Milliarde (billion)
    "Tel",  # Telefon (telephone)
    "Fax",  # Fax (facsimile)
    "Str",  # Straße (street)
    "Hnr",  # Hausnummer (house number)
    "Bd",  # Band (volume)
    # -------------------------------
    # English Titles and Abbreviations
    # -------------------------------
    "Mr",  # Mister
    "Mrs",  # Mistress
    "Ms",  # Miss
    "Jr",  # Junior
    "Sr",  # Senior
    "M.A",  # Master of Arts
    "M.Sc",  # Master of Science
    "M.Eng",  # Master of Engineering
    "B.A",  # Bachelor of Arts
    "B.Sc",  # Bachelor of Science
    "Ph.D",  # Doctor of Philosophy
    # Address and place abbreviations
    "St",  # Saint or Street
    "Mt",  # Mount
    "Ft",  # Fort or Featuring
    "Rd",  # Road
    "Blvd",  # Boulevard
    "Ave",  # Avenue
    "Sq",  # Square
    "Ln",  # Lane
    "Dr",  # Drive (also Doctor — context-sensitive)
    "Pl",  # Place
    "Ste",  # Suite
    "Apt",  # Apartment
    "Fl",  # Floor
    # Company-related abbreviations
    "Inc",  # Incorporated
    "Ltd",  # Limited
    "Co",  # Company
    "Corp",  # Corporation
    # Common English abbreviations
    "i.e",  # that is
    "e.g",  # for example
    "etc",  # et cetera
    "cf",  # confer (compare)
    "vs",  # versus
}

# Compile patterns to identify titles, dates and segments without sentence-
# ending punctuation in transcribed text.
ENDS_WITH_TITLE = re.compile(
    r"\b(" + "|".join(TITLES) + r")[\.,:;!\?]*$", re.IGNORECASE
)
ENDS_WITH_NUMBER = re.compile(r"\b([1-9]|[12]\d|3[01])([.])$")
ENDS_WITHOUT_PUNCTUATION = re.compile(r"[^\.\?!]$")


def sentence_is_incomplete(sentence: str):
    """
    Check if sentence needs to be buffered (ends with academic title,
    number, or without punctuation).
    """
    return (
        ENDS_WITH_TITLE.search(sentence)
        or ENDS_WITH_NUMBER.search(sentence)
        or ENDS_WITHOUT_PUNCTUATION.search(sentence)
    )


def sentence_is_complete(sentence: str):
    return not sentence_is_incomplete(sentence)


def buffer_sentences(segments, use_speaker_diarization=False):
    """
    Join sentences that have been falsely split (e.g. after academic titles,
    numbers).
    """
    custom_segs = []
    sentence_buffer = ""
    start_time = None
    end_time = None
    words_buffer = []

    for segment in segments:
        segment_start_time = segment["start"]
        segment_end_time = segment["end"]
        if use_speaker_diarization:
            segment_speaker = segment.get("speaker", "SPEAKER_XX")
        sentence = segment["text"].strip()
        segment_words = segment.get("words", [])

        if sentence_is_incomplete(sentence):
            sentence_buffer += sentence + " "
            words_buffer.extend(segment_words)
            if start_time is None:
                start_time = segment_start_time
            end_time = segment_end_time
        else:
            # Handle sentence completion or standalone sentences.
            if sentence_buffer:
                # Sentence completion
                sentence_buffer += sentence
                words_buffer.extend(segment_words)
                end_time = segment_end_time
                if use_speaker_diarization:
                    custom_segs.append(
                        {
                            "start": start_time,
                            "end": end_time,
                            "text": sentence_buffer,
                            "speaker": segment_speaker,
                            "words": words_buffer,
                        }
                    )
                else:
                    custom_segs.append(
                        {
                            "start": start_time,
                            "end": end_time,
                            "text": sentence_buffer,
                            "words": words_buffer,
                        }
                    )
                sentence_buffer = ""
                words_buffer = []
                start_time = None
            else:
                # Standalone sentences
                if use_speaker_diarization:
                    custom_segs.append(
                        {
                            "start": segment_start_time,
                            "end": segment_end_time,
                            "text": sentence,
                            "speaker": segment_speaker,
                            "words": segment_words,
                        }
                    )
                else:
                    custom_segs.append(
                        {
                            "start": segment_start_time,
                            "end": segment_end_time,
                            "text": sentence,
                            "words": segment_words,
                        }
                    )

    # Add any remaining buffered sentence to the segments list.
    if sentence_buffer:
        if use_speaker_diarization:
            custom_segs.append(
                {
                    "start": start_time,
                    "end": end_time,
                    "text": sentence_buffer.strip(),
                    "speaker": segment_speaker,
                    "words": words_buffer,
                }
            )
        else:
            custom_segs.append(
                {
                    "start": start_time,
                    "end": end_time,
                    "text": sentence_buffer.strip(),
                    "words": words_buffer,
                }
            )

    return custom_segs


def uppercase_sentences(custom_segs):
    """
    Turn the first letter of a sentence to uppercase if it needs to be.
    """
    for i in range(1, len(custom_segs)):
        if (custom_segs[i - 1]["text"][-1] != ",") and (
            custom_segs[i]["text"][0].islower()
        ):
            custom_segs[i]["text"] = (
                custom_segs[i]["text"][0].upper() + custom_segs[i]["text"][1:]
            )


def split_long_sentences(
    segments, use_speaker_diarization=False, max_sentence_length=120
):
    """
    Splits a long segment into two if it has a comma.
    If a segment text is longer than 120 characters, and has a comma
    after the 120th character, break it into two segments at the comma
    position.
    The end time of the first segment, that is, the start time of the
    second segment, are estimated based on the len of the two sentence
    parts.
    max_sentence_length: normally injected from config; default is fallback only.
    """
    for segment in segments:
        sentence = segment["text"]
        segment_words = segment.get("words", [])
        if use_speaker_diarization:
            segment_speaker = segment["speaker"]

        if len(sentence) <= max_sentence_length:
            yield segment
            continue

        current_sentence = sentence
        current_words = segment_words
        current_start = segment["start"]
        current_end = segment["end"]

        while True:
            if len(current_sentence) <= max_sentence_length:
                if use_speaker_diarization:
                    yield {
                        "start": current_start,
                        "end": current_end,
                        "text": current_sentence,
                        "speaker": segment_speaker,
                        "words": current_words,
                    }
                else:
                    yield {
                        "start": current_start,
                        "end": current_end,
                        "text": current_sentence,
                        "words": current_words,
                    }
                break

            split_index = current_sentence.find(",", max_sentence_length)
            if split_index == -1:
                if use_speaker_diarization:
                    yield {
                        "start": current_start,
                        "end": current_end,
                        "text": current_sentence,
                        "speaker": segment_speaker,
                        "words": current_words,
                    }
                else:
                    yield {
                        "start": current_start,
                        "end": current_end,
                        "text": current_sentence,
                        "words": current_words,
                    }
                break

            sentence_part1 = current_sentence[: split_index + 1].strip()
            sentence_part2 = current_sentence[split_index + 1 :].strip()
            duration = current_end - current_start
            split_time = current_start + duration * len(sentence_part1) / len(
                current_sentence
            )

            # Split words basierend auf Anzahl der Wörter im Text
            words_count_part1 = len(sentence_part1.split())
            words_part1 = current_words[:words_count_part1]
            words_part2 = current_words[words_count_part1:]

            if use_speaker_diarization:
                yield {
                    "start": current_start,
                    "end": split_time,
                    "text": sentence_part1,
                    "speaker": segment_speaker,
                    "words": words_part1,
                }
            else:
                yield {
                    "start": current_start,
                    "end": split_time,
                    "text": sentence_part1,
                    "words": words_part1,
                }

            current_start = split_time
            current_sentence = sentence_part2
            current_words = words_part2


def process_whisperx_segments(segments):
    """
    Post-processes transcribed segments:
    Joins sentence parts that have been falsely split.
    Then splits sentences that are too long.
    """
    config = get_config()
    max_sentence_length = config["whisper"]["max_sentence_length"]
    use_speaker_diarization = config["whisper"]["use_speaker_diarization"]

    processed_segments = buffer_sentences(
        segments, use_speaker_diarization=use_speaker_diarization
    )
    uppercase_sentences(processed_segments)
    processed_segments = list(
        split_long_sentences(
            processed_segments,
            use_speaker_diarization=use_speaker_diarization,
            max_sentence_length=max_sentence_length,
        )
    )
    # Sammle alle word_segments aus den prozessierten Segmenten
    processed_word_segments = []
    for segment in processed_segments:
        processed_word_segments.extend(segment.get("words", []))

    # Erstelle Output-Struktur mit beiden: segments und word_segments
    result = {"segments": processed_segments, "word_segments": processed_word_segments}

    return result
