# Pathos Assistant

Pathos Assistant is a conversational AI assistant designed to be extensible and run locally. It supports natural language commands, Home Assistant integration, and multiple local and remote services for LLM and TTS. This project is being developed iteratively.

## Features

*   **Conversational AI:** Engage in text-based conversations.
*   **Multiple LLM Backends:**
    *   Connect to any OpenAI API compatible server (e.g., Ollama, local vLLM instances, OpenAI API).
    *   Run GGUF models locally using `llama-cpp-python` for full offline capability (CPU or GPU accelerated).
*   **Multiple TTS Backends:**
    *   Use a Kokoro-FastAPI compatible server for high-quality TTS.
    *   Use `pyttsx3` for local, offline TTS using system voices (SAPI5, NSSpeech, eSpeak).
*   **Voice Commands (Experimental):**
    *   Speech-to-Text (STT) via Whisper (`/listen`, `/always_listen`).
    *   Wake Word detection via PicoVoice Porcupine (`/always_listen`).
*   **Home Assistant Integration:** Control smart home devices using natural language or specific commands.
*   **Memory:** Remembers and recalls information across sessions.
*   **Customizable Persona:** Define the assistant's personality and behavior.
*   **Extensible Skills:** Designed for adding new capabilities (like Home Assistant control).

## Prerequisites

Beyond Python itself (version 3.8+ recommended) and Pip, Pathos Assistant relies on several external tools and libraries for its full functionality. The `setup.sh` script (see Installation) attempts to guide you in checking for these.

**Core Requirements:**
*   **Python Packages:** Listed in `eidos_assistant/requirements.txt`. These are installed by `pip install -r eidos_assistant/requirements.txt` (handled by the `setup.sh` script). Key libraries include `PyYAML`, `openai`, `python-dotenv`, `openai-whisper`, `pvporcupine`, `requests`, `playsound`, `PyAudio`, `pyttsx3`, and `llama-cpp-python`.
*   **LLM Engine Configuration:** Pathos Assistant supports two main types of LLM engines, configured via `LLM_ENGINE_TYPE` in the `.env` file:
    *   **`openai` (Default):** Connects to an OpenAI API compatible server. Requires `LLM_API_BASE_URL` and `LLM_API_KEY` (if applicable).
    *   **`local_llama_cpp`:** Runs a GGUF-format model locally. Requires `llama-cpp-python` installation and a model path (`LOCAL_LLM_MODEL_PATH`). See "Local LLM (llama-cpp-python) Setup" for details.
*   **TTS Engine Configuration (for `/say`):** Pathos Assistant supports multiple TTS engines, configured via `TTS_ENGINE` in the `.env` file:
    *   **`kokoro` (Default):** Requires a running instance of a Kokoro-FastAPI compatible server.
    *   **`local_pyttsx3`:** Uses the `pyttsx3` Python library for local, offline text-to-speech.

**System-Level Dependencies (checked by `setup.sh`):**

The `setup.sh` script will try to detect if these are present and provide installation instructions if they appear to be missing. Manual installation might be required depending on your OS and environment.

*   **C Compiler & CMake (for `local_llama_cpp`):**
    *   **Why:** If you choose `LLM_ENGINE_TYPE="local_llama_cpp"`, `llama-cpp-python` usually needs to be compiled from source during installation. This requires a C compiler (like GCC or Clang) and CMake.
    *   **Checked by `setup.sh`:** Yes.
    *   **Common Installation:**
        *   Debian/Ubuntu: `sudo apt install build-essential cmake`
        *   Fedora: `sudo dnf groupinstall "Development Tools" && sudo dnf install cmake`
        *   macOS: `xcode-select --install` (for Clang and build tools), and `brew install cmake` (if using Homebrew for CMake).
*   **`ffmpeg`:**
    *   **Why:** Essential for audio processing. `openai-whisper` (used for Speech-to-Text in `/listen` and `/always_listen`) requires `ffmpeg` to convert various audio formats into a format it can process.
    *   **Checked by `setup.sh`:** Yes.
    *   **Common Installation:**
        *   Debian/Ubuntu: `sudo apt install ffmpeg`
        *   Fedora: `sudo dnf install ffmpeg`
        *   macOS (Homebrew): `brew install ffmpeg`

*   **PortAudio:**
    *   **Why:** The `PyAudio` library, used for capturing live microphone input (e.g., in `/always_listen` mode), needs PortAudio development libraries.
    *   **Checked by `setup.sh`:** Yes (for Linux and macOS).
    *   **Common Installation:**
        *   Linux (Debian/Ubuntu): `sudo apt install portaudio19-dev libasound2-dev`
        *   Linux (Fedora): `sudo dnf install portaudio-devel alsa-lib-devel`
        *   macOS (Homebrew): `brew install portaudio`
        *   Windows: PyAudio installers often bundle PortAudio, but ensure microphone permissions are granted.

*   **GStreamer (Linux, for `playsound` MP3 playback):**
    *   **Why:** On Linux, the `playsound` library (used by the `/say` command for direct audio playback) often relies on GStreamer and its Python bindings to play MP3 files. Without these, MP3 playback might fail or be silent.
    *   **Checked by `setup.sh`:** Provides information and install commands for Linux.
    *   **Common Installation (Debian/Ubuntu):** `sudo apt install gir1.2-gstreamer-1.0 gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly python3-gi python3-gst-1.0`
    *   **Common Installation (Fedora):** `sudo dnf install gstreamer1-devel gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugins-ugly gstreamer1-plugins-bad-free python3-gobject python3-gst-1.0`
    *   **Note:** For other OSes, `playsound` usually handles MP3 playback without extra GStreamer steps.

*   **eSpeak (Linux, for `pyttsx3` local TTS):**
    *   **Why:** If you choose `TTS_ENGINE="local_pyttsx3"` on Linux, `pyttsx3` often uses `espeak` as its backend for speech synthesis.
    *   **Checked by `setup.sh`:** Yes.
    *   **Common Installation:**
        *   Debian/Ubuntu: `sudo apt install espeak`
        *   Fedora: `sudo dnf install espeak`
        *   (Note: `ffmpeg` and `libespeak1` may also be beneficial and are mentioned by `pyttsx3` documentation; `setup.sh` may also suggest these).

*   **Wake Word Engine Specifics:**
    *   `pvporcupine` (Python library): For wake word detection (e.g., "Hey Pathos").
    *   Picovoice AccessKey: Required for `pvporcupine`. See "Configuration" section.

*   **Home Assistant Integration:**
    *   `requests` (Python library): For communicating with your Home Assistant server.

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd pathos-assistant # Or your chosen directory name
    ```
2.  **Run the Setup Script:**
    Navigate to the `eidos_assistant` directory and execute the setup script:
    ```bash
    cd eidos_assistant
    ./setup.sh
    ```
    This script will:
    *   Install necessary Python packages from `requirements.txt`.
    *   Attempt to detect your Operating System (Linux, macOS).
    *   Check for key system dependencies like `ffmpeg` and `PortAudio`.
    *   Provide instructions for installing missing system dependencies (including C compiler & CMake for `llama-cpp-python`).
    *   Offer guidance for GStreamer on Linux for MP3 playback and eSpeak for `pyttsx3`.
    *   **Note on `llama-cpp-python` compilation:** The `setup.sh` script reminds you that `llama-cpp-python` might compile from source. For hardware acceleration (GPU support like CUDA or Metal), you'll need to set specific `CMAKE_ARGS` environment variables *before* running `pip install -r requirements.txt` or `pip install llama-cpp-python`. Refer to the official `llama-cpp-python` documentation for detailed instructions on this. If you install it without these arguments first, you may need to uninstall and reinstall it with the correct `CMAKE_ARGS`.

    Please pay attention to the output of `setup.sh` and install any missing system packages it recommends. Manual installation might still be needed if the script cannot fully automate it for your specific OS distribution or setup. The `setup.sh` script also provides guidance for installing `espeak` (for `pyttsx3` on Linux) and GStreamer plugins (for `playsound` on Linux).

## Local LLM (`llama-cpp-python`) Setup

If you set `LLM_ENGINE_TYPE="local_llama_cpp"` in your `.env` file, follow these additional steps:

1.  **Install `llama-cpp-python` with appropriate hardware acceleration:**
    *   Ensure you have a C compiler and CMake installed (see "System-Level Dependencies" and run `setup.sh` for checks).
    *   For **CPU-only**, `pip install llama-cpp-python` (as part of `requirements.txt`) might be sufficient, or it will build from source.
    *   For **GPU acceleration** (highly recommended for better performance):
        *   **NVIDIA GPUs (CUDA):** You'll need the CUDA Toolkit installed. Set `CMAKE_ARGS` like:
            ```bash
            CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python --upgrade --force-reinstall --no-cache-dir
            ```
            (Adjust `-DGGML_CUDA` flags based on `llama-cpp-python` docs if needed).
        *   **Apple Silicon (Metal):**
            ```bash
            CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python --upgrade --force-reinstall --no-cache-dir
            ```
        *   For other backends (OpenBLAS, ROCm, Vulkan), consult the [official `llama-cpp-python` documentation](https://llama-cpp-python.readthedocs.io/en/latest/#installation).
    *   It's best to set `CMAKE_ARGS` *before* running `pip install -r requirements.txt` for the first time, or you may need to uninstall `llama-cpp-python` and reinstall it.

2.  **Download a GGUF Model:**
    *   You need a model file in GGUF format. You can find many on Hugging Face Hub (e.g., search for models by "TheBloke" or other providers who specialize in GGUF).
    *   Choose a model size and quantization level appropriate for your hardware (e.g., Q4_K_M or Q5_K_M are common balances of size/performance). Smaller models (e.g., 3B, 7B parameters) are more suitable for CPU or limited VRAM.
    *   Example: Download a model like `llama-2-7b-chat.Q4_K_M.gguf`.

3.  **Configure `.env`:**
    *   Set `LLM_ENGINE_TYPE="local_llama_cpp"`.
    *   Set `LOCAL_LLM_MODEL_PATH` to the absolute path of your downloaded `.gguf` file.
    *   Adjust `LOCAL_LLM_N_GPU_LAYERS` (e.g., to a high number like `100` or `-1` if you want to offload as many layers as possible to GPU, or `0` for CPU only).
    *   Adjust `LOCAL_LLM_N_CTX` (context window) if needed (e.g., `2048`, `4096`). Check the model's recommended context size.
    *   Optionally set `LOCAL_LLM_CHAT_FORMAT` if you know your model's specific format (e.g., "llama-2", "mistral", "chatml"). If unset, `llama-cpp-python` will try to auto-detect.

4.  **Model Loading Time:** Be aware that loading the local model into memory when Pathos Assistant starts can take some time (from seconds to minutes) depending on model size and system speed. Subsequent uses may be faster if the model remains cached by the OS.

## Configuration via `.env` File

Pathos Assistant uses a `.env` file in the project root (`eidos_assistant/`) to manage configurations for external services and engine choices. Create this file by copying `.env.example` (if it exists) or by creating a new file named `.env`.

Example `.env` content:

```env
# .env - Environment variables for Pathos Assistant

# --- LLM Engine Configuration ---
# LLM_ENGINE_TYPE: Specifies the LLM engine to use.
# Options:
#   "openai" (default): Connects to an OpenAI API compatible server (e.g., Ollama, vLLM).
#                       Uses LLM_API_BASE_URL and LLM_API_KEY.
#   "local_llama_cpp": Runs a GGUF model locally using llama-cpp-python.
#                      Uses LOCAL_LLM_MODEL_PATH and other LOCAL_LLM_* variables.
LLM_ENGINE_TYPE="openai"

# --- OpenAI Configuration (if LLM_ENGINE_TYPE is "openai") ---
LLM_API_BASE_URL="http://localhost:11434/v1" # Example for Ollama
LLM_API_KEY="NotNeededForOllama"             # No API key needed for local Ollama
# OPENAI_MODEL_NAME="gemma:2b"               # Optional: Specify model for OpenAI compatible server

# --- Local Llama.cpp Configuration (if LLM_ENGINE_TYPE is "local_llama_cpp") ---
LOCAL_LLM_MODEL_PATH="/path/to/your/model.gguf" # REQUIRED if using local_llama_cpp
LOCAL_LLM_N_GPU_LAYERS=0                        # Number of layers to offload to GPU. 0 for CPU, -1 for all possible.
LOCAL_LLM_N_CTX=2048                            # Context window size.
LOCAL_LLM_CHAT_FORMAT="llama-2"                 # Optional: e.g., llama-2, mistral, chatml, vicuna. Auto-detect if not set.
# LOCAL_LLM_TEMPERATURE=0.7                     # Optional: Defaults to 0.7 in code
# LOCAL_LLM_MAX_TOKENS=150                      # Optional: Defaults to 150 in code


# --- Text-to-Speech (TTS) Configuration ---
# Choose your TTS engine. Options:
# "kokoro" (default): Uses a Kokoro-FastAPI compatible server.
# "local_pyttsx3": Uses the pyttsx3 library for local, offline TTS.
TTS_ENGINE="kokoro"

# Configuration for Kokoro TTS (if TTS_ENGINE="kokoro")
KOKORO_TTS_BASE_URL="http://localhost:8880/v1"
KOKORO_TTS_API_KEY="not-needed"
KOKORO_TTS_VOICE="af_sky"
# Example Kokoro voices: "af_sky+af_bella" (blended), "af_bella(2)+af_heart(1)" (weighted)

# Configuration for local_pyttsx3 (if TTS_ENGINE="local_pyttsx3")
# pyttsx3 uses system voices. Voice selection/rate/volume are not currently set via .env.
# On Linux, 'espeak' is a common backend for pyttsx3. Ensure it's installed (see Prerequisites).

# --- Porcupine Wake Word Engine Configuration ---
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
(Details for LLM, TTS, Porcupine, and Home Assistant as shown in the example above)

The application will attempt to load these variables. If `.env` is not found or a variable is missing, fallback default values will be used where possible (which also point to common local server addresses).
Make sure your `.env` file is added to your `.gitignore` to avoid committing sensitive information.

**Setting up Porcupine Wake Word:**
(Details as previously defined - ensure this section is complete and accurate)

**Setting up Home Assistant Integration:**
(Details as previously defined - ensure this section is complete and accurate)

## Running the Assistant

Currently, the assistant runs via a command-line interface:

```bash
python eidos_assistant/main.py
```
Ensure your configured LLM and TTS engines are running and accessible if they are server-based. For local engines like `llama-cpp-python` or `pyttsx3`, ensure they are correctly installed and configured.

## Testing with `testMe.sh`

A helper script `eidos_assistant/testMe.sh` is provided to guide you through testing various functionalities. It does not run automated tests but provides a checklist and instructions for manually verifying different components like:
*   Initial setup validation using `/validate_setup`.
*   LLM engine functionality (both OpenAI compatible and local Llama.cpp).
*   TTS engine functionality (both Kokoro and local pyttsx3).
*   Basic STT via `/listen`.
*   Home Assistant command execution.

To use it:
```bash
cd eidos_assistant
./testMe.sh
```
Follow the on-screen prompts, which will involve editing your `.env` file and running `python main.py` to interact with Pathos Assistant.

## Advanced Voice Features (STT, Wake Word, Always-Listening Mode)

Features like Speech-to-Text (STT) via the `/listen` command, Wake Word detection, and the `/always_listen` mode require careful setup:

1.  **Install Python Libraries:** Ensure `openai-whisper` (including `torch`), `pvporcupine`, `PyAudio`, and `playsound` are correctly installed (handled by `requirements.txt` and `setup.sh`).
2.  **Install System Dependencies:**
    *   For STT (`openai-whisper`): `ffmpeg` is crucial.
    *   For Wake Word & Live Mic Input (`pvporcupine`, `PyAudio`): `PortAudio` development libraries (e.g., `portaudio19-dev`, `libasound2-dev` on Linux) are needed.
    *   For TTS MP3 Playback on Linux (`playsound`): GStreamer libraries and plugins (good, ugly) are often necessary.
    *   The `setup.sh` script attempts to check for these.
3.  **Configure Services & Keys:**
    *   For Wake Word (`/always_listen`): A valid `PICOVOICE_ACCESS_KEY` and Porcupine keyword model(s) must be configured in `.env`.
    *   For TTS (if using `kokoro`): Ensure the Kokoro-FastAPI server is running and configured in `.env`.
4.  **Ensure Hardware Access:** A functional microphone must be available and accessible to the Python environment where Pathos is run.
5.  **Download Models:** Whisper and Porcupine will download their specific AI models on first use, requiring an internet connection at that time.

The successful operation of this entire voice pipeline (microphone -> wake word -> STT -> LLM -> TTS audio playback) is **highly contingent upon the user's local setup meeting all these requirements.**

## Troubleshooting

If you encounter issues:

*   **Run `/validate_setup`:** Type this command in Pathos Assistant first. It checks many common configuration and dependency issues for LLM, TTS, FFmpeg, Microphones, and PicoVoice.
*   **Review Console Output:** Pathos Assistant now provides more specific error messages for missing dependencies or misconfigurations. Check the terminal output where you ran `python main.py`.
*   **`llama-cpp-python` Compilation Errors:**
    *   Ensure a C compiler (GCC, Clang, MSVC) and CMake are installed. `setup.sh` checks for these and provides installation hints.
    *   For hardware acceleration (CUDA, Metal, etc.), you **must** set `CMAKE_ARGS` *before* installing `llama-cpp-python`. Refer to the [official `llama-cpp-python` documentation](https://llama-cpp-python.readthedocs.io/en/latest/#installation) for the correct flags for your hardware. If already installed without, uninstall (`pip uninstall llama-cpp-python`) and reinstall with the correct `CMAKE_ARGS`.
*   **Local LLM Model Issues (`local_llama_cpp`):**
    *   **Model Path:** Double-check `LOCAL_LLM_MODEL_PATH` in your `.env` file. It must be the exact path to your GGUF model file.
    *   **Model Download:** Ensure you have downloaded a compatible GGUF model file.
    *   **Permissions:** Ensure the application has read permissions for the model file.
    *   **Performance:** Large models can be slow on CPU. Ensure `LOCAL_LLM_N_GPU_LAYERS` is set appropriately if you have a GPU and installed `llama-cpp-python` with GPU support.
*   **`pyttsx3` No Sound (especially on Linux):**
    *   Ensure `espeak` is installed: `sudo apt install espeak` or `sudo dnf install espeak`. `setup.sh` checks for this.
    *   Sometimes, other backends might be needed or specific PulseAudio/ALSA configurations might interfere.
*   **`playsound` No Sound for MP3s (Linux):**
    *   This usually means GStreamer plugins are missing. Install them (e.g., `gstreamer1.0-plugins-good`, `gstreamer1.0-plugins-ugly`). `setup.sh` provides specific commands.
*   **Microphone Not Working (`PyAudio` / `/always_listen` / `/listen` after wake word):**
    *   Ensure PortAudio development libraries are installed (e.g., `portaudio19-dev` on Debian/Ubuntu). `setup.sh` checks for this.
    *   Verify your microphone is connected, not muted, and selected as the default system input.
    *   Check microphone permissions for your terminal or Python application.
*   **`ffmpeg` Not Found (STT features):**
    *   Ensure `ffmpeg` is installed and in your system's PATH. `setup.sh` checks for this.
*   **Python Package Installation Issues:**
    *   Ensure `pip` is up to date (`pip install --upgrade pip`).
    *   If a specific package fails, try installing it manually with verbose output to see the error (e.g., `pip install -v openai-whisper`).

## Project Structure

*   `eidos_assistant/`: Main application directory.
    *   `main.py`: Entry point for the assistant.
    *   `core/`: Core logic.
        *   `llm_engine.py`: Handles LLM interactions (OpenAI API or local Llama.cpp).
        *   `memory.py`: Manages persistent memory.
        *   `persona_config.yaml`: Defines the assistant's personality.
        *   `validation_utils.py`: Helper functions for the `/validate_setup` command.
    *   `interface/`: Handles external interactions.
        *   `voice_io.py`: Manages TTS (Kokoro, pyttsx3) and STT (Whisper), Wake Word (PicoVoice), audio playback.
    *   `skills/`: Contains callable skills like Home Assistant integration.
        *   `home_assistant_skill.py`: Logic for Home Assistant control.
    *   `data/`: For persistent data like memory.
        *   `memory.json`: Stores the assistant's memory.
    *   `.env`: Environment variable configuration (user-created).
    *   `requirements.txt`: Python package dependencies.
    *   `setup.sh`: Shell script for helping set up dependencies.
    *   `testMe.sh`: Guided testing script.

## Slash Commands

You can interact with Pathos Assistant using special slash commands:

*   `/remember <category>.<key>=<value>`: Stores information.
*   `/recall <category>.<key>`: Retrieves stored information.
*   `/forget <category>.<key>`: Removes stored information.
*   `/system_prompt`: Displays the current system prompt being used for the LLM.
*   `/say <text to speak>`: Generates speech from the provided text using the configured TTS engine (either Kokoro or local pyttsx3 via `TTS_ENGINE` in `.env`). Saves it to `eidos_tts_output.mp3` and then attempts to play it directly using `playsound`.
    *   Example: `/say Hello, I am Pathos.`
    *   **Note on Playback (Linux with `playsound`):** The `playsound` library, used for playback *after* TTS generation (regardless of which engine produced the MP3), may require GStreamer and its Python bindings to be installed on your Linux system to play MP3 files.
    *   **Note on `local_pyttsx3` on Linux:** This engine often relies on `espeak` (see Prerequisites).
    *   Playback is blocking (the assistant will wait until sound finishes).
*   `/listen <path_to_audio_file>`: Transcribes the audio from the specified file using Whisper STT and displays the text.
    *   Example: `/listen path/to/my_audio.wav`
    *   **Note:** This command requires `openai-whisper` and `ffmpeg` to be correctly installed and configured in your environment. The STT model (default: `base.en`) will be downloaded by Whisper on first use.
*   `/always_listen`: Activates "always-listening" mode using the microphone. Pathos listens for a configured wake word (e.g., "picovoice" via `.env`). Upon detection, it records a command, transcribes it, processes it with the LLM, and speaks the response. Press Ctrl+C to exit.
    *   **Note:** This is an advanced feature requiring full setup of PyAudio, PortAudio, PicoVoice Porcupine (AccessKey, keyword files), Whisper, and ffmpeg.
*   `/ha_status <entity_id>`: Retrieves and displays the current state of a Home Assistant entity.
*   `/ha_toggle <entity_id>`: Toggles a Home Assistant entity (e.g., a light or switch).
*   `/validate_setup`: Performs a series of checks on your setup and dependencies (LLM, TTS, FFmpeg, Microphone, PicoVoice) and reports their status.
