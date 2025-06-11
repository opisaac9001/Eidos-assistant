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
2.  Install required Python packages. Navigate to the `eidos_assistant` directory (if you are in the parent directory that contains it) and run:
    ```bash
    pip install -r requirements.txt
    # This file now includes all necessary dependencies.
    # Key dependencies for core features include PyYAML, openai, python-dotenv.
    # For voice: openai-whisper, pvporcupine, playsound, PyAudio.
    # For Home Assistant: requests.
    # For Knowledge Base (RAG): chromadb, sentence-transformers.
    # For News Headlines: feedparser.
    # For Web Search: duckduckgo-search.
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

# OpenWeatherMap API Key (for Weather Skill)
OPENWEATHERMAP_API_KEY="YOUR_OPENWEATHERMAP_API_KEY_HERE"
```

**Key Environment Variables:**
(Details as previously defined)
*   `OPENWEATHERMAP_API_KEY`: Your API key from OpenWeatherMap.org, required for the Weather skill to fetch current weather data.

The application will attempt to load these variables. If `.env` is not found or a variable is missing, fallback default values will be used (which also point to common local server addresses).
Make sure your `.env` file is added to your `.gitignore` to avoid committing sensitive information.

**Setting up Porcupine Wake Word:**
(Details as previously defined)

**Setting up Home Assistant Integration:**
(Details as previously defined)

**Setting up Weather Skill:**

To enable Pathos to fetch current weather information, you need to configure an API key from OpenWeatherMap.
1.  Sign up for a free (or paid) API key at [https://openweathermap.org/appid](https://openweathermap.org/appid). The "Current Weather Data" API is available for free.
2.  Once you have your API key, add it to your `eidos_assistant/.env` file:
    ```env
    OPENWEATHERMAP_API_KEY="YOUR_API_KEY_HERE"
    ```
    Replace `"YOUR_API_KEY_HERE"` with the actual key you obtained.

The WeatherSkill has been refactored to use the new Skill Capability Framework (see below). Its `tool_name` for LLM interaction is now `"get_weather"`. For example, if the LLM decides to fetch weather, it would output JSON like: `{"tool_name": "get_weather", "parameters": {"city": "London", "units": "metric"}}`.

### News Skill

Pathos can fetch recent news headlines from a predefined list of RSS feeds. This skill uses the `feedparser` library to parse RSS data.

Currently, the skill includes default feeds for categories such as:
*   **World News**: BBC News
*   **Tech News**: TechCrunch
*   **Science News**: ScienceDaily
*   **General Tech**: Ars Technica

You can request news from one of these specific categories, or get a mix from all available sources if no category (or "all") is specified. When fetching from all sources, headlines are aggregated and sorted by publication date.

Customizing the list of RSS feeds may be supported in a future update. No API keys are required for the current default news feeds.

**Natural Language Control for Home Assistant**
Pathos can now understand natural language commands to control your Home Assistant devices (e.g., "turn on the lights", "check thermostat status") and can also list available devices to help you understand its capabilities.
(Details as previously defined)


## Knowledge Base (RAG)

Pathos Assistant can build and use a local knowledge base to provide more informed answers. This is achieved through Retrieval Augmented Generation (RAG).

Documents (currently plain text and Markdown files) can be added to the knowledge base. When you ask a question, Pathos will search these documents for relevant information and use that to augment its response from the LLM.

This feature uses ChromaDB for storing document embeddings locally and Sentence-Transformers (specifically, the 'all-MiniLM-L6-v2' model by default) for generating these embeddings.

The knowledge base data is persisted by default in the `eidos_assistant/data/kb_chroma_db/` directory.

Note: The effectiveness of this feature depends on the quality of ingested documents and the relevance of your queries to their content.


## Skill Capability Framework

To provide a standardized and extensible way to add new functionalities (tools) that the LLM can use, Pathos Assistant incorporates a Skill Capability Framework.

**Core Concepts:**

*   **`BaseSkill` Abstract Class:** Located in `eidos_assistant/skills/base_skill.py`, this class defines the contract that all skills must adhere to. It requires skills to implement specific methods for defining their capabilities and for execution.
*   **Tool Signature (`get_tool_signature()`):** Each skill must implement this method. It returns a structured dictionary (or a list of them if the skill provides multiple distinct tools) that describes the tool(s) to the LLM. This signature includes:
    *   `tool_name`: A unique name for the tool (e.g., "get_weather", "home_assistant_control").
    *   `description`: A clear description of what the tool does.
    *   `parameters`: A list of parameters the tool accepts. Each parameter is defined with its `name`, `type` (e.g., "string", "integer", "boolean" based on JSON schema types), `description`, and whether it's `required`.
    *   The structure is defined using `ToolSignature` and `ToolParameter` TypedDicts in `base_skill.py` for clarity and type checking.
*   **Execution (`execute()`):** Each skill must implement this method. The `LLMEngine` calls `execute(action: str | None, args: Dict[str, Any])` with arguments parsed from the LLM's JSON output. The `action` parameter allows a single skill to handle multiple related functions if needed (though often, an 'action' can also be a regular parameter). The method returns a result that the `LLMEngine` then processes (e.g., formats for the user or uses in a subsequent LLM call).

**Integration with LLMEngine:**

1.  **Registration:** Skill instances (that inherit from `BaseSkill`) are registered with the `LLMEngine` using its `register_skill()` method during initialization.
2.  **Dynamic System Prompt:** The `LLMEngine` dynamically constructs the "Available Tools" section of its system prompt by iterating through the signatures of all registered skills. This informs the LLM about what tools it can request and how to format the JSON for them.
3.  **Dynamic Dispatch:** When the LLM responds with a JSON object indicating a tool call, the `LLMEngine` uses the `tool_name` to find the corresponding registered skill in its `self.skills` dictionary and then calls its `execute()` method with the provided parameters.

**Transition:**
This is a new framework. Existing skills (like Home Assistant, Web Search, News) will be gradually refactored to inherit from `BaseSkill` and integrate with this system. During the transition, `LLMEngine` maintains both the new dynamic dispatch mechanism and legacy hardcoded handling for non-refactored skills. The `WeatherSkill` is the first skill to be fully refactored to this new framework.

The code for the framework and individual skills includes comments to guide developers.


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
*   `/ha_list_entities`: Retrieves and displays a list of all available entities from your Home Assistant instance, showing their entity ID, friendly name, and current state.
    *   Example: `/ha_list_entities`
*   `/kb_add_file <file_path>`: Adds the content of the specified text or Markdown file to the knowledge base. The file name is used as the document ID.
    *   Example: `/kb_add_file path/to/my_document.txt`
*   `/kb_add_directory <directory_path>`: Recursively scans the specified directory for `.txt` and `.md` files and adds their content to the knowledge base. The relative path of each file from the specified directory is used as its document ID.
    *   Example: `/kb_add_directory path/to/my_notes_folder/`
*   `/weather <city_name> [--units imperial|metric]`: Fetches the current weather for the specified city. Units default to metric if not specified. The LLM will use the tool name `"get_weather"` for this functionality.
    *   Example 1: `/weather London`
    *   Example 2: `/weather "New York" --units imperial`
*   `/search <query>`: Performs a web search using DuckDuckGo for the given query and displays the top results.
    *   Example: `/search latest AI advancements`
*   `/news [category] [--limit <number>]`: Fetches recent news headlines. You can specify an optional `category` (e.g., 'Tech News', 'World News', 'Science News', 'Ars Technica'). If no category or 'all' is provided, it fetches a mix from default sources. The `--limit` flag (defaulting to 5) controls the number of headlines returned.
    *   Example 1: `/news`
    *   Example 2: `/news Tech News --limit 3`
    *   Example 3: `/news "World News"`
