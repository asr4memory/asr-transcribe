"""
Custom alignment process.
TODO: Split up large function into smaller functions.
"""
import re

# Define set of titles and abbreviations that should not be treated as sentence
# endings.
titles = {"Dr", "Prof", "Mr", "Mrs", "Ms", "Hr", "Fr", "usw", "bzw", "resp",
          "i.e", "e.g", "ca", "M. A", "M. Sc", "M. Eng", "B. A", "B. Sc"}

# Compile patterns to identify titles, dates and segments without sentence-
# ending punctuation in transcribed text.
title_pattern = re.compile(r'\b(' + '|'.join(titles) + r')[\.,:;!\?]*$', re.IGNORECASE)
num_pattern = re.compile(r'\b([1-9]|[12]\d|3[01])([.])$')
non_punct_pattern = re.compile(r'[^\.\?!]$')

def align_segments(segments):
    """
    Iterates through each transcribed segment and...
    """

    # Initialize processing variables
    custom_segs = []
    sentence_buffer = ""
    start_time = None
    end_time = None

    for i, segment in enumerate(segments):
        segment_start_time = segment["start"]
        segment_end_time = segment["end"]
        sentence = segment["text"].strip()
        # Check if sentence needs to be buffered (ends with title,
        # number, or without punctuation).
        if title_pattern.search(sentence) or num_pattern.search(sentence) or non_punct_pattern.search(sentence):
            sentence_buffer += sentence + " "
            if start_time is None:
                start_time = segment_start_time
            end_time = segment_end_time
        else:
            # Handle sentence completion or standalone sentences.
            if sentence_buffer:
                sentence_buffer += sentence
                end_time = segment_end_time
                custom_segs.append({"start": start_time, "end": end_time, "sentence": sentence_buffer.strip()})
                sentence_buffer = ""
                start_time = None
                end_time = None
            else:
                custom_segs.append({"start": segment_start_time, "end": segment_end_time, "sentence": sentence})

    # Add any remaining buffered sentence to the segments list.
    if sentence_buffer:
        custom_segs.append({"start": start_time, "end": end_time, "sentence": sentence_buffer.strip()})

    # Check if first letter of segment's sentence needs to be changed to
    # uppercase.
    for i in range(1, len(custom_segs)):
        if (custom_segs[i-1]["sentence"][-1] != ',') and (custom_segs[i]["sentence"][0].islower()):
            custom_segs[i]["sentence"] = custom_segs[i]["sentence"][0].upper() + custom_segs[i]["sentence"][1:]

    # Start of loop to check for sentences that are longer than 120 characters.
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
                split_time = seg["start"] + duration * (len(first_sentence) / len(sentence))
                # Replace the original segment with the first part and insert
                # the second part after it.
                custom_segs[i] = {"start": seg["start"], "end": split_time, "sentence": first_sentence}
                custom_segs.insert(i + 1, {"start": split_time, "end": seg["end"], "sentence": second_sentence})
        i += 1

    return custom_segs
