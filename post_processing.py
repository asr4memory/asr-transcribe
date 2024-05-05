"""
Custom post-processing of whisperx segments.
Customized segments have a different structure than input (whisperx) segments.
"""
import re
from app_config import get_config

config = get_config()

# Define set of titles and abbreviations that should not be treated as
# sentence endings.
titles = {"Dr", "Prof", "Mr", "Mrs", "Ms", "Hr", "Fr", "usw", "bzw", "resp",
          "i.e", "e.g", "ca", "M. A", "M. Sc", "M. Eng", "B. A", "B. Sc"}

# Compile patterns to identify titles, dates and segments without sentence-
# ending punctuation in transcribed text.
ENDS_WITH_TITLE = re.compile(r'\b(' + '|'.join(titles) + r')[\.,:;!\?]*$',
                             re.IGNORECASE)
ENDS_WITH_NUMBER = re.compile(r'\b([1-9]|[12]\d|3[01])([.])$')
ENDS_WITHOUT_PUNCTUATION = re.compile(r'[^\.\?!]$')

max_sentence_length = config['whisper']['max_sentence_length']
use_speaker_diarization = config['whisper']['use_speaker_diarization']


def sentence_is_incomplete(sentence: str):
    """
    Check if sentence needs to be buffered (ends with academic title,
    number, or without punctuation).
    """
    return (ENDS_WITH_TITLE.search(sentence) or
            ENDS_WITH_NUMBER.search(sentence) or
            ENDS_WITHOUT_PUNCTUATION.search(sentence))


def sentence_is_complete(sentence: str):
    return not sentence_is_incomplete(sentence)


def buffer_sentences(segments):
    """
    Join sentences that have been falsely split (e.g. after academic titles,
    numbers).
    """
    custom_segs = []
    sentence_buffer = ""
    start_time = None
    end_time = None

    for segment in segments:
        segment_start_time = segment["start"]
        segment_end_time = segment["end"]
        if use_speaker_diarization:
            segment_speaker = segment.get("speaker", "SPEAKER_XX")
        sentence = segment["text"].strip()

        if sentence_is_incomplete(sentence):
            sentence_buffer += sentence + " "
            if start_time is None:
                start_time = segment_start_time
            end_time = segment_end_time
        else:
            # Handle sentence completion or standalone sentences.
            if sentence_buffer:
                # Sentence completion
                sentence_buffer += sentence
                end_time = segment_end_time
                if use_speaker_diarization:
                     custom_segs.append({"start": start_time,
                                        "end": end_time,
                                        "text": sentence_buffer,
                                        "speaker": segment_speaker})
                else:
                    custom_segs.append({"start": start_time,
                                        "end": end_time,
                                        "text": sentence_buffer})
                sentence_buffer = ""
                start_time = None
            else:
                # Standalone sentences
                if use_speaker_diarization:
                    custom_segs.append({"start": segment_start_time,
                                        "end": segment_end_time,
                                        "text": sentence,
                                        "speaker": segment_speaker})
                else:
                    custom_segs.append({"start": segment_start_time,
                                        "end": segment_end_time,
                                        "text": sentence})

    # Add any remaining buffered sentence to the segments list.
    if sentence_buffer:
        if use_speaker_diarization:
            custom_segs.append({"start": start_time,
                                "end": end_time,
                                "text": sentence_buffer.strip(),
                                "speaker": segment_speaker})
        else:
            custom_segs.append({"start": start_time,
                                "end": end_time,
                                "text": sentence_buffer.strip()})

    return custom_segs


def uppercase_sentences(custom_segs):
    """
    Turn the first letter of a sentence to uppercase if it needs to be.
    """
    for i in range(1, len(custom_segs)):
        if ((custom_segs[i-1]["text"][-1] != ',') and
            (custom_segs[i]["text"][0].islower())):
            custom_segs[i]["text"] = (custom_segs[i]["text"][0].upper() +
                                      custom_segs[i]["text"][1:])


def split_long_sentences(segments):
    """
    Splits a long segment into two if it has a comma.
    If a segment text is longer than 120 characters, and has a comma
    after the 120th character, break it into two segments at the comma
    position.
    The end time of the first segment, that is, the start time of the
    second segment, are estimated based on the len of the two sentence
    parts.
    """
    for segment in segments:
        sentence = segment["text"]
        if use_speaker_diarization: segment_speaker = segment["speaker"]

        if len(sentence) <= max_sentence_length:
            yield segment
        else:
            split_index = sentence.find(",", max_sentence_length)
            if split_index == -1:
                yield segment
            else:
                sentence_part1 = sentence[:split_index + 1].strip()
                sentence_part2 = sentence[split_index + 1:].strip()
                duration = segment["end"] - segment["start"]
                split_time = (segment["start"]
                              + duration * len(sentence_part1) / len(sentence))
                if use_speaker_diarization:
                    yield {"start": segment["start"],
                           "end": split_time,
                           "text": sentence_part1,
                           "speaker": segment_speaker}
                    yield {"start": split_time,
                           "end": segment["end"],
                           "text": sentence_part2,
                           "speaker": segment_speaker}
                else:
                    yield {"start": segment["start"],
                           "end": split_time,
                           "text": sentence_part1}
                    yield {"start": split_time,
                           "end": segment["end"],
                           "text": sentence_part2}


def process_whisperx_word_segments(word_segments):
    """
    Fills missing word timecodes by calculating the distance between
    last known end timecode and next occuring start timecode and
    splitting it into multiple timecodes of equal length.
    """
    nan_indices = [i for i, item in enumerate(word_segments)
                   if 'start' not in item or 'end' not in item]

    for idx in nan_indices:
        prev_known_end_idx = max(
            [i for i in range(idx) if 'end' in word_segments[i]],
            default=-1
        )
        next_known_start_idx = min(
            [i for i in range(idx + 1, len(word_segments)) if 'start' in word_segments[i]],
            default=len(word_segments)
        )

        if prev_known_end_idx == -1:
            prev_end_time = 0
        else:
            prev_end_time = word_segments[prev_known_end_idx]['end']
        if next_known_start_idx == len(word_segments):
            next_start_time = prev_end_time + 1
        else:
            next_start_time = word_segments[next_known_start_idx]['start']

        distance = next_start_time - prev_end_time
        gaps = next_known_start_idx - prev_known_end_idx - 1
        increment = distance / (gaps * 2 + 1)

        for i in range(1, gaps + 1):
            word_segments[prev_known_end_idx + i]['start'] = prev_end_time + increment * i
            word_segments[prev_known_end_idx + i]['end'] = prev_end_time + increment * i * 2

    return word_segments


def process_whisperx_segments(segments):
    """
    Post-processes transcribed segments:
    Joins sentence parts that have been falsely split.
    Then splits sentences that are too long.
    """

    result = buffer_sentences(segments)
    uppercase_sentences(result)
    result = list(split_long_sentences(result))

    return result
