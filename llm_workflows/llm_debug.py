from subprocess_handler import run_llm_subprocess
from app_config import get_config
from asr_workflow import get_llm_languages

config = get_config()
use_llms = config["llm"]["use_llms"]
