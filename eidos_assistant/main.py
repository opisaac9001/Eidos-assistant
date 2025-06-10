import sys
import os
import re # Added for command parsing

# Add the 'core' directory to sys.path to allow importing LLMEngine
current_dir = os.path.dirname(os.path.abspath(__file__))
core_dir = os.path.join(current_dir, 'core')
if core_dir not in sys.path:
    sys.path.append(core_dir)

# Add 'interface' directory to sys.path
interface_dir = os.path.join(current_dir, 'interface')
if interface_dir not in sys.path:
    sys.path.append(interface_dir)

try:
    from llm_engine import LLMEngine
    from voice_io import VoiceIO
except ImportError as e:
    print(f"Error: Could not import required modules. Check paths. Details: {e}")
    sys.exit(1)

def run_assistant():
    print("Initializing Eidos Assistant...")

    engine = LLMEngine() # Uses defaults, including .env loading attempt

    if not engine.persona: # Persona loading is separate from client init for LLM
        print("Warning: LLM Engine did not load a persona. Using defaults.")
        # The engine will use its default system prompt if persona fails.

    print("Initializing Voice Interface...")
    voice_interface = VoiceIO() # Uses defaults, including .env loading attempt for Kokoro
    if not voice_interface.tts_client: # Check if client initialized successfully
        print("Warning: VoiceIO TTS client failed to initialize. /say command may not work as expected.")

    if not engine.client: # Check if LLM client initialized
        print("Warning: LLM Engine client failed to initialize. LLM interactions may not work.")

    # Print assistant startup message regardless of client statuses, as basic commands might still work.
    print(f"Eidos Assistant ({engine.get_persona_attribute('identity.name') or 'DefaultName'}, {engine.get_persona_attribute('tone') or 'default tone'}) started.")
    if engine.client :
        print(f"LLM Engine connected to: {engine.api_base_url}")
    else:
        print(f"LLM Engine NOT connected to: {engine.api_base_url} (client init failed or not attempted)")

    if voice_interface.tts_client:
        print(f"VoiceIO TTS connected to: {voice_interface.kokoro_base_url}")
    else:
        print(f"VoiceIO TTS NOT connected (client init failed or not attempted)")

    print("Ensure your OpenAI API-compatible LLM server (and Kokoro TTS server for /say) is running if needed.")
    print("Type 'quit' or 'exit' to end the session.")
    print("-" * 30)

    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["quit", "exit"]:
                print("Exiting Eidos Assistant. Goodbye!")
                break

            if not user_input.strip(): # Handle empty input
                continue

            if user_input.startswith("/"):
                command_parts = user_input.split(" ", 1)
                command = command_parts[0]
                args_str = command_parts[1] if len(command_parts) > 1 else ""

                if command == "/remember":
                    match = re.match(r"(\w+)\.(\w+)=(.+)", args_str)
                    if match:
                        category, key, value = match.groups()
                        # Basic type conversion for common types, could be expanded
                        if value.lower() == "true": value = True
                        elif value.lower() == "false": value = False
                        elif value.isdigit(): value = int(value)
                        elif value.replace('.', '', 1).isdigit(): # crude float check
                            try: value = float(value)
                            except ValueError: pass # Keep as string if not a simple float

                        if engine.remember(category, key, value):
                            print(f"Eidos: Okay, I've remembered that {category}.{key} is {value}.")
                            # Refresh system prompt if a known prompt-affecting key is changed
                            if (category == "user_profile" and key == "name") or \
                               (category == "user_preferences" and key == "theme"):
                                engine.refresh_system_prompt()
                                print(f"Eidos: My system prompt has been updated.")
                        else:
                            print(f"Eidos: I couldn't remember that. There might have been an issue.")
                    else:
                        print("Eidos: Usage: /remember <category>.<key>=<value> (e.g., /remember user_profile.name=Alice)")

                elif command == "/recall":
                    match = re.match(r"(\w+)\.(\w+)", args_str)
                    if match:
                        category, key = match.groups()
                        value = engine.recall(category, key)
                        if value is not None:
                            print(f"Eidos: I recall {category}.{key} is: {value}")
                        else:
                            print(f"Eidos: I don't have anything stored for {category}.{key}.")
                    else:
                        print("Eidos: Usage: /recall <category>.<key> (e.g., /recall user_profile.name)")

                elif command == "/forget":
                    match = re.match(r"(\w+)\.(\w+)", args_str)
                    if match:
                        category, key = match.groups()
                        if engine.forget(category, key):
                            print(f"Eidos: Okay, I've forgotten {category}.{key}.")
                            if (category == "user_profile" and key == "name") or \
                               (category == "user_preferences" and key == "theme"):
                                engine.refresh_system_prompt()
                                print(f"Eidos: My system prompt has been updated.")
                        else:
                            print(f"Eidos: I couldn't forget that, or it wasn't stored.")
                    else:
                        print("Eidos: Usage: /forget <category>.<key> (e.g., /forget user_profile.name)")

                elif command == "/system_prompt":
                    print(f"Eidos (Debug): Current system prompt is:\n{engine.system_prompt}")

                elif command == "/say":
                    text_to_speak = args_str.strip()
                    if not text_to_speak:
                        print("Eidos: Usage: /say <text you want me to speak>")
                    else:
                        print(f"Eidos: Attempting to generate speech for: '{text_to_speak[:50]}...'")
                        output_filename = "eidos_tts_output.mp3"
                        if voice_interface.text_to_speech(text_to_speak, output_filename=output_filename):
                            print(f"Eidos: Speech saved to {output_filename}. You can play it with an audio player.")
                        else:
                            print(f"Eidos: Sorry, I couldn't generate speech. Check logs or TTS server status.")

                elif command == "/listen":
                    audio_file_path = args_str.strip()
                    if not audio_file_path:
                        print("Eidos: Usage: /listen <path_to_audio_file> (e.g., /listen my_audio.wav)")
                    else:
                        print(f"Eidos: Attempting to transcribe audio from: '{audio_file_path}'...")
                        transcribed_text = voice_interface.speech_to_text(audio_file_path)

                        if transcribed_text.startswith("[STT") or transcribed_text.startswith("[Audio File"): # Check for known error messages from VoiceIO
                            print(f"Eidos STT: {transcribed_text}") # Print the error/status message from VoiceIO
                        elif transcribed_text:
                            print(f"Eidos STT: Transcribed text: \"{transcribed_text}\"")
                            # Optional: Feed to LLM
                            # print("Eidos: Processing transcribed text with LLM...")
                            # assistant_response = engine.get_response(transcribed_text)
                            # print(f"Eidos: {assistant_response}")
                        else:
                            print(f"Eidos STT: Transcription failed or produced no text. Ensure the audio file is valid and STT model is working.")

                else:
                    print(f"Eidos: Unknown command '{command}'. Try /remember, /recall, /forget, /say, /system_prompt, or /listen.")
                continue # Skip sending command to LLM

            # Only try to get LLM response if client is available
            if not engine.client:
                print("Eidos (Error): LLM client not available. Cannot process general queries.")
                continue

            assistant_response = engine.get_response(user_input)
            print(f"Eidos: {assistant_response}")

        except KeyboardInterrupt:
            print("\nExiting Eidos Assistant due to interrupt. Goodbye!")
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            # Optionally, decide if the loop should break on all errors
            # break
    # Ensure Porcupine is cleaned up if it was initialized, though run_always_listening_mode handles its own.
    # This is more of a general cleanup if VoiceIO was used elsewhere and main is exiting.
    finally:
        if 'voice_interface' in locals() and hasattr(voice_interface, 'delete_porcupine'):
            voice_interface.delete_porcupine() # Call if porcupine might have been used outside always_listening
        print("Eidos Assistant session ended.")


def run_always_listening_mode(engine, voice_interface):
    print("\n--- Pathos Always-Listening Mode (Conceptual) ---")
    if not voice_interface.porcupine:
        print("Pathos: Porcupine Wake Word engine not initialized. Cannot start always-listening mode.")
        print("Pathos: Please check your PICOVOICE_ACCESS_KEY and Porcupine configurations in .env and README.")
        return

    print(f"Pathos: Listening for wake word(s): {voice_interface.porcupine_keywords_list}...")
    print(f"Pathos: (This is a conceptual loop. Actual microphone input and continuous STT are not implemented here.)")
    print("Pathos: To exit this conceptual mode, type 'quit' or 'exit' if a prompt appears, or use Ctrl+C.")

    # Conceptual loop - in a real scenario, this would involve an audio stream.
    # For this placeholder, we'll just simulate a few iterations or wait for user input to break.
    try:
        # --- Placeholder for audio input library setup (e.g., PyAudio) ---
        # Example (conceptual, PyAudio not installed or used here):
        # import pyaudio
        # pa = pyaudio.PyAudio()
        # audio_stream = pa.open(
        #     rate=voice_interface.porcupine.sample_rate, # Should be 16000 for Porcupine
        #     channels=1,
        #     format=pyaudio.paInt16, # Porcupine needs int16
        #     input=True,
        #     frames_per_buffer=voice_interface.porcupine_frame_length
        # )
        # print("Pathos: (Conceptual) Microphone stream opened.")
        # --- End of placeholder ---

        active_listening_for_command = False
        # In a real app, you'd have a way to buffer audio after wake word,
        # or start a dedicated STT recording session.

        # Simulate a few checks or a way to break for this conceptual demo
        for i in range(5): # Simulate a few cycles for demo purposes
            print(f"\nPathos (Conceptual Listen Cycle {i+1}):")

            # --- Placeholder for reading audio frame ---
            # conceptual_audio_frame = list(audio_stream.read(voice_interface.porcupine_frame_length))
            # For this demo, we don't have real audio.
            # We can't call process_audio_chunk_for_wakeword without a real frame.
            # So, we'll simulate a wake word detection manually for one cycle.
            # --- End of placeholder ---

            if i == 2: # Simulate wake word detection on the 3rd conceptual cycle
                if not voice_interface.porcupine_keywords_list: # Check if list is empty
                    print("Pathos: (Conceptual) No keywords configured for detection.")
                else:
                    detected_keyword_index = 0 # Simulate first configured keyword detected
                    print(f"Pathos: Wake word '{voice_interface.porcupine_keywords_list[detected_keyword_index]}' detected conceptually!")
                    active_listening_for_command = True

                    # --- Placeholder for starting STT after wake word ---
                    print("Pathos: (Conceptual) Would now listen for command via STT...")
                    # In a real app:
                    # 1. Start buffering/recording audio for STT.
                    # 2. After a pause or fixed duration, stop recording.
                    # 3. Save to a temporary file.
                    # temp_audio_file = "temp_stt_command.wav" # Needs to be in a writable location
                    # transcribed_command = voice_interface.speech_to_text(temp_audio_file)
                    # print(f"Pathos (Conceptual STT): Transcribed: '{transcribed_command}'")
                    # if transcribed_command and not transcribed_command.startswith("[STT"):
                    #     response = engine.get_response(transcribed_command)
                    #     print(f"Pathos: {response}")
                    #     if voice_interface.tts_client: # If TTS is available
                    #         # This output_filename should ideally be unique or managed
                    #         tts_output_file = "pathos_response.mp3"
                    #         voice_interface.text_to_speech(response, output_filename=tts_output_file)
                    #         print(f"Pathos: (Conceptual) Spoke response. Audio saved to {tts_output_file}.")
                    # else:
                    #     print("Pathos: (Conceptual STT) No command transcribed or STT error.")
                    # if os.path.exists(temp_audio_file): os.remove(temp_audio_file) # Clean up
                    # --- End of placeholder ---

                    active_listening_for_command = False # Reset
                    print("Pathos: (Conceptual) Returning to listening for wake word...")
            else:
                print("Pathos: (Conceptual) No wake word detected in this cycle.")

            # Simulate a short delay as audio frames would come in over time
            # import time
            # time.sleep(0.1) # Not using time.sleep to avoid subtask issues.

        print("\nPathos: (Conceptual) Always-listening demo cycles finished.")

    except KeyboardInterrupt:
        print("\nPathos: Always-listening mode interrupted by user.")
    finally:
        # --- Placeholder for closing audio stream ---
        # if 'audio_stream' in locals() and audio_stream.is_active():
        #    audio_stream.stop_stream()
        #    audio_stream.close()
        # if 'pa' in locals():
        #    pa.terminate()
        # print("Pathos: (Conceptual) Microphone stream closed.")
        # --- End of placeholder ---
        if voice_interface.porcupine: # Ensure delete is called if porcupine was init'd
            voice_interface.delete_porcupine()
        print("Pathos: Exited always-listening mode.")

if __name__ == '__main__':
    run_assistant()
