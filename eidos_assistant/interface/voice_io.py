import os
from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError

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
        Captures audio from the microphone and converts it to text.
        Placeholder implementation.
        """
        print("STT: Listening for speech...")
        # In a real implementation, this would use a library like Whisper
        # to capture and transcribe audio.
        placeholder_text = "This is a placeholder for recognized speech."
        print(f"STT: (Placeholder) Recognized: '{placeholder_text}'")
        return placeholder_text

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

    print("\nVoiceIO module TTS test complete.")
