# Pathos Assistant

Pathos Assistant is a conversational AI assistant designed to be extensible and run locally. It can now understand natural language commands to control your Home Assistant devices (e.g., "turn on the lights", "check thermostat status") by intelligently forming requests to your Home Assistant server. This project is being developed iteratively.

## Prerequisites

*   Python (version 3.8+ recommended)
*   Pip (Python package installer)
*   Access to a local Large Language Model (LLM) server that is compatible with the OpenAI API.
*   For Text-to-Speech (TTS) functionality with the `/say` command, a running instance of a Kokoro-FastAPI compatible server is needed.
*   **For Direct TTS Audio Playback on Linux (via `/say` command):**
    *   The `playsound` library (installed via pip) relies on GStreamer for playing MP3 files. You may need to install GStreamer and its Python introspection bindings if MP3 playback doesn't work. On Debian/Ubuntu, this might involve packages like `gir1.2-gstreamer-1.0`, `gstreamer1.0-plugins-good`, `gstreamer1.0-plugins-ugly`.
*   **For Speech-to-Text (STT) functionality (`/listen` command):**
    *   The `openai-whisper` Python library (which includes `torch`). You can typically install this via `pip install openai-whisper`.
    *   `ffmpeg` installed on your system and available in your PATH. (e.g., `sudo apt install ffmpeg` on Debian/Ubuntu, or download from ffmpeg.org for other OS).
*   **For Wake Word Detection (e.g., `/always_listen` command):**
    *   The `pvporcupine` Python library. (`pip install pvporcupine`)
    *   A Picovoice AccessKey (see Configuration section).
*   **For Live Microphone Input (used in `/always_listen` mode):**
    *   `PyAudio` (Python library) requires system-level audio libraries.
        *   On Linux: `portaudio19-dev` and `libasound2-dev` (e.g., `sudo apt install portaudio19-dev libasound2-dev`).
        *   On macOS: `portaudio` (e.g., `brew install portaudio`).
        *   On Windows: PyAudio wheels often bundle PortAudio, but ensure microphone permissions are granted.
*   **For Home Assistant Integration (planned feature):**
    *   The `requests` Python library. (`pip install requests`)

## Installation

1.  Clone this repository.
2.  Install required Python packages:
    ```bash
    # pip install -r requirements.txt
    # (requirements.txt will be added in a future step)
    # For now, manually ensure the following are installed if not handled by subtasks:
    # pip install PyYAML openai python-dotenv openai-whisper pvporcupine requests playsound PyAudio
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
(Details as previously defined)

The application will attempt to load these variables. If `.env` is not found or a variable is missing, fallback default values will be used (which also point to common local server addresses).
Make sure your `.env` file is added to your `.gitignore` to avoid committing sensitive information.

**Setting up Porcupine Wake Word:**
(Details as previously defined)

**Setting up Home Assistant Integration:**
(Details as previously defined)

**Natural Language Control for Home Assistant**
(Details as previously defined)


## Running the Assistant

Currently, the assistant runs via a command-line interface:

```bash
python eidos_assistant/main.py
```

**Important for Conversational AI & TTS:**
(Details as previously defined)

**Important Notes on Advanced Voice Features (STT, Wake Word, Always-Listening Mode):**

Features like Speech-to-Text (STT) via the `/listen` command, Wake Word detection, and the `/always_listen` mode have been implemented in the codebase but **could not be fully tested by the AI assistant developer due to limitations in the development sandbox environment.** These limitations include issues installing large dependencies (like `torch` for Whisper), accessing specific hardware like microphones, or installing system-level audio libraries (like PortAudio for `PyAudio` or `ffmpeg`).

Users wishing to use these advanced voice features must:
1.  **Install Python Libraries:** Ensure `openai-whisper`, `pvporcupine`, `PyAudio`, and `playsound` are correctly installed (e.g., via `pip install openai-whisper pvporcupine PyAudio playsound`).
2.  **Install System Dependencies:**
    *   For STT (`openai-whisper`): `ffmpeg`.
    *   For Wake Word & Live Mic Input (`pvporcupine`, `PyAudio`): `PortAudio` (e.g., `portaudio19-dev`, `libasound2-dev` on Linux).
    *   For TTS MP3 Playback on Linux (`playsound`): GStreamer libraries.
3.  **Configure Services & Keys:**
    *   For Wake Word: A valid `PICOVOICE_ACCESS_KEY` and Porcupine keyword model(s) configured in `.env`.
    *   For TTS: A running Kokoro-FastAPI (or compatible) server configured in `.env`.
4.  **Ensure Hardware Access:** A functional microphone must be available and accessible to the Python environment where Pathos is run.
5.  **Download Models:** Whisper and Porcupine will download their specific models on first use, requiring an internet connection.

The successful operation of this entire voice pipeline (microphone -> wake word -> STT -> LLM -> TTS audio playback) is **highly contingent upon the user's local setup meeting all these requirements.**

## Project Structure
(Details as previously defined)

## Slash Commands

You can interact with the Eidos Assistant using special slash commands:
(Memory commands, /system_prompt as previously defined)

*   `/say <text to speak>`: Generates speech from the provided text using the configured TTS server, saves it to `eidos_tts_output.mp3`, and then attempts to play it directly.
    *   Example: `/say Hello, I am Pathos.`
    *   **Note on Playback (Linux):** The `playsound` library, used for playback, may require GStreamer and its Python bindings (e.g., `python3-gi`, `gir1.2-gstreamer-1.0`) to be installed on your Linux system to play MP3 files. On Windows and macOS, it typically works without extra steps for MP3s. Playback is blocking (the assistant will wait until sound finishes).

*   `/listen <path_to_audio_file>`: Transcribes the audio from the specified file using Whisper STT and displays the text.
    *   Example: `/listen path/to/my_audio.wav`
    *   **Note:** This command requires `openai-whisper` and `ffmpeg` to be correctly installed and configured in your environment. The STT model (`base.en` by default) will be downloaded by Whisper on first use.

*   `/always_listen`: Activates the "always-listening" mode using the microphone. Pathos will listen for a configured wake word (e.g., "picovoice"). Upon detection, it will listen for a spoken command, transcribe it, process it with the LLM, and speak the response. Press Ctrl+C to exit this mode.
    *   **Note:** This is an advanced feature and is **provided as largely untested by the AI assistant developer** due to sandbox limitations. Its functionality is highly dependent on the correct installation and configuration of multiple components by the user:
        *   `PyAudio` with its system dependencies (like PortAudio) for microphone access.
        *   `pvporcupine` for wake word detection (requires Picovoice AccessKey and keyword model setup).
        *   `openai-whisper` for Speech-to-Text (requires `ffmpeg` and `torch`).
        *   A functional microphone accessible by the Python environment.
        *   Correctly configured TTS for audio responses.

*   `/ha_status <entity_id>`: Retrieves and displays the current state and attributes of the specified Home Assistant entity.
    *   Example: `/ha_status light.living_room`
*   `/ha_toggle <entity_id>`: Sends a 'toggle' command to the specified Home Assistant entity (e.g., to toggle a light or switch).
    *   Example: `/ha_toggle switch.smart_plug`
