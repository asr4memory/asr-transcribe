import sys
import io
import logging
import colorlog

DATE_FORMAT = datefmt="%Y-%m-%dT%H:%M:%S%z"

logger = logging.getLogger('asr-transcribe')

fmt = logging.Formatter(
    fmt="%(asctime)s | %(levelname)s | %(message)s",
    datefmt=DATE_FORMAT,
)

fmt_col = colorlog.ColoredFormatter(
    "%(blue)s%(asctime)s%(reset)s | %(log_color)s%(levelname)s%(reset)s | %(log_color)s%(message)s%(reset)s",
    datefmt=DATE_FORMAT,
)

stdoutHandler = colorlog.StreamHandler(stream=sys.stdout)
stdoutHandler.setLevel(logging.DEBUG)
stdoutHandler.setFormatter(fmt_col)

memory_stream = io.StringIO()
memoryHandler = logging.StreamHandler(stream=memory_stream)
memoryHandler.setLevel(logging.INFO)
memoryHandler.setFormatter(fmt)

filehandler = logging.FileHandler('asr-transcribe.log')
filehandler.setLevel(logging.INFO)
filehandler.setFormatter(fmt)

logger.addHandler(stdoutHandler)
logger.addHandler(memoryHandler)
logger.addHandler(filehandler)
logger.setLevel(logging.DEBUG)
