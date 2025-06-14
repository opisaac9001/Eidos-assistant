#!/bin/bash

# This script sets up the Eidos Assistant environment.
# It installs Python dependencies and checks for common system dependencies.

echo "Starting Eidos Assistant setup..."

# --- Python Dependencies ---
echo ""
echo "Installing Python dependencies from requirements.txt..."
if pip install -r eidos_assistant/requirements.txt; then
    echo "Python dependencies installed successfully."
else
    echo "Error installing Python dependencies. Please check pip output."
    # Decide if script should exit here. For now, let's continue with system checks.
fi

echo ""
echo "--- System Dependency Checks ---"

# --- OS Detection ---
OS_TYPE=""
if [[ "$(uname)" == "Linux" ]]; then
    OS_TYPE="Linux"
    if command -v apt-get &> /dev/null; then
        PKG_MANAGER="apt"
    elif command -v dnf &> /dev/null; then
        PKG_MANAGER="dnf"
    else
        PKG_MANAGER="unknown_linux"
    fi
elif [[ "$(uname)" == "Darwin" ]]; then # macOS
    OS_TYPE="macOS"
    if command -v brew &> /dev/null; then
        PKG_MANAGER="brew"
    else
        PKG_MANAGER="unknown_mac"
    fi
else
    OS_TYPE="Unknown"
fi

echo "Detected OS: $OS_TYPE"
if [[ "$OS_TYPE" == "Linux" && "$PKG_MANAGER" != "unknown_linux" ]]; then
    echo "Linux Package Manager: $PKG_MANAGER"
elif [[ "$OS_TYPE" == "macOS" && "$PKG_MANAGER" != "unknown_mac" ]]; then
    echo "macOS Package Manager: $PKG_MANAGER"
fi

# --- ffmpeg Check ---
echo ""
echo "Checking for ffmpeg (required for Speech-to-Text)..."
if command -v ffmpeg &> /dev/null; then
    echo "ffmpeg is already installed."
else
    echo "ffmpeg not found."
    if [[ "$PKG_MANAGER" == "apt" ]]; then
        echo "To install ffmpeg on Debian/Ubuntu, run: sudo apt update && sudo apt install ffmpeg"
    elif [[ "$PKG_MANAGER" == "dnf" ]]; then
        echo "To install ffmpeg on Fedora, run: sudo dnf install ffmpeg"
    elif [[ "$OS_TYPE" == "macOS" && "$PKG_MANAGER" == "brew" ]]; then
        echo "To install ffmpeg on macOS with Homebrew, run: brew install ffmpeg"
    else
        echo "Please install ffmpeg using your system's package manager. It is required for audio processing (e.g., for Whisper STT)."
    fi
fi

# --- PortAudio Check ---
echo ""
echo "Checking for PortAudio (required for microphone input with PyAudio)..."
PORTAUDIO_INSTALLED=false
if [[ "$OS_TYPE" == "Linux" ]]; then
    if [[ "$PKG_MANAGER" == "apt" ]]; then
        # Check if already installed (simple check, might not be perfect)
        if dpkg -s portaudio19-dev &> /dev/null; then
            echo "PortAudio (portaudio19-dev) appears to be installed."
            PORTAUDIO_INSTALLED=true
        else
            echo "PortAudio (portaudio19-dev) not found or status unknown."
            echo "To install PortAudio and its development files on Debian/Ubuntu for PyAudio, run: sudo apt update && sudo apt install portaudio19-dev libasound2-dev"
        fi
    elif [[ "$PKG_MANAGER" == "dnf" ]]; then
        if rpm -q portaudio-devel &> /dev/null; then
            echo "PortAudio (portaudio-devel) appears to be installed."
            PORTAUDIO_INSTALLED=true
        else
            echo "PortAudio (portaudio-devel) not found or status unknown."
            echo "To install PortAudio and its development files on Fedora for PyAudio, run: sudo dnf install portaudio-devel alsa-lib-devel"
        fi
    else
        echo "Could not determine your Linux package manager for PortAudio. Please ensure PortAudio development libraries (e.g., portaudio19-dev or portaudio-devel) and ALSA development libraries (e.g., libasound2-dev or alsa-lib-devel) are installed."
    fi
elif [[ "$OS_TYPE" == "macOS" ]]; then
    if [[ "$PKG_MANAGER" == "brew" ]]; then
        if brew ls --versions portaudio &> /dev/null; then
            echo "PortAudio appears to be installed via Homebrew."
            PORTAUDIO_INSTALLED=true
        else
            echo "PortAudio not found via Homebrew."
            echo "To install PortAudio on macOS with Homebrew, run: brew install portaudio"
        fi
    else
        echo "Homebrew not found. Please install PortAudio using 'brew install portaudio' or ensure it's installed via other means."
    fi
else
    echo "PortAudio check skipped for $OS_TYPE. Ensure it is installed if you plan to use microphone input."
fi

# --- GStreamer Check (Linux for playsound MP3) ---
echo ""
if [[ "$OS_TYPE" == "Linux" ]]; then
    echo "Checking for GStreamer (recommended for MP3 playback with 'playsound' on Linux)..."
    # This is a general recommendation, not a strict 'is installed' check, as playsound might work with partial GStreamer.
    echo "For MP3 playback with the 'playsound' library on Linux, GStreamer and its Python bindings are often required."
    if [[ "$PKG_MANAGER" == "apt" ]]; then
        echo "Recommended GStreamer packages for Debian/Ubuntu:"
        echo "sudo apt update && sudo apt install gir1.2-gstreamer-1.0 gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly python3-gi python3-gst-1.0"
    elif [[ "$PKG_MANAGER" == "dnf" ]]; then
        echo "Recommended GStreamer packages for Fedora:"
        echo "sudo dnf install gstreamer1-devel gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugins-ugly gstreamer1-plugins-bad-free python3-gobject python3-gst-1.0"
    else
        echo "Please ensure GStreamer, its plugins (good, ugly, bad), and Python GObject/Gst bindings are installed using your Linux distribution's package manager."
    fi
else
    echo "GStreamer check is primarily for Linux MP3 playback with 'playsound'. Skipping for $OS_TYPE."
fi

# --- eSpeak Check (Linux for pyttsx3) ---
echo ""
if [[ "$OS_TYPE" == "Linux" ]]; then
    echo "Checking for eSpeak (common backend for 'pyttsx3' local TTS on Linux)..."
    if command -v espeak &> /dev/null; then
        echo "eSpeak appears to be installed."
    else
        echo "eSpeak not found."
        if [[ "$PKG_MANAGER" == "apt" ]]; then
            echo "To install eSpeak on Debian/Ubuntu, run: sudo apt update && sudo apt install espeak"
            echo "ffmpeg and libespeak1 might also be beneficial: sudo apt install ffmpeg libespeak1"
        elif [[ "$PKG_MANAGER" == "dnf" ]]; then
            echo "To install eSpeak on Fedora, run: sudo dnf install espeak"
            echo "ffmpeg might also be beneficial: sudo dnf install ffmpeg" # libespeak might be part of espeak package
        else
            echo "Please install eSpeak using your Linux distribution's package manager if you intend to use pyttsx3."
        fi
    fi
else
    echo "eSpeak check is primarily for Linux users of pyttsx3. Skipping for $OS_TYPE."
fi

# --- C Compiler and CMake Check (for llama-cpp-python) ---
echo ""
echo "Checking for C Compiler (gcc or clang) and CMake (for llama-cpp-python)..."
COMPILER_FOUND=false
if command -v gcc &> /dev/null; then
    echo "gcc (C compiler) found."
    COMPILER_FOUND=true
elif command -v clang &> /dev/null; then
    echo "clang (C compiler) found."
    COMPILER_FOUND=true
else
    echo "Neither gcc nor clang found."
fi

CMAKE_FOUND=false
if command -v cmake &> /dev/null; then
    echo "cmake found."
    CMAKE_FOUND=true
else
    echo "cmake not found."
fi

if [[ "$COMPILER_FOUND" == false || "$CMAKE_FOUND" == false ]]; then
    echo "A C compiler (gcc or clang) and cmake are required to build llama-cpp-python if a pre-built wheel is not available for your system."
    if [[ "$OS_TYPE" == "Linux" ]]; then
        if [[ "$PKG_MANAGER" == "apt" ]]; then
            echo "To install them on Debian/Ubuntu, run: sudo apt update && sudo apt install build-essential cmake"
        elif [[ "$PKG_MANAGER" == "dnf" ]]; then
            echo "To install them on Fedora, run: sudo dnf groupinstall \"Development Tools\" && sudo dnf install cmake" # "Development Tools" includes gcc/g++
        else
            echo "Please install a C compiler (gcc or clang) and cmake using your Linux distribution's package manager."
        fi
    elif [[ "$OS_TYPE" == "macOS" ]]; then
        echo "On macOS, ensure you have Xcode Command Line Tools installed. You can install them by running: xcode-select --install"
        echo "If Homebrew is installed, you can also install cmake via: brew install cmake"
    else
        echo "Please ensure a C compiler and CMake are installed on your system."
    fi
fi
echo "Note: llama-cpp-python often compiles from source during pip install if a pre-built binary ('wheel') is not available for your Python version/platform."
echo "This compilation can take some time and may require specific CMAKE_ARGS for hardware acceleration (e.g., GPU support)."
echo "For GPU/hardware acceleration (CUDA, Metal, OpenBLAS, etc.), please consult the llama-cpp-python documentation for setting CMAKE_ARGS *before* running 'pip install llama-cpp-python' or 'pip install -r requirements.txt'."
echo "You might need to reinstall llama-cpp-python with these arguments if you've already installed it without them."


echo ""
echo "--- Setup Script Finished ---"
echo "Please review the messages above. If any dependencies were reported missing, install them using the provided commands or your system's package manager."
echo "Refer to eidos_assistant/README.md for more details on prerequisites and troubleshooting."
