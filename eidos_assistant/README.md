# Eidos Assistant

Eidos Assistant is a conversational AI assistant designed to be extensible and run locally. This project is being developed iteratively.

## Prerequisites

*   Python (version 3.8+ recommended)
*   Pip (Python package installer)
*   Access to a local Large Language Model (LLM) server that is compatible with the OpenAI API.
*   For Text-to-Speech (TTS) functionality with the `/say` command, a running instance of a Kokoro-FastAPI compatible server is needed.
*   **For Speech-to-Text (STT) functionality (`/listen` command):**
    *   The `openai-whisper` Python library (which includes `torch`). You can typically install this via `pip install openai-whisper`.
    *   `ffmpeg` installed on your system and available in your PATH. (e.g., `sudo apt install ffmpeg` on Debian/Ubuntu, or download from ffmpeg.org for other OS).

## Installation

1.  Clone this repository.
2.  Install required Python packages:
    ```bash
    # pip install -r requirements.txt
    # (requirements.txt will be added in a future step)
    # For now, manually ensure the following are installed if not handled by subtasks:
    # pip install PyYAML openai python-dotenv openai-whisper
    ```

## Configuration via .env File

Eidos Assistant uses a `.env` file in the project root (`eidos_assistant/`) to manage configurations for external services. Create this file if it doesn't exist.

Example `.env` content:

```env
# .env - Environment variables for Eidos Assistant

# LLM Configuration (OpenAI compatible API)
LLM_API_BASE_URL="http://localhost:11434/v1"
LLM_API_KEY="NotNeededForOllama" # Or your actual API key if required

# Kokoro TTS Server Configuration (OpenAI compatible API via remsky/Kokoro-FastAPI)
KOKORO_TTS_BASE_URL="http://localhost:8880/v1"
KOKORO_TTS_API_KEY="not-needed" # Or your actual API key if required
KOKORO_TTS_VOICE="af_sky"
# Example voices: "af_sky+af_bella" (blended), "af_bella(2)+af_heart(1)" (weighted)
```

**Key Environment Variables:**

*   `LLM_API_BASE_URL`: The base URL for your OpenAI API compatible LLM server.
*   `LLM_API_KEY`: The API key for your LLM server (if required).
*   `KOKORO_TTS_BASE_URL`: The base URL for your Kokoro-FastAPI TTS server.
*   `KOKORO_TTS_API_KEY`: The API key for your TTS server (if required, typically "not-needed" for local Kokoro-FastAPI).
*   `KOKORO_TTS_VOICE`: The default voice to be used for TTS. Consult your Kokoro-FastAPI documentation for available voices.

The application will attempt to load these variables. If `.env` is not found or a variable is missing, fallback default values will be used (which also point to common local server addresses).
Make sure your `.env` file is added to your `.gitignore` to avoid committing sensitive information.

## Running the Assistant

Currently, the assistant runs via a command-line interface:

```bash
python eidos_assistant/main.py
```

**Important for Conversational AI & TTS:**

To enable full conversational capabilities, you need a local LLM server running that is compatible with the OpenAI API (e.g., Ollama, LM Studio, VLLM).
For the `/say` command to work, a Kokoro-FastAPI compatible TTS server must be running and accessible at the configured `KOKORO_TTS_BASE_URL`.

The assistant is configured by default to attempt to connect to an LLM at `http://localhost:11434/v1` and TTS at `http://localhost:8880/v1`. If your servers are running on different addresses or ports, update your `.env` file or modify the default values in the code.

Ensure your servers are running *before* starting the Eidos Assistant. If the assistant cannot connect, it will indicate an error or relevant commands may fail.

**Important Note on Speech-to-Text (STT):**

The Speech-to-Text (STT) functionality (e.g., the `/listen` command) using Whisper has been implemented in the codebase but **could not be tested by the AI assistant developer due to limitations in the development sandbox environment** (specifically, issues installing large dependencies like `torch` which is part of `openai-whisper`).

Users wishing to use STT must:
1.  Ensure `openai-whisper` is installed in their Python environment (`pip install openai-whisper`).
2.  Ensure `ffmpeg` is installed on their system and accessible in the PATH.
3.  Verify that Whisper can download its models (e.g., `base.en`) which requires an internet connection on first run.

The successful operation of STT features is contingent upon the user's local setup meeting these requirements.

## Project Structure

*   `core/`: Core components like the LLM engine and persona configuration.
*   `core/memory.py`: Manages the assistant's long-term memory.
*   `interface/`: User interface components (e.g., voice I/O).
*   `skills/`: Future directory for assistant skills/plugins.
*   `ingestion/`: Future directory for data ingestion pipelines.
*   `data/`: Data storage (e.g., databases, logs).
*   `data/memory.json`: Stores data like user preferences, facts, and profile information.
*   `main.py`: Main application entry point.

## Slash Commands

You can interact with the Eidos Assistant using special slash commands:

*   `/remember <category>.<key>=<value>`: Stores a piece of information.
    *   Example: `/remember user_profile.name=Alice`
    *   Example: `/remember user_preferences.theme=dark`
    *   If you update `user_profile.name` or `user_preferences.theme`, the assistant's system prompt will be updated immediately to reflect this change.
    *   Values are attempted to be saved as boolean (`true`/`false`), integer, or float if they match, otherwise as string.

*   `/recall <category>.<key>`: Retrieves a piece of information from memory.
    *   Example: `/recall user_profile.name`

*   `/forget <category>.<key>`: Removes a piece of information from memory.
    *   Example: `/forget user_profile.name`
    *   If this affects the system prompt (e.g. forgetting `user_profile.name`), the prompt will be updated.

*   `/system_prompt`: (Debug command) Prints the current system prompt that the LLM engine is using.

*   `/say <text to speak>`: Generates speech from the provided text using the configured TTS server and saves it to `eidos_tts_output.mp3` in the project root.
    *   Example: `/say Hello, I am Eidos.`

*   `/listen <path_to_audio_file>`: Transcribes the audio from the specified file using Whisper STT and displays the text.
    *   Example: `/listen path/to/my_audio.wav`
    *   **Note:** This command requires `openai-whisper` and `ffmpeg` to be correctly installed and configured in your environment. The STT model (`base.en` by default) will be downloaded by Whisper on first use.
