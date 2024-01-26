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
                                    "sentence": sentence_buffer})
                sentence_buffer = ""
                start_time = None
            else:
                # Standalone sentences
                custom_segs.append({"start": segment_start_time,
                                    "end": segment_end_time,
                                    "sentence": sentence})

    # Add any remaining buffered sentence to the segments list.
    if sentence_buffer:
        custom_segs.append({"start": start_time,
                            "end": end_time,
                            "sentence": sentence_buffer.strip()})

    return custom_segs


def uppercase_sentences(custom_segs):
    """
    Turn the first letter of a sentence to uppercase if it needs to be.
    """
    for i in range(1, len(custom_segs)):
        if ((custom_segs[i-1]["sentence"][-1] != ',') and
            (custom_segs[i]["sentence"][0].islower())):
            custom_segs[i]["sentence"] = (custom_segs[i]["sentence"][0].upper() +
                                          custom_segs[i]["sentence"][1:])


def split_long_sentences(custom_segs):
    """
    Check for sentences that are longer than 120 characters
    and split them at the next comma.
    """
    i = 0
    while i < len(custom_segs):
        seg = custom_segs[i]
        sentence = seg["sentence"]
        # If sentence is longer than 120 characters, find the position of the
        # next comma after the 120th character.
        if len(sentence) > 120:
            split_point = sentence.find(',', 120)
            # If a comma is found, split the sentence at this point and trim
            # any leading/trailing whitespace.
            if split_point != -1:
                first_sentence = sentence[:split_point + 1].strip()
                second_sentence = sentence[split_point + 1:].strip()
                # Calculate duration of the segment and find the time point
                # to split the segment.
                duration = seg["end"] - seg["start"]
                split_time = (seg["start"] + duration *
                              (len(first_sentence) / len(sentence)))
                # Replace the original segment with the first part and insert
                # the second part after it.
                custom_segs[i] = {"start": seg["start"],
                                  "end": split_time,
                                  "sentence": first_sentence}
                custom_segs.insert(i + 1, {"start": split_time,
                                           "end": seg["end"],
                                           "sentence": second_sentence})
        i += 1


def process_whisperx_segments(segments):
    """
    Post-processes transcribed segments:
    Joins sentence parts that have been falsely split.
    Then splits sentences that are too long.
    """

    result = buffer_sentences(segments)
    uppercase_sentences(result)
    split_long_sentences(result)

    return result
