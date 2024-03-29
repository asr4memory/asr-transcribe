"""
Custom post-processing of whisperx segments.
Customized segments have a different structure than input (whisperx) segments.
"""
import re

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

MAX_SENTENCE_LENGTH = 120


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
                custom_segs.append({"start": start_time,
                                    "end": end_time,
                                    "text": sentence_buffer})
                sentence_buffer = ""
                start_time = None
            else:
                # Standalone sentences
                custom_segs.append({"start": segment_start_time,
                                    "end": segment_end_time,
                                    "text": sentence})

    # Add any remaining buffered sentence to the segments list.
    if sentence_buffer:
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

        if len(sentence) <= MAX_SENTENCE_LENGTH:
            yield segment
        else:
            split_index = sentence.find(",", MAX_SENTENCE_LENGTH)
            if split_index == -1:
                yield segment
            else:
                sentence_part1 = sentence[:split_index + 1].strip()
                sentence_part2 = sentence[split_index + 1:].strip()
                duration = segment["end"] - segment["start"]
                split_time = (segment["start"]
                              + duration * len(sentence_part1) / len(sentence))
                yield {"start": segment["start"],
                       "end": split_time,
                       "text": sentence_part1}
                yield {"start": split_time,
                       "end": segment["end"],
                       "text": sentence_part2}


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
