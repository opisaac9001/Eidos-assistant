import os
from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError
import whisper # Ensure whisper import is present
import pvporcupine # Added for Wake Word
from playsound import playsound, PlaysoundException # Added for playback
import pyaudio # For microphone input
import wave    # For saving recorded audio for STT
import struct  # For converting audio bytes to int16 samples
import time    # For STT recording duration
import subprocess # For ffmpeg check in speech_to_text


# Construct path to .env in the eidos_assistant/ directory
# Assumes voice_io.py is in eidos_assistant/interface/
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if not load_dotenv(dotenv_path=dotenv_path):
    print(f"Warning: voice_io.py - Could not load .env file from {dotenv_path}")
else:
    print(f"Debug: voice_io.py - Successfully loaded .env file from {dotenv_path}")

try:
    import pyttsx3
except ImportError:
    print("VoiceIO Warning: pyttsx3 library not found. Local TTS via pyttsx3 will be unavailable.")
    pyttsx3 = None # Ensure pyttsx3 is defined so checks don't break if not installed


class VoiceIO:
    def __init__(self):
        """Initializes the VoiceIO system, configured for selected TTS engine."""
        self.tts_engine_type = os.getenv("TTS_ENGINE", "kokoro").lower()
        self.pyttsx3_engine = None
        self.tts_client = None # For Kokoro

        if self.tts_engine_type == "kokoro":
            self.kokoro_base_url = os.getenv("KOKORO_TTS_BASE_URL", "http://localhost:8880/v1")
            self.kokoro_api_key = os.getenv("KOKORO_TTS_API_KEY", "not-needed")
            self.default_voice = os.getenv("KOKORO_TTS_VOICE", "af_sky")
            print(f"VoiceIO: Initializing TTS engine: Kokoro (URL: {self.kokoro_base_url}, Default Voice: {self.default_voice})")
            try:
                self.tts_client = OpenAI(base_url=self.kokoro_base_url, api_key=self.kokoro_api_key)
                print("VoiceIO: OpenAI client for Kokoro TTS initialized successfully.")
            except Exception as e:
                self.tts_client = None
                print(f"VoiceIO Error: Failed to initialize OpenAI client for Kokoro TTS: {e}")
        elif self.tts_engine_type == "local_pyttsx3":
            print(f"VoiceIO: Initializing TTS engine: local_pyttsx3")
            if pyttsx3:
                try:
                    self.pyttsx3_engine = pyttsx3.init()
                    if self.pyttsx3_engine:
                         print("VoiceIO: pyttsx3 engine initialized successfully.")
                    else:
                         print("VoiceIO Error: pyttsx3.init() returned None. Cannot use local_pyttsx3.")
                except Exception as e:
                    self.pyttsx3_engine = None
                    print(f"VoiceIO Error: Failed to initialize pyttsx3 engine: {e}")
                    print("  Ensure prerequisites for pyttsx3 are met (e.g., espeak on Linux).")
            else:
                print("VoiceIO Error: pyttsx3 library was not imported. Cannot use 'local_pyttsx3' engine.")
        else:
            print(f"VoiceIO Warning: Unknown TTS_ENGINE type '{self.tts_engine_type}'. No TTS will be active.")

        # STT Initialization (remains the same)
        print("VoiceIO: Initializing STT (Whisper)...")
        try:
            # Consider making self.stt_model_name configurable via .env
            self.stt_model_name = os.getenv("WHISPER_MODEL_NAME", "base.en")
            print(f"VoiceIO: Attempting to load Whisper STT model '{self.stt_model_name}'...")
            self.stt_model = whisper.load_model(self.stt_model_name)
            print(f"VoiceIO: Whisper STT model '{self.stt_model_name}' loaded successfully.")
        except ImportError: # Specifically catch if whisper is not installed
            self.stt_model = None
            print("VoiceIO Error: 'openai-whisper' library not found. Please install it (e.g., pip install openai-whisper).")
            print("STT functionality will be unavailable.")
        except Exception as e: # Catch other errors like model download issues, torch issues
            self.stt_model = None
            print(f"VoiceIO Error: Failed to load Whisper STT model '{self.stt_model_name}': {e}")
            print("This could be due to issues with 'torch', 'ffmpeg' not being installed, or problems downloading model files.")
            print("STT functionality will be unavailable.")
        # Ensure self.stt_model is defined.
        if not hasattr(self, 'stt_model'): # Should be redundant now but safe.
            self.stt_model = None


        # --- Porcupine Initialization ---
        print("VoiceIO: Attempting to initialize Porcupine Wake Word Engine...")
        self.porcupine = None
        self.porcupine_frame_length = None # Will be set by Porcupine if successful
        self.porcupine_keywords_list = []  # To store the actual keywords being used for logging/display
        self.picovoice_access_key = os.getenv("PICOVOICE_ACCESS_KEY") # Store for validation checks
        self.porcupine_builtin_keywords = os.getenv("PORCUPINE_BUILTIN_KEYWORDS", "picovoice")
        self.porcupine_keyword_paths_str = os.getenv("PORCUPINE_KEYWORD_PATHS", "")
        self.porcupine_model_path = os.getenv("PORCUPINE_MODEL_PATH", None) # Already correctly defaults to None
        self.porcupine_sensitivities_str = os.getenv("PORCUPINE_SENSITIVITIES", "")


        try:
            if not self.picovoice_access_key or self.picovoice_access_key == "YOUR_PICOVOICE_ACCESS_KEY_HERE":
                print("VoiceIO Warning: PICOVOICE_ACCESS_KEY not set in .env or is a placeholder. Porcupine will not initialize.")
                raise ValueError("Missing or placeholder PICOVOICE_ACCESS_KEY")

            keywords = []
            if self.porcupine_builtin_keywords:
                keywords.extend([k.strip() for k in self.porcupine_builtin_keywords.split(',') if k.strip()])

            # Store parsed paths for validation, even if some don't exist yet.
            self.porcupine_keyword_paths = []
            if self.porcupine_keyword_paths_str:
                 self.porcupine_keyword_paths.extend([p.strip() for p in self.porcupine_keyword_paths_str.split(',') if p.strip()])


            if not keywords and not self.porcupine_keyword_paths:
                print("VoiceIO Warning: No built-in keywords or keyword_paths provided for Porcupine. Porcupine will not initialize.")
                raise ValueError("No keywords or keyword_paths for Porcupine")

            # Used for display and sensitivity matching
            current_keyword_identifiers = keywords + [os.path.basename(p) for p in self.porcupine_keyword_paths]


            sensitivities = None
            if self.porcupine_sensitivities_str:
                try:
                    sensitivities = [float(s.strip()) for s in self.porcupine_sensitivities_str.split(',') if s.strip()]
                    if len(sensitivities) != len(current_keyword_identifiers):
                        print(f"VoiceIO Warning: Number of sensitivities ({len(sensitivities)}) does not match number of keywords ({len(current_keyword_identifiers)}). Using default sensitivities.")
                        sensitivities = None
                except ValueError:
                    print("VoiceIO Warning: Invalid format for PORCUPINE_SENSITIVITIES. Using default sensitivities.")
                    sensitivities = None

            init_args = {"access_key": self.picovoice_access_key}
            if keywords:
                init_args["keywords"] = keywords
            if self.porcupine_keyword_paths: # Use the parsed list
                init_args["keyword_paths"] = self.porcupine_keyword_paths
            if self.porcupine_model_path and self.porcupine_model_path.strip():
                init_args["model_path"] = self.porcupine_model_path.strip()
            if sensitivities:
                init_args["sensitivities"] = sensitivities

            # Actual initialization
            self.porcupine = pvporcupine.create(**init_args)
            self.porcupine_frame_length = self.porcupine.frame_length
            self.porcupine_keywords_list = current_keyword_identifiers # Store the ones actually used
            print(f"VoiceIO: Porcupine initialized successfully with keywords: {self.porcupine_keywords_list}, frame_length: {self.porcupine_frame_length}.")

        except ImportError:
            print("VoiceIO Error: 'pvporcupine' library not found. Please install it (e.g., pip install pvporcupine). Wake word detection will be unavailable.")
        except pvporcupine.PorcupineError as pe:
            print(f"VoiceIO Error: Porcupine engine error: {pe}. This could be due to an invalid AccessKey, missing/corrupt model or keyword files, or incorrect audio device settings.")
        except ValueError as ve: # For our config checks
            print(f"VoiceIO Error: Porcupine configuration error: {ve}")
        except Exception as e: # Catch-all for other unexpected init errors
            print(f"VoiceIO Error: Failed to initialize Porcupine: {e}. Wake word detection will be unavailable.")
            # self.porcupine remains None

        # --- PyAudio Attributes & Initialization ---
        self.pyaudio_instance = None
        self.audio_stream = None
        self.audio_stream_sample_rate = 16000 # Standard for Porcupine/Whisper
        self.audio_stream_channels = 1 # Mono
        # self.porcupine_frame_length should be set if Porcupine initialized successfully
        # If not, audio streaming for wake word won't work properly.
        self.audio_chunk_size = getattr(self.porcupine, 'frame_length', 512)


    def start_audio_stream(self) -> bool:
        """Initializes PyAudio and opens an audio input stream."""
        if not self.porcupine: # Porcupine is essential for frame_length
            print("VoiceIO Error: Porcupine not initialized. Cannot start audio stream as frame length is unknown for wake word detection.")
            return False
        if self.audio_stream and self.audio_stream.is_active():
            print("VoiceIO Info: Audio stream is already active.")
            return True

        print("VoiceIO: Initializing PyAudio to open audio stream...")
        try:
            self.pyaudio_instance = pyaudio.PyAudio() # Initialize PyAudio
            self.audio_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16, # Standard format for voice
                channels=self.audio_stream_channels,
                rate=self.audio_stream_sample_rate,
                input=True, # We are recording
                frames_per_buffer=self.audio_chunk_size # Critical for Porcupine
            )
            print(f"VoiceIO: Audio stream started successfully (Rate: {self.audio_stream_sample_rate}, Channels: {self.audio_stream_channels}, Chunk: {self.audio_chunk_size}).")
            return True
        except ImportError:
            print("VoiceIO Error: PyAudio library not found. Cannot start audio stream. Please install 'PyAudio'.")
            self.pyaudio_instance = None
            self.audio_stream = None
            return False
        except IOError as ioe:
            print(f"VoiceIO Error: Failed to open audio stream due to IOError: {ioe}.")
            print("  This often means no microphone is connected, or PortAudio is misconfigured or missing system libraries (e.g., portaudio19-dev on Linux).")
            print("  Try running `/validate_setup` or `./setup.sh` for system dependency checks.")
            if self.pyaudio_instance: self.pyaudio_instance.terminate()
            self.pyaudio_instance = None
            self.audio_stream = None
            return False
        except Exception as e:
            print(f"VoiceIO Error: Could not start PyAudio stream due to an unexpected error: {e}. Check microphone and PortAudio setup.")
            if self.pyaudio_instance: self.pyaudio_instance.terminate()
            self.pyaudio_instance = None
            self.audio_stream = None
            return False

    def read_audio_stream_chunk(self) -> list[int] | None:
        """Reads a chunk of audio data from the stream, formatted for Porcupine (list of int16 PCM samples)."""
        if not self.audio_stream or not self.audio_stream.is_active():
            # This can be noisy if called repeatedly when stream is intentionally down (e.g., during STT).
            # print("VoiceIO Info: Audio stream not active or not initialized. Cannot read chunk.")
            return None
        try:
            data_bytes = self.audio_stream.read(self.audio_chunk_size, exception_on_overflow=False)
            num_samples = len(data_bytes) // 2
            if num_samples * 2 != len(data_bytes):
                print(f"VoiceIO Warning: Read an incomplete frame. Expected {self.audio_chunk_size*2} bytes, got {len(data_bytes)}.")
                return None
            pcm_data = struct.unpack('%dh' % num_samples, data_bytes)
            return list(pcm_data)
        except IOError as e:
            print(f"VoiceIO Error: PyAudio stream read IOError: {e}. The audio device might have been disconnected or encountered an issue.")
            self.stop_audio_stream() # Attempt to gracefully stop on error
            return None
        except Exception as e:
            print(f"VoiceIO Error: Unexpected error reading audio stream: {e}")
            return None

    def stop_audio_stream(self):
        """Stops and closes the audio stream and terminates PyAudio instance if it exists."""
        if self.audio_stream:
            try:
                if self.audio_stream.is_active():
                    self.audio_stream.stop_stream()
                    print("VoiceIO: Audio stream stopped.")
                self.audio_stream.close()
                print("VoiceIO: Audio stream closed.")
            except Exception as e:
                print(f"VoiceIO Error: Exception during audio stream stop/close: {e}")
            finally:
                self.audio_stream = None

        if self.pyaudio_instance:
            try:
                self.pyaudio_instance.terminate()
                print("VoiceIO: PyAudio instance terminated.")
            except Exception as e:
                print(f"VoiceIO Error: Exception during PyAudio instance termination: {e}")
            finally:
                self.pyaudio_instance = None

    def record_audio_for_stt(self, duration_seconds: int, temp_filename: str = "temp_stt_audio.wav") -> str | None:
        """
        Records audio from the microphone for a specified duration and saves it to a WAV file.
        Returns the absolute path to the saved file on success, None on failure.
        """
        print(f"VoiceIO: Starting {duration_seconds}s audio recording for STT, attempting to save to {temp_filename}...")

        try:
            import pyaudio # Check PyAudio availability
        except ImportError:
            print("VoiceIO Error: PyAudio library not found. Cannot record audio for STT. Please install 'PyAudio'.")
            return None

        record_pa_instance = None
        record_audio_stream = None
        frames = []

        try:
            record_pa_instance = pyaudio.PyAudio()
            record_audio_stream = record_pa_instance.open(
                format=pyaudio.paInt16,
                channels=self.audio_stream_channels,
                rate=self.audio_stream_sample_rate,
                input=True,
                frames_per_buffer=self.audio_chunk_size
            )
            print("VoiceIO: Microphone stream opened successfully for STT recording.")
        except IOError as ioe:
            print(f"VoiceIO Error: Failed to open microphone stream for STT recording due to IOError: {ioe}")
            print("  Ensure a microphone is connected and permitted, and PortAudio is correctly set up (e.g., portaudio19-dev on Linux).")
            if record_pa_instance: record_pa_instance.terminate()
            return None
        except Exception as e:
            print(f"VoiceIO Error: Could not open microphone stream for STT recording: {e}")
            if record_pa_instance: record_pa_instance.terminate()
            return None

        try:
            num_chunks_to_record = int((self.audio_stream_sample_rate / self.audio_chunk_size) * duration_seconds)
            print(f"VoiceIO: Recording {num_chunks_to_record} chunks...")
            for _ in range(num_chunks_to_record):
                data_bytes = record_audio_stream.read(self.audio_chunk_size, exception_on_overflow=False)
                frames.append(data_bytes)
            print("VoiceIO: Recording finished.")
        except IOError as e:
            print(f"VoiceIO Error during STT audio recording (read from stream): {e}")
            return None
        finally:
            if record_audio_stream:
                try:
                    record_audio_stream.stop_stream()
                    record_audio_stream.close()
                except Exception as e_close: print(f"VoiceIO Warning: Error closing STT recording stream: {e_close}")
            if record_pa_instance:
                try:
                    record_pa_instance.terminate()
                except Exception as e_term: print(f"VoiceIO Warning: Error terminating PyAudio for STT recording: {e_term}")

        if not frames:
            print("VoiceIO Error: No audio frames recorded for STT.")
            return None

        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            abs_temp_filename = os.path.join(project_root, temp_filename)
            with wave.open(abs_temp_filename, 'wb') as wf:
                wf.setnchannels(self.audio_stream_channels)
                # Use PyAudio's method to get sample size for paInt16 (should be 2 bytes)
                wf.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
                wf.setframerate(self.audio_stream_sample_rate)
                wf.writeframes(b''.join(frames))
            print(f"VoiceIO: STT audio successfully saved to {abs_temp_filename}")
            return abs_temp_filename
        except Exception as e:
            print(f"VoiceIO Error: Failed to save STT audio to WAV file '{abs_temp_filename}': {e}")
            return None

    def text_to_speech(self, text: str, voice: str = None, output_filename: str = "eidos_tts_output.mp3") -> bool:
        """
        Converts text to speech using Kokoro-FastAPI (OpenAI compatible) and saves to a file.
        Returns True on success (speech generated), False on failure.
        Playback status is printed internally.
        """
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        abs_output_filename = os.path.join(project_root, output_filename)
        output_dir = os.path.dirname(abs_output_filename)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        tts_generated_successfully = False

        if self.tts_engine_type == "kokoro":
            if not self.tts_client:
                print("VoiceIO Error: Kokoro TTS client not initialized. Check TTS server URL/config in your .env file and ensure the TTS server is running.")
                return False
            actual_voice = voice if voice else self.default_voice
            try:
                print(f"VoiceIO (Kokoro): Requesting TTS for text: '{text[:50]}...' with voice: {actual_voice}")
                response = self.tts_client.audio.speech.create(
                    model="kokoro", input=text, voice=actual_voice, response_format="mp3"
                )
                response.stream_to_file(abs_output_filename)
                print(f"VoiceIO (Kokoro): Speech successfully saved to {abs_output_filename}")
                tts_generated_successfully = True
            except APIConnectionError as e:
                print(f"VoiceIO (Kokoro) TTS Error: Failed to connect to API at {self.kokoro_base_url}. Details: {e}")
                return False
            except APIStatusError as e:
                print(f"VoiceIO (Kokoro) TTS Error: API returned an error: Status {e.status_code}, Response: {e.response}. Check server logs and your request.")
                return False
            except Exception as e:
                print(f"VoiceIO (Kokoro) TTS Error: An unexpected error: {e}.")
                return False

        elif self.tts_engine_type == "local_pyttsx3":
            if not self.pyttsx3_engine:
                print("VoiceIO Error: pyttsx3 engine not initialized. Cannot generate speech.")
                return False
            try:
                print(f"VoiceIO (pyttsx3): Requesting TTS for text: '{text[:50]}...'")
                self.pyttsx3_engine.save_to_file(text, abs_output_filename)
                self.pyttsx3_engine.runAndWait() # Blocks until speaking/saving is complete
                print(f"VoiceIO (pyttsx3): Speech successfully saved to {abs_output_filename}")
                tts_generated_successfully = True
            except Exception as e:
                print(f"VoiceIO (pyttsx3) Error: Failed to generate speech: {e}")
                return False
        else:
            print(f"VoiceIO Error: Unknown or uninitialized TTS_ENGINE type '{self.tts_engine_type}'. Cannot generate speech.")
            return False

        if tts_generated_successfully:
            # Play the sound (common to both engines if file saved)
            print(f"VoiceIO: Attempting to play speech from {abs_output_filename}...")
            try:
                playsound(abs_output_filename)
                print(f"VoiceIO: Finished playing {abs_output_filename}.")
            except PlaysoundException as pse:
                error_msg = f"VoiceIO Warning: Error playing speech with playsound: {pse}."
                import sys
                if sys.platform.startswith("linux"):
                    error_msg += " This might be due to missing GStreamer plugins for MP3 playback on Linux. Please ensure GStreamer and relevant plugins (e.g., good, ugly) are installed."
                print(error_msg)
            except Exception as e:
                print(f"VoiceIO Warning: An unexpected error occurred during audio playback: {e}")
            return True

            return False

    def speech_to_text(self, audio_file_path: str) -> str: # Modified to take audio_file_path
        """
        Transcribes audio from a file path using Whisper.
        Returns the transcribed text, or an empty string on failure.
        NOTE: This method is untested by the AI assistant due to environment limitations.
        The user must ensure 'openai-whisper' and 'ffmpeg' are installed.
        """
        # 1. Check if STT model is loaded
        if not self.stt_model:
            return "[STT Model Not Loaded: Ensure openai-whisper and its dependencies (like PyTorch) are correctly installed. Check initial startup logs for errors.]"

        # 2. Check for ffmpeg accessibility
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, check=True, timeout=5) # Added timeout
        except FileNotFoundError:
            return "[STT Error: ffmpeg not found. Please ensure ffmpeg is installed and in your system's PATH.]"
        except subprocess.TimeoutExpired:
            return "[STT Error: ffmpeg check timed out. Ensure ffmpeg is responsive.]"
        except (subprocess.CalledProcessError, Exception) as e: # Catch other ffmpeg related errors
            return f"[STT Error: ffmpeg found but may be misconfigured or produced an error during version check: {str(e)[:100]}...]"

        # 3. Check if audio file exists
        if not os.path.exists(audio_file_path):
            return f"[Audio File Not Found: '{audio_file_path}']"

        # 4. Attempt transcription
        try:
            print(f"VoiceIO: Attempting to transcribe audio from '{audio_file_path}' using Whisper model '{self.stt_model_name}'...")
            # Consider making fp16 configurable if GPU is available
            result = self.stt_model.transcribe(audio_file_path, fp16=False)
            transcribed_text = result["text"]
            print(f"VoiceIO STT: Transcription complete. Text: '{transcribed_text[:100]}...'")
            return transcribed_text.strip()
        except Exception as e:
            return f"[STT Transcription Error: {str(e)[:150]}... Check audio file format and Whisper logs.]"

    def process_audio_chunk_for_wakeword(self, audio_chunk_pcm: list[int]) -> int:
        """
        Processes a chunk of audio data for wake word detection.
        audio_chunk_pcm: A list/tuple of int16 PCM samples. Must be of length porcupine.frame_length.
        Returns: Index of the detected keyword if a wake word is detected (e.g., 0, 1, ...),
                 -1 otherwise.
        NOTE: This method is untested by the AI assistant. User must ensure correct setup.
        """
        if not self.porcupine:
            # This being printed repeatedly can be noisy if Porcupine intentionally wasn't initialized.
            # print("VoiceIO Debug: Porcupine not initialized, skipping wake word processing.")
            return -1

        if len(audio_chunk_pcm) != self.porcupine_frame_length:
            # This is a critical error if it occurs, as Porcupine expects exact frame lengths.
            print(f"VoiceIO Error: Audio chunk length ({len(audio_chunk_pcm)}) does not match Porcupine frame length ({self.porcupine_frame_length}). Input will be ignored by Porcupine.")
            return -1

        try:
            keyword_index = self.porcupine.process(audio_chunk_pcm)
            return keyword_index
        except pvporcupine.PorcupineError as e:
            print(f"VoiceIO Error: Porcupine process error during audio processing: {e}. This might indicate an issue with the audio data or Porcupine engine state.")
            return -1
        except Exception as e: # Catch any other unexpected error
            print(f"VoiceIO Error: Unexpected error during Porcupine.process(): {e}")
            return -1

    def delete_porcupine(self):
        """Releases resources acquired by Porcupine."""
        if self.porcupine:
            print("VoiceIO: Deleting Porcupine instance...")
            try:
                self.stop_audio_stream() # Ensure stream is stopped if porcupine was using it
                self.porcupine.delete()
                self.porcupine = None
                print("VoiceIO: Porcupine instance deleted.")
            except Exception as e:
                print(f"VoiceIO Error: Failed to delete Porcupine instance: {e}")
        else: # If porcupine wasn't even initialized, ensure any stray stream is closed.
            self.stop_audio_stream()


if __name__ == '__main__':
    print("\nTesting VoiceIO module (TTS with Kokoro-FastAPI)...")
    # Ensure .env is in the project root (eidos_assistant/) for this test to pick it up.
    # The load_dotenv call at the top of the script should handle it.

    voice_interface = VoiceIO()

    if not voice_interface.tts_client:
        print("Skipping TTS test as client failed to initialize.")
    else:
        print(f"Using Kokoro Server: {voice_interface.kokoro_base_url}")
        print(f"Default voice: {voice_interface.default_voice}")

        test_text = "Hello from Eidos Assistant! This is a test of the Kokoro Text to Speech system."
        # Output file will be in eidos_assistant/ directory for this test
        output_file = "test_tts_output.mp3"

        print(f"Attempting to generate speech for: '{test_text}'")
        success = voice_interface.text_to_speech(test_text, output_filename=output_file)

        if success:
            print(f"Test speech generated successfully: {output_file}")
            print(f"Please check for an audio file named '{output_file}' in the eidos_assistant directory.")
            # Clean up the test file

            # Construct absolute path for removal, consistent with how it's created
            project_root_for_cleanup = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            abs_output_file_for_cleanup = os.path.join(project_root_for_cleanup, output_file)

            if os.path.exists(abs_output_file_for_cleanup):
                # os.remove(abs_output_file_for_cleanup) # Commented out for now so user can check file
                print(f"Cleanup: '{abs_output_file_for_cleanup}' would be removed here in a real test suite.")
        else:
            print("Test speech generation failed.")
            print("Ensure your Kokoro-FastAPI server is running and accessible at the configured URL,")
            print(f"and the voice '{voice_interface.default_voice}' is valid.")

    print("\nVoiceIO module TTS test complete.") # This was the end of the original __main__

    # --- STT (Whisper) Test Section (Untested by Assistant) ---
    print("\n--- STT (Whisper) Test Section (Untested by Assistant) ---")
    if not voice_interface.stt_model:
        print("VoiceIO STT: Skipping STT test as Whisper model did not load (see errors above).")
        print("VoiceIO STT: Ensure 'openai-whisper' and 'ffmpeg' are installed in your Python environment.")
    else:
        print("VoiceIO STT: Model appears loaded. To test, provide a valid audio file path.")
        # Example of how a user might test:
        # test_audio_file = "path/to/your/audiofile.wav"
        # print(f"VoiceIO STT: If you had an audio file at '{test_audio_file}', you could test with:")
        # print(f"transcribed_text = voice_interface.speech_to_text(test_audio_file)")
        # print(f"Result: {{transcribed_text}}")

        # Simulating a file not found error for the test structure:
        print("\nVoiceIO STT: Testing with a non-existent file path...")
        non_existent_file = "non_existent_audio_sample.wav"
        transcription_attempt = voice_interface.speech_to_text(non_existent_file)
        print(f"VoiceIO STT: Attempt to transcribe '{non_existent_file}' returned: '{transcription_attempt}' (expected '[Audio File Not Found]').")

    # --- Porcupine Wake Word Test Section (Untested by Assistant) ---
    print("\n--- Porcupine Wake Word Test Section (Untested by Assistant) ---")
    if not voice_interface.porcupine:
        print("VoiceIO Porcupine: Skipping wake word test as Porcupine did not initialize (see errors above).")
        print("VoiceIO Porcupine: Ensure 'pvporcupine' is installed, PICOVOICE_ACCESS_KEY is valid, and keyword/model paths are correct.")
    else:
        print(f"VoiceIO Porcupine: Initialized with keywords: {voice_interface.porcupine_keywords_list}")
        print(f"VoiceIO Porcupine: Expected audio frame length: {voice_interface.porcupine_frame_length}")
        # Example of how a user might test with a dummy audio frame:
        # This requires a source of audio data, e.g., from a microphone or file,
        # correctly formatted as a list of int16 PCM samples of porcupine.frame_length.
        print("VoiceIO Porcupine: To test, you would need to feed audio frames of the correct length.")
        # dummy_frame = [0] * voice_interface.porcupine_frame_length
        # keyword_idx = voice_interface.process_audio_chunk_for_wakeword(dummy_frame)
        # print(f"VoiceIO Porcupine: Processing dummy frame returned: {keyword_idx} (expected -1 for silence)")

    # --- PyAudio Streaming Test Section (Conceptual - Untested by Assistant) ---
    print("\n--- PyAudio Streaming Test Section (Conceptual - Untested by Assistant) ---")
    if voice_interface.porcupine and voice_interface.porcupine_frame_length: # Need frame length for stream
        print("VoiceIO PyAudio: Attempting to test audio stream start/stop (no actual reading).")
        if voice_interface.start_audio_stream():
            print("VoiceIO PyAudio: Stream started conceptually.")
            # In a real test, you might try:
            # chunk = voice_interface.read_audio_stream_chunk()
            # if chunk: print(f"Read {len(chunk)} samples.")
            voice_interface.stop_audio_stream()
            print("VoiceIO PyAudio: Stream stopped conceptually.")
        else:
            print("VoiceIO PyAudio: Failed to start stream conceptually. Check PyAudio/PortAudio installation and microphone.")

        print("\nVoiceIO PyAudio: Attempting to test STT recording (conceptual).")
        # Test recording will try to create file in project root (eidos_assistant/)
        temp_stt_file = voice_interface.record_audio_for_stt(duration_seconds=1, temp_filename="test_stt_rec.wav")
        if temp_stt_file and os.path.exists(temp_stt_file):
            print(f"VoiceIO PyAudio: STT recording saved to {temp_stt_file} conceptually.")
            os.remove(temp_stt_file) # Cleanup test file
            print(f"VoiceIO PyAudio: Cleaned up {temp_stt_file}.")
        elif temp_stt_file is None:
             print(f"VoiceIO PyAudio: STT recording failed conceptually.")
        else: # temp_stt_file is a path but file does not exist
             print(f"VoiceIO PyAudio: STT recording returned path {temp_stt_file} but file not found.")
    else:
        print("VoiceIO PyAudio: Skipping audio stream tests as Porcupine (needed for frame_length) or PyAudio did not initialize (or PyAudio not installed).")

    # Ensure final cleanup if user tests interactively
    voice_interface.delete_porcupine() # This will also call stop_audio_stream

    print("\n--- End of VoiceIO __main__ tests (after adding PyAudio placeholders) ---")
