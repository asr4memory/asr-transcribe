from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-asr-transcribe",
    version="1.0.0",
    description="CLI harness for the asr-transcribe audio transcription pipeline",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-asr-transcribe=cli_anything.asr_transcribe.asr_transcribe_cli:main",
        ],
    },
    python_requires=">=3.10",
    include_package_data=True,
)
