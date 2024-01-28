import copy
from post_processing import (sentence_is_incomplete, uppercase_sentences,
                             split_long_sentences)

class TestSentenceIsIncomplete:
    def test_no_punctuation(self):
        assert sentence_is_incomplete("This sentence has no punctuation")

    def test_number(self):
        """
        Do we actually need the number check?
        What does it even do?
        """
        assert sentence_is_incomplete("This sentence ends with 821")

    def test_academic_title(self):
        assert sentence_is_incomplete("This sentence ends with a Dr.")

    def test_normal_sentence(self):
        assert not sentence_is_incomplete("This is a normal sentence with punctuation.")


def test_uppercase_sentences():
    segment1 = {"sentence": "The first sentence is not affected.",
                "start": 0.0, "end": 0.0}
    segment2 = {"sentence": "the sentences after that are affected,",
                "start": 0.0, "end": 0.0}
    segment3 = {"sentence": "unless there is a comma before them.",
                "start": 0.0, "end": 0.0}
    segments = [segment1, segment2, segment3]

    expected = [copy.deepcopy(segment1),
                {"sentence": "The sentences after that are affected,",
                 "start": 0.0, "end": 0.0},
                copy.deepcopy(segment3)]

    uppercase_sentences(segments)
    assert expected == segments


def test_split_sentences():
    segment1 = {"sentence": "This sentence is way shorter than 120 characters.",
                "start": 0.0, "end": 10.0}
    segment2 = {"sentence": ("This sentence is longer than 120 characters "
                             "and it should be broken up into two sentences "
                             "after the comma appearing shortly after 120, "
                             "and so in the end we have two sentences instead "
                             "of one."),
                "start": 10.0, "end": 40.0}
    segment3 = {"sentence": "The last sentence is also below 120 characters.",
                "start": 40.0, "end": 50.0}
    original_segments = [segment1, segment2, segment3]

    segment2a = {"sentence": ("This sentence is longer than 120 characters "
                              "and it should be broken up into two sentences "
                              "after the comma appearing shortly after 120,"),
                 "start": 10.0, "end": 31.157894736842106}
    segment2b = {"sentence": ("and so in the end we have two sentences instead "
                              "of one."),
                 "start": 31.157894736842106, "end": 40.0}

    expected_segments = [segment1, segment2a, segment2b, segment3]
    actual_segments = list(split_long_sentences(original_segments))

    assert expected_segments == actual_segments
