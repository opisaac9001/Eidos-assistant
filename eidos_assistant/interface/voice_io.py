import os
from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError
import whisper # Ensure whisper import is present
import pvporcupine # Added for Wake Word

# Construct path to .env in the eidos_assistant/ directory
# Assumes voice_io.py is in eidos_assistant/interface/
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if not load_dotenv(dotenv_path=dotenv_path):
    print(f"Warning: voice_io.py - Could not load .env file from {dotenv_path}")
else:
    print(f"Debug: voice_io.py - Successfully loaded .env file from {dotenv_path}")


class VoiceIO:
    def __init__(self):
        """Initializes the VoiceIO system, configured for Kokoro TTS via OpenAI API."""
        self.kokoro_base_url = os.getenv("KOKORO_TTS_BASE_URL", "http://localhost:8880/v1")
        self.kokoro_api_key = os.getenv("KOKORO_TTS_API_KEY", "not-needed")
        self.default_voice = os.getenv("KOKORO_TTS_VOICE", "af_sky")

        print(f"VoiceIO Initializing with TTS URL: {self.kokoro_base_url}, Default Voice: {self.default_voice}")

        try:
            self.tts_client = OpenAI(base_url=self.kokoro_base_url, api_key=self.kokoro_api_key)
            print("VoiceIO: OpenAI client for TTS initialized successfully.")
        except Exception as e:
            self.tts_client = None
            print(f"VoiceIO Error: Failed to initialize OpenAI client for TTS: {e}")

        print("VoiceIO: Initializing STT (Whisper)...")
        try:
            # For faster loading and CPU usage, using a small English-only model.
            # Other models: "tiny.en", "tiny", "base", "small.en", "small", "medium.en", "medium", "large"
            self.stt_model_name = "base.en"
            self.stt_model = whisper.load_model(self.stt_model_name)
            print(f"VoiceIO: Whisper STT model '{self.stt_model_name}' loaded successfully.")
        except Exception as e:
            self.stt_model = None
            print(f"VoiceIO Error: Failed to load Whisper STT model '{self.stt_model_name}': {e}")
            print("STT functionality will be unavailable. Ensure ffmpeg is installed and model files can be downloaded by Whisper.")
        # Ensure self.stt_model is defined even if all try-excepts were somehow bypassed, though unlikely
        if not hasattr(self, 'stt_model'):
            self.stt_model = None

        print("VoiceIO: Attempting to initialize Porcupine Wake Word Engine...")
        self.porcupine = None
        self.porcupine_frame_length = None
        self.porcupine_keywords_list = [] # To store the actual keywords being used

        try:
            access_key = os.getenv("PICOVOICE_ACCESS_KEY")
            if not access_key or access_key == "YOUR_PICOVOICE_ACCESS_KEY_HERE":
                print("VoiceIO Warning: PICOVOICE_ACCESS_KEY not set in .env or is placeholder. Porcupine will not initialize.")
                raise ValueError("Missing PICOVOICE_ACCESS_KEY")

            builtin_keywords_str = os.getenv("PORCUPINE_BUILTIN_KEYWORDS", "picovoice") # Default to 'picovoice'
            keyword_paths_str = os.getenv("PORCUPINE_KEYWORD_PATHS", "")
            model_path_str = os.getenv("PORCUPINE_MODEL_PATH", None) # Defaults to None for standard English model
            sensitivities_str = os.getenv("PORCUPINE_SENSITIVITIES", "")

            keywords = []
            if builtin_keywords_str:
                keywords.extend([k.strip() for k in builtin_keywords_str.split(',') if k.strip()])

            keyword_paths = []
            if keyword_paths_str:
                keyword_paths.extend([p.strip() for p in keyword_paths_str.split(',') if p.strip()])

            if not keywords and not keyword_paths:
                print("VoiceIO Warning: No built-in keywords or keyword_paths provided for Porcupine. Porcupine will not initialize.")
                raise ValueError("No keywords or keyword_paths for Porcupine")

            self.porcupine_keywords_list = keywords + [os.path.basename(p) for p in keyword_paths] # Store for reference

            sensitivities = None
            if sensitivities_str:
                try:
                    sensitivities = [float(s.strip()) for s in sensitivities_str.split(',') if s.strip()]
                    if len(sensitivities) != (len(keywords) + len(keyword_paths)):
                        print(f"VoiceIO Warning: Number of sensitivities ({len(sensitivities)}) does not match number of keywords ({len(keywords) + len(keyword_paths)}). Using default sensitivities.")
                        sensitivities = None
                except ValueError:
                    print("VoiceIO Warning: Invalid format for PORCUPINE_SENSITIVITIES. Using default sensitivities.")
                    sensitivities = None

            init_args = {"access_key": access_key}
            if keywords: # pvporcupine uses 'keywords' for built-in
                init_args["keywords"] = keywords
            if keyword_paths: # and 'keyword_paths' for custom .ppn files
                init_args["keyword_paths"] = keyword_paths
            if model_path_str and model_path_str.strip(): # Only add if provided and not empty
                init_args["model_path"] = model_path_str.strip()
            if sensitivities:
                init_args["sensitivities"] = sensitivities

            self.porcupine = pvporcupine.create(**init_args)
            self.porcupine_frame_length = self.porcupine.frame_length
            print(f"VoiceIO: Porcupine initialized successfully with keywords: {self.porcupine_keywords_list}, frame_length: {self.porcupine_frame_length}.")

        except ImportError:
            print("VoiceIO Error: pvporcupine library not found. Wake word detection will be unavailable.")
            print("Please ensure 'pvporcupine' is installed in your environment.")
        except pvporcupine.PorcupineError as pe: # Catch specific Porcupine errors
            print(f"VoiceIO Error: Porcupine engine error: {pe}")
            print("This could be due to an invalid AccessKey, model file issues, or other configuration problems.")
        except ValueError as ve: # Catch our own ValueErrors for config issues
            print(f"VoiceIO Error: Porcupine configuration error: {ve}")
        except Exception as e:
            print(f"VoiceIO Error: Failed to initialize Porcupine: {e}")
            print("Wake word detection will be unavailable.")


    def text_to_speech(self, text: str, voice: str = None, output_filename: str = "eidos_tts_output.mp3") -> bool:
        """
        Converts text to speech using Kokoro-FastAPI (OpenAI compatible) and saves to a file.
        Returns True on success, False on failure.
        """
        if not self.tts_client:
            print("VoiceIO Error: TTS client not initialized. Cannot generate speech.")
            return False

        actual_voice = voice if voice else self.default_voice

        try:
            print(f"VoiceIO: Requesting TTS for text: '{text[:50]}...' with voice: {actual_voice}")
            response = self.tts_client.audio.speech.create(
                model="kokoro",  # Model name might be ignored by Kokoro-FastAPI but is standard
                input=text,
                voice=actual_voice,
                response_format="mp3"  # Kokoro-FastAPI supports mp3, wav, opus, flac
            )

            # Ensure the directory for output_filename exists (if it includes a path)
            # For this script, output_filename is relative to where voice_io.py is run (eidos_assistant/interface/)
            # If main.py calls this, path might need adjustment or be absolute.
            # The test __main__ block will make it in eidos_assistant/ root.

            # Make output_filename relative to project root for consistency in tests.
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            abs_output_filename = os.path.join(project_root, output_filename)

            output_dir = os.path.dirname(abs_output_filename)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            response.stream_to_file(abs_output_filename)
            print(f"VoiceIO: Speech successfully saved to {abs_output_filename}")
            return True
        except APIConnectionError as e:
            print(f"VoiceIO TTS Error: Failed to connect to Kokoro API at {self.kokoro_base_url}: {e}")
        except APIStatusError as e:
            print(f"VoiceIO TTS Error: Kokoro API returned an error: Status {e.status_code}, Response: {e.response}")
        except Exception as e:
            print(f"VoiceIO TTS Error: An unexpected error occurred: {e}")

        return False

    def speech_to_text(self) -> str:
        """
        Transcribes audio from a file path using Whisper.
        Returns the transcribed text, or an empty string on failure.
        NOTE: This method is untested by the AI assistant due to environment limitations.
        The user must ensure 'openai-whisper' and 'ffmpeg' are installed.
        """
        if not self.stt_model:
            print("VoiceIO Error: STT model not loaded or failed to initialize. Cannot transcribe audio.")
            return "[STT Model Not Available]"

        if not os.path.exists(audio_file_path):
            print(f"VoiceIO STT Error: Audio file not found at '{audio_file_path}'")
            return "[Audio File Not Found]"

        try:
            print(f"VoiceIO: Attempting to transcribe audio from '{audio_file_path}' using Whisper model '{self.stt_model_name}'...")
            # fp16=False is generally recommended for CPU inference.
            # If the user has a GPU and CUDA setup, they might change this or use a different device setting.
            result = self.stt_model.transcribe(audio_file_path, fp16=False)
            transcribed_text = result["text"]
            print(f"VoiceIO STT: Transcription complete. Text: '{transcribed_text[:100]}...'")
            return transcribed_text.strip()
        except Exception as e:
            print(f"VoiceIO STT Error: An error occurred during transcription: {e}")
            return "[STT Transcription Error]"

    def process_audio_chunk_for_wakeword(self, audio_chunk_pcm: list[int]) -> int:
        """
        Processes a chunk of audio data for wake word detection.
        audio_chunk_pcm: A list/tuple of int16 PCM samples. Must be of length porcupine.frame_length.
        Returns: Index of the detected keyword if a wake word is detected (e.g., 0, 1, ...),
                 -1 otherwise.
        NOTE: This method is untested by the AI assistant. User must ensure correct setup.
        """
        if not self.porcupine:
            # print("VoiceIO Debug: Porcupine not initialized, skipping wake word processing.") # Can be too noisy
            return -1

        if len(audio_chunk_pcm) != self.porcupine_frame_length:
            print(f"VoiceIO Error: Audio chunk length ({len(audio_chunk_pcm)}) does not match Porcupine frame length ({self.porcupine_frame_length}).")
            return -1

        try:
            keyword_index = self.porcupine.process(audio_chunk_pcm)
            # if keyword_index >= 0:
            #    print(f"VoiceIO Debug: Wake word detected with index: {keyword_index}") # Can be too noisy
            return keyword_index # Will be -1 if no keyword detected, or 0, 1, ... if detected
        except pvporcupine.PorcupineError as e:
            print(f"VoiceIO Error: Porcupine process error: {e}")
            return -1
        except Exception as e:
            print(f"VoiceIO Error: Unexpected error during Porcupine process: {e}")
            return -1

    def delete_porcupine(self):
        """Releases resources acquired by Porcupine."""
        if self.porcupine:
            print("VoiceIO: Deleting Porcupine instance...")
            try:
                self.porcupine.delete()
                self.porcupine = None
                print("VoiceIO: Porcupine instance deleted.")
            except Exception as e:
                print(f"VoiceIO Error: Failed to delete Porcupine instance: {e}")

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

    # Example of calling delete
    # voice_interface.delete_porcupine()

    print("\n--- End of VoiceIO __main__ tests (after adding Porcupine) ---")
