# Pathos Assistant

Pathos Assistant is a conversational AI assistant designed to be extensible and run locally. It can now understand natural language commands to control your Home Assistant devices (e.g., "turn on the lights", "check thermostat status") by intelligently forming requests to your Home Assistant server. This project is being developed iteratively.

## Prerequisites

*   Python (version 3.8+ recommended)
*   Pip (Python package installer)
*   Access to a local Large Language Model (LLM) server that is compatible with the OpenAI API.
*   For Text-to-Speech (TTS) functionality with the `/say` command, a running instance of a Kokoro-FastAPI compatible server is needed.
*   **For Speech-to-Text (STT) functionality (`/listen` command):**
    *   The `openai-whisper` Python library (which includes `torch`). You can typically install this via `pip install openai-whisper`.
    *   `ffmpeg` installed on your system and available in your PATH. (e.g., `sudo apt install ffmpeg` on Debian/Ubuntu, or download from ffmpeg.org for other OS).
*   **For Wake Word Detection (e.g., `/always_listen` command):**
    *   The `pvporcupine` Python library. (`pip install pvporcupine`)
    *   A Picovoice AccessKey (see Configuration section).
*   **For Home Assistant Integration (planned feature):**
    *   The `requests` Python library. (`pip install requests`)

## Installation

1.  Clone this repository.
2.  Install required Python packages:
    ```bash
    # pip install -r requirements.txt
    # (requirements.txt will be added in a future step)
    # For now, manually ensure the following are installed if not handled by subtasks:
    # pip install PyYAML openai python-dotenv openai-whisper pvporcupine requests
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

# Porcupine Wake Word Engine Configuration
PICOVOICE_ACCESS_KEY="YOUR_PICOVOICE_ACCESS_KEY_HERE"
PORCUPINE_BUILTIN_KEYWORDS="picovoice"
PORCUPINE_KEYWORD_PATHS=""
PORCUPINE_MODEL_PATH=""
PORCUPINE_SENSITIVITIES=""

# Home Assistant Configuration
HOME_ASSISTANT_URL="http://homeassistant.local:8123"
HOME_ASSISTANT_TOKEN="YOUR_LONG_LIVED_ACCESS_TOKEN_HERE"
```

**Key Environment Variables:**

*   `LLM_API_BASE_URL`: The base URL for your OpenAI API compatible LLM server.
*   `LLM_API_KEY`: The API key for your LLM server (if required).
*   `KOKORO_TTS_BASE_URL`: The base URL for your Kokoro-FastAPI TTS server.
*   `KOKORO_TTS_API_KEY`: The API key for your TTS server (if required, typically "not-needed" for local Kokoro-FastAPI).
*   `KOKORO_TTS_VOICE`: The default voice to be used for TTS. Consult your Kokoro-FastAPI documentation for available voices.
*   `PICOVOICE_ACCESS_KEY`: Your AccessKey from the [Picovoice Console](https://console.picovoice.ai/). Required for Porcupine Wake Word.
*   `PORCUPINE_BUILTIN_KEYWORDS`: Optional. A comma-separated list of built-in keywords to detect (e.g., "picovoice", "bumblebee"). Defaults to "picovoice".
*   `PORCUPINE_KEYWORD_PATHS`: Optional. A comma-separated list of absolute paths to custom `.ppn` wake word model files. If you want to use "Pathos" as a wake word, you'll need to create a model for it on the Picovoice Console and provide the path here.
*   `PORCUPINE_MODEL_PATH`: Optional. Path to a Porcupine model file (`.pv`) for non-English language support. Defaults to English.
*   `PORCUPINE_SENSITIVITIES`: Optional. A comma-separated list of sensitivity values (0.0 to 1.0) for each keyword. Must match the number and order of combined built-in and custom keywords.
*   `HOME_ASSISTANT_URL`: The full URL of your Home Assistant instance (e.g., `http://localhost:8123` or `http://your_ha_ip_address:8123`).
*   `HOME_ASSISTANT_TOKEN`: A Long-Lived Access Token generated from your Home Assistant user profile.


The application will attempt to load these variables. If `.env` is not found or a variable is missing, fallback default values will be used (which also point to common local server addresses).
Make sure your `.env` file is added to your `.gitignore` to avoid committing sensitive information.

**Setting up Porcupine Wake Word:**
1.  Sign up for a free account at [Picovoice Console](https://console.picovoice.ai/).
2.  Copy your `AccessKey` from the console and set it as `PICOVOICE_ACCESS_KEY` in your `.env` file.
3.  Porcupine can detect built-in keywords (like "picovoice", "bumblebee", "grasshopper", etc. - check Picovoice documentation for the full list for English). You can list desired ones in `PORCUPINE_BUILTIN_KEYWORDS`.
4.  To use custom wake words (e.g., "Pathos"), you need to train a model on the Picovoice Console. This will generate a `.ppn` file. Provide the full path to this file (or multiple, comma-separated) in `PORCUPINE_KEYWORD_PATHS`.
5.  If using only built-in keywords, `PORCUPINE_KEYWORD_PATHS` can be left empty. If using only custom keywords, `PORCUPINE_BUILTIN_KEYWORDS` can be left empty. Both can be used together.

**Setting up Home Assistant Integration:**
1.  Ensure your Home Assistant instance is running and accessible from where you run Pathos.
2.  Set `HOME_ASSISTANT_URL` in your `.env` file to the correct URL for your Home Assistant instance.
3.  Generate a Long-Lived Access Token in Home Assistant:
    *   Go to your Home Assistant profile (click your user icon in the bottom left).
    *   Scroll down to the "Long-Lived Access Tokens" section.
    *   Click "Create Token", give it a name (e.g., "Pathos_Assistant"), and copy the generated token.
    *   **Important:** You will only see the token once. Store it securely.
4.  Set this token as `HOME_ASSISTANT_TOKEN` in your `.env` file.

**Natural Language Control for Home Assistant**

When you give Pathos a command related to smart home devices (e.g., "Turn on the kitchen light," "Is the front door locked?"), Pathos's underlying Language Model (LLM) is instructed to translate your request into a specific JSON format. This JSON object precisely defines the action (like turning a device on/off or getting its status), the target device (entity ID), and any necessary parameters (like brightness or temperature). Pathos then processes this JSON command to interact with your Home Assistant server.

This allows for more flexible and natural interaction than using only fixed slash commands. For this to work effectively:
*   Your Home Assistant must be correctly configured in the `.env` file.
*   The LLM must be capable of understanding your request and correctly formatting the JSON based on the instructions in its system prompt.
*   You might need to be specific with entity names if you have many similar devices, or help Pathos learn them over time (future feature).

Examples of what you can try:
*   "Pathos, turn on the living room lamp."
*   "Pathos, please switch off the bedroom fan."
*   "Can you toggle the office air purifier?"
*   "What is the current status of the main door lock?"
*   "Set the thermostat to 21 degrees."


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

**Important Notes on Advanced Voice Features (STT & Wake Word):**
Features like Speech-to-Text (STT) via the `/listen` command (using Whisper) and the planned Wake Word detection (using Porcupine, e.g., via `/always_listen`) have been implemented or designed in the codebase but **could not be fully tested by the AI assistant developer due to limitations in the development sandbox environment.** These limitations include issues installing large dependencies (like `torch` for Whisper) or accessing hardware like microphones.

Users wishing to use these advanced voice features must:
1.  **For STT:** Ensure `openai-whisper` is installed (`pip install openai-whisper`), `ffmpeg` is on the system PATH, and Whisper models can be downloaded.
2.  **For Wake Word:**
    *   Ensure `pvporcupine` is installed (`pip install pvporcupine`).
    *   Obtain a `PICOVOICE_ACCESS_KEY` from the [Picovoice Console](https://console.picovoice.ai/) and configure it in the `.env` file.
    *   Configure built-in keywords (e.g., via `PORCUPINE_BUILTIN_KEYWORDS="picovoice"`) or paths to custom `.ppn` model files (via `PORCUPINE_KEYWORD_PATHS`) in the `.env` file.
3.  **For a functional always-listening loop (using Wake Word and STT):** Implement real-time microphone audio capture (e.g., using a library like PyAudio or sounddevice) and integrate it with the conceptual loop provided in `main.py`. This part is not pre-implemented.

The successful operation of these features is contingent upon the user's local setup meeting these specific requirements. The core logic for STT and Wake Word detection has been added to `VoiceIO` but could not be live-tested by the AI assistant developer.

## Project Structure

*   `core/`: Core components like the LLM engine and persona configuration.
*   `core/memory.py`: Manages the assistant's long-term memory.
*   `interface/`: User interface components (e.g., voice I/O).
*   `skills/`: Future directory for assistant skills/plugins.
*   `skills/home_assistant_skill.py`: Contains the `HomeAssistantSkill` class for interacting with a Home Assistant instance.
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

*   `/always_listen`: Activates a conceptual "always-listening" mode.
    *   **Note:** This command in its current state initiates a placeholder loop. It demonstrates where wake word detection using Porcupine would occur if live microphone audio processing were fully implemented. It does not currently process live audio. To make this functional, you would need to integrate an audio input library (e.g., PyAudio, sounddevice) to continuously feed audio data to the Porcupine engine within `VoiceIO`.

*   `/ha_status <entity_id>`: Retrieves and displays the current state and attributes of the specified Home Assistant entity.
    *   Example: `/ha_status light.living_room`
*   `/ha_toggle <entity_id>`: Sends a 'toggle' command to the specified Home Assistant entity (e.g., to toggle a light or switch).
    *   Example: `/ha_toggle switch.smart_plug`
