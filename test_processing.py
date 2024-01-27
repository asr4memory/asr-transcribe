from post_processing import sentence_is_incomplete

class TestSentenceIsIncomplete:
    def test_no_punctuation(self):
        assert sentence_is_incomplete("Howdy, Alice")

    def test_number(self):
        """
        Do we actually need the number check?
        What does it even do?
        """
        assert sentence_is_incomplete("How do you like this number: 821")

    def test_academic_title(self):
        assert sentence_is_incomplete("Sorry, I'm not a Dr.")

    def test_normal_sentence(self):
        assert not sentence_is_incomplete("We all have to die some day.")
