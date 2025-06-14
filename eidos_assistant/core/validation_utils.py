import subprocess
import os # For Picovoice model path check
# We might need PyAudio and other imports later, adding them as we implement functions

def check_ffmpeg_accessible():
    """
    Checks if ffmpeg is installed and accessible by running 'ffmpeg -version'.

    Returns:
        tuple: (bool, str) where bool is True if ffmpeg is accessible, False otherwise.
               The string contains the ffmpeg version or an error message.
    """
    try:
        process = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, check=True)
        # Extract the first line of the version output for brevity
        version_line = process.stdout.splitlines()[0] if process.stdout else "Version information not found."
        return True, f"FFmpeg is accessible. Version: {version_line}"
    except FileNotFoundError:
        return False, "FFmpeg not found. Please ensure it is installed and in your system's PATH."
    except subprocess.CalledProcessError as e:
        return False, f"FFmpeg found but '-version' command failed. Error: {e.stderr}"
    except Exception as e:
        return False, f"An unexpected error occurred while checking ffmpeg: {str(e)}"

# Placeholder for list_microphones - will be implemented next
def list_microphones():
    return (False, "Microphone listing not yet implemented.")


def list_microphones():
    """
    Lists available audio input devices using PyAudio.

    Returns:
        tuple: (bool, object) where bool indicates success.
               Object is a list of microphone names if successful, or an error message string otherwise.
    """
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        mics = []
        host_api_count = p.get_host_api_count()

        for i in range(host_api_count):
            host_api_info = p.get_host_api_info_by_index(i)
            device_count = host_api_info.get('deviceCount', 0)
            for j in range(device_count):
                device_info = p.get_device_info_by_host_api_device_index(i, j)
                if device_info.get('maxInputChannels', 0) > 0:
                    mics.append(f"Device ID {device_info.get('index')}: {device_info.get('name')} (Host API: {host_api_info.get('name')})")

        p.terminate()

        if not mics:
            return True, "No microphone input devices found. Ensure a microphone is connected and drivers are installed."
        return True, mics
    except ImportError:
        return False, "PyAudio library not found. Please install it (e.g., 'pip install PyAudio'). System dependencies like PortAudio might also be required (see README and setup.sh)."
    except AttributeError as e:
        # This can happen if PortAudio system libraries are missing or not found by PyAudio
        if "_portaudio" in str(e).lower():
             return False, f"PyAudio error (likely missing PortAudio system library or incorrect version): {str(e)}. Please run setup.sh or check README for PortAudio installation."
        return False, f"PyAudio encountered an attribute error: {str(e)}. This might indicate an issue with PyAudio installation or system audio configuration."
    except Exception as e:
        # Catch any other exceptions from PyAudio, such as no host API found
        return False, f"An unexpected error occurred while listing microphones with PyAudio: {str(e)}. Ensure PortAudio system libraries are correctly installed."

# Placeholder for check_picovoice_config - will be implemented later
def check_picovoice_config(voice_io_instance):
    """
    Checks the Picovoice (Porcupine) wake word engine configuration.

    Args:
        voice_io_instance: An instance of the VoiceIO class.

    Returns:
        list: A list of tuples, where each tuple is (bool, str) representing
              a specific check's success status and a message.
    """
    results = []

    if not voice_io_instance:
        results.append((False, "VoiceIO instance not provided."))
        return results

    # 1. Check AccessKey
    if voice_io_instance.picovoice_access_key:
        results.append((True, f"PICOVOICE_ACCESS_KEY is set (value: '***{voice_io_instance.picovoice_access_key[-4:]}').")) # Show last 4 chars for confirmation
    else:
        results.append((False, "PICOVOICE_ACCESS_KEY is NOT set in .env or VoiceIO. Wake word detection will fail."))

    # 2. Check Keyword Paths or Built-in Keywords
    has_keywords = False
    if voice_io_instance.porcupine_keyword_paths:
        results.append((True, f"Custom Porcupine keyword paths are configured: {voice_io_instance.porcupine_keyword_paths}"))
        has_keywords = True
        # Check if custom keyword files exist
        for path in voice_io_instance.porcupine_keyword_paths:
            if os.path.exists(path):
                results.append((True, f"  Keyword file found: {path}"))
            else:
                results.append((False, f"  Keyword file NOT found: {path}"))

    if voice_io_instance.porcupine_builtin_keywords:
        results.append((True, f"Built-in Porcupine keywords are configured: {voice_io_instance.porcupine_builtin_keywords}"))
        has_keywords = True

    if not has_keywords:
        results.append((False, "No Porcupine keyword paths or built-in keywords are configured. Wake word detection requires at least one."))

    # 3. Check Model Path (if custom)
    if voice_io_instance.porcupine_model_path: # If it's None or empty, Porcupine uses the default model
        results.append((True, f"Custom Porcupine model path is configured: {voice_io_instance.porcupine_model_path}"))
        if os.path.exists(voice_io_instance.porcupine_model_path):
            results.append((True, f"  Custom model file found: {voice_io_instance.porcupine_model_path}"))
        else:
            results.append((False, f"  Custom model file NOT found: {voice_io_instance.porcupine_model_path}"))
    else:
        results.append((True, "Using default Porcupine model file (no custom path set)."))

    # 4. Check if Porcupine instance was created (basic check, VoiceIO tries to init it)
    # This is an indirect check of whether the settings *could* work.
    # A more direct test would be to try initializing Porcupine here, but that might be too much for a validation script
    # if it's already initialized in VoiceIO. For now, we rely on VoiceIO's own initialization attempt.
    if voice_io_instance.porcupine:
        results.append((True, "Porcupine engine instance exists in VoiceIO (likely initialized successfully)."))
    else:
        results.append((False, "Porcupine engine instance does NOT exist in VoiceIO. This could be due to missing AccessKey, keyword files, model file, or other initialization errors. Check VoiceIO logs at startup."))

    return results

def check_llm_setup(llm_engine_instance):
    """
    Checks the configured LLM engine setup (OpenAI client or local Llama CPP).

    Args:
        llm_engine_instance: An instance of the LLMEngine class.

    Returns:
        tuple: (bool, str) where bool is True if the setup seems OK, False otherwise.
               The string contains a success or error/status message.
    """
    if not llm_engine_instance:
        return False, "LLMEngine instance not provided to check_llm_setup."

    engine_type = getattr(llm_engine_instance, 'llm_engine_type', 'unknown')

    if engine_type == "openai":
        if not llm_engine_instance.client:
            return False, (f"OpenAI client not initialized. "
                           f"API Base URL configured: {getattr(llm_engine_instance, 'api_base_url', 'Not Set')}. "
                           f"Check .env (LLM_ENGINE_TYPE='openai', LLM_API_BASE_URL) and ensure the server is running.")
        try:
            llm_engine_instance.client.models.list() # Simple API call to check connectivity
            return True, f"Successfully connected to OpenAI compatible LLM server at {llm_engine_instance.api_base_url}."
        except Exception as e:
            error_message = str(e)
            if "connection refused" in error_message.lower():
                return False, f"Connection to OpenAI compatible LLM server at {llm_engine_instance.api_base_url} refused. Is the server running?"
            return False, f"Failed to connect or communicate with OpenAI compatible LLM server at {llm_engine_instance.api_base_url}. Error: {error_message}"

    elif engine_type == "local_llama_cpp":
        if getattr(llm_engine_instance, 'Llama', None) is None: # Check if Llama class was imported
            return False, "Llama CPP library (llama_cpp) not imported. Cannot use 'local_llama_cpp' engine. Please install it."
        if not llm_engine_instance.local_llm:
            model_path = getattr(llm_engine_instance, 'local_llm_model_path', 'Not Set')
            if not model_path or model_path == 'Not Set':
                 return False, ("Llama CPP model not initialized. LOCAL_LLM_MODEL_PATH is not set in .env.")
            elif not os.path.exists(model_path):
                 return False, (f"Llama CPP model not initialized. Model file not found at LOCAL_LLM_MODEL_PATH: {model_path}. "
                                f"Ensure the path is correct and the GGUF model file exists.")
            return False, (f"Llama CPP model not initialized. Model path: {model_path}. "
                           f"This could be due to an error during LLMEngine setup (e.g., model loading failed). Check console logs.")

        # Basic check: try to get a property from the loaded model or just confirm it exists
        try:
            # Accessing a property like model_path from the Llama object itself isn't standard.
            # Instead, we can infer it's loaded if self.local_llm exists and no exceptions occurred during its init.
            # A more robust check would be to load a tiny dummy model, but that's too complex for validation.
            # For now, if self.local_llm object exists, we assume it loaded correctly.
            # The LLMEngine's __init__ should have logged errors if loading failed.
            return True, (f"Llama CPP model appears to be initialized. "
                          f"Model path: {llm_engine_instance.local_llm_model_path}, "
                          f"GPU Layers: {llm_engine_instance.local_llm_n_gpu_layers}, "
                          f"Context (n_ctx): {llm_engine_instance.local_llm_n_ctx}, "
                          f"Chat Format: {llm_engine_instance.local_llm_chat_format or 'auto'}")
        except Exception as e: # Should not happen if local_llm object exists and was checked
             return False, f"Llama CPP model found but failed a basic check: {e}"


    else:
        return False, f"LLM_ENGINE_TYPE is set to an unknown type: '{engine_type}'. Valid options are 'openai' or 'local_llama_cpp'."

def check_tts_setup(voice_io_instance):
    """
    Checks the configured TTS engine setup (Kokoro server or local pyttsx3).

    Args:
        voice_io_instance: An instance of the VoiceIO class, which holds the TTS config.

    Returns:
        tuple: (bool, str) where bool is True if the setup seems OK, False otherwise.
               The string contains a success or error/status message.
    """
    if not voice_io_instance:
        return False, "VoiceIO instance not provided to check_tts_setup."

    engine_type = getattr(voice_io_instance, 'tts_engine_type', 'unknown')

    if engine_type == "kokoro":
        if not voice_io_instance.tts_client:
            return False, (f"Kokoro TTS client not initialized. "
                           f"API Base URL configured: {getattr(voice_io_instance, 'kokoro_base_url', 'Not Set')}. "
                           f"Check .env (TTS_ENGINE='kokoro', KOKORO_TTS_BASE_URL) and ensure the Kokoro server is running.")
        try:
            # Attempt a simple API call, e.g., listing voices if supported, or just a health check.
            # For OpenAI client, often a simple model list or similar lightweight call can work.
            # Kokoro-FastAPI's /v1/voices endpoint:
            response = voice_io_instance.tts_client.get("voices") # Assumes tts_client is an httpx client for Kokoro
            response.raise_for_status() # Check for HTTP errors
            return True, f"Successfully connected to Kokoro TTS server at {voice_io_instance.kokoro_base_url} and received voice list."
        except Exception as e:
            error_message = str(e)
            if "connection refused" in error_message.lower():
                return False, f"Connection to Kokoro TTS server at {voice_io_instance.kokoro_base_url} refused. Is the server running?"
            return False, f"Failed to connect or communicate with Kokoro TTS server at {voice_io_instance.kokoro_base_url}. Error: {error_message}"

    elif engine_type == "local_pyttsx3":
        if not voice_io_instance.pyttsx3_engine:
            # Check if pyttsx3 module itself failed to import
            if 'pyttsx3' in globals() and globals()['pyttsx3'] is None:
                 return False, "pyttsx3 library failed to import. Please ensure it is installed correctly (pip install pyttsx3)."
            return False, ("pyttsx3 engine not initialized in VoiceIO. "
                           "This could be due to an initialization error during VoiceIO setup. "
                           "Check console logs. On Linux, ensure 'espeak' is installed ('sudo apt install espeak').")
        try:
            # Try to get a property as a basic check that the engine is alive
            # voices = voice_io_instance.pyttsx3_engine.getProperty('voices')
            # if not voices: # Some systems might return empty list but not error
            #     return True, "pyttsx3 engine is initialized, but no voices were found. TTS might not work."
            # For a simpler check, just confirm engine object exists.
            # A more robust check would be to try synthesizing a very short silent audio, but that's too complex here.
            voice_io_instance.pyttsx3_engine.getProperty('rate') # Simple call to see if it errors
            return True, "pyttsx3 engine is initialized. Ensure your OS has TTS capabilities (e.g., SAPI5 on Win, NSSpeech on macOS, eSpeak on Linux)."
        except Exception as e:
            return False, f"pyttsx3 engine appears initialized but failed a basic check. Error: {e}. Ensure OS TTS components are functional."

    else:
        return False, f"TTS_ENGINE is set to an unknown type: '{engine_type}'. Valid options are 'kokoro' or 'local_pyttsx3'."
