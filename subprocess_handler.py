
import subprocess
import sys
import threading
import pickle
from logger import logger

def stream_subprocess_output(process, subprocess_name: str, log_stderr_to_logger: bool = False):
    """
    Stream subprocess stderr in real-time while collecting stdout/stderr safely.
    Uses threading to avoid deadlock with pipes. Optionally mirrors captured
    stderr into the main logger for persistent logging.

    Args:
        process: subprocess.Popen object with stdout/stderr pipes
        subprocess_name: Name of subprocess for display (e.g., "Whisper", "LLM")

    Returns:
        Tuple of (stdout_data, stderr_data)
    """
    stdout_data = [b'']
    stderr_data = [b'']

    def read_stream(stream, output_list, is_stderr=False):
        """Read from a stream and store/display output."""
        if stream is None:
            return

        data = b''
        try:
            while True:
                chunk = stream.read(1024)
                if not chunk:
                    break
                data += chunk
                if is_stderr:
                    # Display stderr in real-time
                    sys.stderr.write(chunk.decode('utf-8', errors='ignore'))
                    sys.stderr.flush()
        except:
            pass
        finally:
            output_list[0] = data

    # Create threads to read stdout and stderr simultaneously
    stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, stdout_data, False))
    stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, stderr_data, True))

    stdout_thread.daemon = True
    stderr_thread.daemon = True

    stdout_thread.start()
    stderr_thread.start()

    # Wait for process to complete
    process.wait()

    # Wait for threads to finish reading
    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)

    if log_stderr_to_logger and stderr_data[0]:
        stderr_text = stderr_data[0].decode('utf-8', errors='ignore')
        for line in stderr_text.splitlines():
            stripped = line.rstrip()
            if stripped:
                logger.info("[%s subprocess] %s", subprocess_name, stripped)

    return stdout_data[0], stderr_data[0]


def run_whisper_subprocess(audio_path: str):
    """
    Run complete Whisper pipeline in isolated subprocess.
    Returns: dict with 'segments', 'word_segments', and 'language' keys

    Memory is guaranteed to be freed when subprocess exits.
    """
    logger.info("Starting Whisper subprocess...")

    # Use Popen for real-time output streaming
    process = subprocess.Popen(
        [sys.executable, "whisper_subprocess.py", str(audio_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Stream stderr in real-time while collecting stdout
    stdout_data, stderr_data = stream_subprocess_output(process, "Whisper")

    if process.returncode != 0:
        error_msg = stderr_data.decode('utf-8', errors='ignore') if stderr_data else "Unknown error"
        logger.error(f"Whisper subprocess failed: {error_msg}")
        raise RuntimeError(f"Whisper subprocess failed: {error_msg}")

    # Deserialize result
    whisper_result = pickle.loads(stdout_data)
    logger.info("Whisper subprocess completed successfully")

    return whisper_result


def run_llm_subprocess(segments):
    """
    Run LLM summarization in isolated subprocess.
    Returns: dict with language codes mapped to summary text.

    Memory is guaranteed to be freed when subprocess exits.
    """
    logger.info("Starting LLM subprocess...")

    # Serialize segments and pass via stdin
    input_data = pickle.dumps(segments)

    # Use Popen for real-time output streaming
    process = subprocess.Popen(
        [sys.executable, "llm_subprocess.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Send input data and stream stderr in real-time
    process.stdin.write(input_data)
    process.stdin.close()

    stdout_data, stderr_data = stream_subprocess_output(process, "LLM", log_stderr_to_logger=True)

    if process.returncode != 0:
        error_msg = stderr_data.decode('utf-8', errors='ignore') if stderr_data else "Unknown error"
        logger.warning(f"LLM subprocess failed: {error_msg}")
        # LLM is optional, so we return None instead of raising
        return None

    # Deserialize result - subprocess returns a tuple (summaries, trials)
    summaries, trials = pickle.loads(stdout_data)

    if trials == 1:
        logger.info("LLM subprocess succeeded on first trial with 32k context window with faster processing")
    elif trials == 2:
        logger.info("LLM subprocess succeeded on second trial with 64k context window with slower processing")

    logger.info("LLM subprocess completed successfully")

    return summaries
