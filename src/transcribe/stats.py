from .utilities import format_duration

class ProcessInfo:
    """
    Stores information about the transcription process.
    """
    def __init__(self, filename, start = 0, end = 0):
        self.filename = filename

    def process_duration(self):
        "Return process duration in seconds."
        delta = self.end - self.start
        return delta.total_seconds()

    def formatted_process_duration(self):
        "Returns formatted process duration."
        seconds = self.process_duration()
        formatted_time = format_duration(seconds)
        formatted_seconds = "{:.1f}s".format(seconds)
        return f"{formatted_time} ({formatted_seconds})"

    def formatted_audio_length(self):
        "Returns formatted length of audio file."
        formatted_time = format_duration(self.audio_length)
        formatted_seconds = "{:.1f}s".format(self.audio_length)
        return f"{formatted_time} ({formatted_seconds})"

    def realtime_factor(self):
        """
        Calculate the real time factor for processing an audio file,
        i.e. the ratio of process duration and audio length.
        """
        return self.process_duration() / self.audio_length

    def __str__(self):
        "Return process string representation."
        return f"ProcessInfo<{self.filename}: {self.process_duration()}>"
