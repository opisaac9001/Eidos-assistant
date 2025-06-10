import sys
import os
import re # Added for command parsing
import time # For sleep in conceptual loop

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
                            print(f"Pathos: Speech saved to {output_filename}.")
                            # VoiceIO.text_to_speech now attempts playback internally and prints messages about it.
                            # We just add a general note here.
                            print(f"Pathos: Attempting to play audio...")
                        else:
                            print(f"Pathos: Sorry, I couldn't generate speech. Check logs or TTS server status.")

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

                elif command == "/always_listen": # This was added in the previous step, ensure it's here
                    print("Eidos: Entering conceptual always-listening mode...")
                    run_always_listening_mode(engine, voice_interface)
                    print("Eidos: Exited conceptual always-listening mode. Returning to standard input.")

                elif command == "/ha_status":
                    entity_id = args_str.strip()
                    if not entity_id:
                        print("Pathos: Usage: /ha_status <entity_id>")
                    elif not engine.ha_skill:
                        print("Pathos: Home Assistant skill is not available or not configured.")
                    else:
                        print(f"Pathos: Getting status for HA entity: '{entity_id}'...")
                        state = engine.ha_skill.get_entity_state(entity_id)
                        if state:
                            print(f"Pathos HA Status: {entity_id} -> State: {state.get('state')}, Attributes: {state.get('attributes')}")
                        else:
                            print(f"Pathos: Could not retrieve status for '{entity_id}'. Check entity ID and HA connection.")

                elif command == "/ha_toggle":
                    entity_id = args_str.strip()
                    if not entity_id:
                        print("Pathos: Usage: /ha_toggle <entity_id>")
                    elif not engine.ha_skill:
                        print("Pathos: Home Assistant skill is not available or not configured.")
                    else:
                        print(f"Pathos: Attempting to toggle HA entity: '{entity_id}'...")
                        # Using "homeassistant" domain for generic toggle
                        if engine.ha_skill.call_service("homeassistant", "toggle", {"entity_id": entity_id}):
                            print(f"Pathos: Toggle command sent for '{entity_id}'. Check Home Assistant for state change.")
                        else:
                            print(f"Pathos: Failed to send toggle command for '{entity_id}'.")
                elif command == "/ha_list_entities":
                    if not engine.ha_skill or not engine.ha_skill.ha_token or engine.ha_skill.ha_token == "YOUR_LONG_LIVED_ACCESS_TOKEN_HERE":
                        print("Pathos: Home Assistant skill is not available or not configured. Please check your .env file.")
                    else:
                        print("Pathos: Retrieving list of entities from Home Assistant...")
                        entities = engine.ha_skill.list_entities()
                        if entities is not None:
                            if not entities:
                                print("Pathos: No entities found in Home Assistant.")
                            else:
                                print("Pathos: Found the following entities:")
                                for entity in entities:
                                    entity_id = entity.get('entity_id', 'Unknown ID')
                                    friendly_name = entity.get('friendly_name', entity_id)
                                    state = entity.get('state', 'Unknown State')
                                    if friendly_name != entity_id:
                                        print(f"  - {entity_id} [{friendly_name}] - State: {state}")
                                    else:
                                        print(f"  - {entity_id} - State: {state}")
                                print(f"Pathos: Total entities found: {len(entities)}.")
                        else:
                            print("Pathos: Failed to retrieve entities from Home Assistant. Check logs for details.")
                else:
                    print(f"Eidos: Unknown command '{command}'. Try /remember, /recall, /forget, /say, /system_prompt, /listen, /always_listen, /ha_status, /ha_toggle, or /ha_list_entities.")
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
        if 'voice_interface' in locals() and hasattr(voice_interface, 'delete_porcupine') and voice_interface.porcupine:
             voice_interface.delete_porcupine() # Ensure Porcupine resources are freed if it was initialized
        print("Eidos Assistant session ended.")


def run_always_listening_mode(engine, voice_interface):
    print("\n--- Pathos Always-Listening Mode ---")

    if not voice_interface.porcupine:
        print("Pathos: Porcupine Wake Word engine not initialized. Cannot start always-listening mode.")
        print("Pathos: Please check your PICOVOICE_ACCESS_KEY and Porcupine configurations in .env and README.")
        return
    if not voice_interface.stt_model:
        print("Pathos: Whisper STT model not initialized. Always-listening mode might not function fully for STT.")
        # Depending on desired behavior, could return here or proceed with wake word only.
        # For now, let's allow it to proceed, but STT will fail if called.

    print(f"Pathos: Attempting to start audio stream for wake word detection...")
    if not voice_interface.start_audio_stream(): # This now depends on Porcupine for frame_length
        print("Pathos: Failed to start audio stream. Exiting always-listening mode.")
        # voice_interface.delete_porcupine() # This is called in the finally block of this function
        return

    print(f"Pathos: Listening for wake word(s): {voice_interface.porcupine_keywords_list}...")
    print("Pathos: Press Ctrl+C to exit always-listening mode.")

    try:
        while True: # Main listening loop
            audio_frame_pcm = voice_interface.read_audio_stream_chunk()
            if not audio_frame_pcm:
                time.sleep(0.05) # Avoid busy-looping on read errors, give system time
                continue

            keyword_index = voice_interface.process_audio_chunk_for_wakeword(audio_frame_pcm)

            if keyword_index >= 0:
                if not voice_interface.porcupine_keywords_list or keyword_index >= len(voice_interface.porcupine_keywords_list):
                    print("Pathos Error: Detected keyword index out of bounds for configured keywords.")
                    continue # Or handle error more robustly

                detected_keyword = voice_interface.porcupine_keywords_list[keyword_index]
                print(f"\nPathos: Wake word '{detected_keyword}' detected!")

                # Conceptual: Stop wake word stream to free up microphone for STT recording, then restart
                # This is a simple approach; more advanced would use a single stream managed differently.
                voice_interface.stop_audio_stream() # Stop stream before STT recording

                project_root = os.path.dirname(os.path.abspath(__file__)) # eidos_assistant directory
                temp_audio_file = os.path.join(project_root, "temp_user_command.wav")

                print("Pathos: Listening for your command...")
                if voice_interface.record_audio_for_stt(duration_seconds=4, temp_filename=temp_audio_file):
                    print(f"Pathos: Processing command from {temp_audio_file}...")
                    transcribed_text = voice_interface.speech_to_text(temp_audio_file)

                    try:
                        if os.path.exists(temp_audio_file):
                            os.remove(temp_audio_file)
                    except OSError as e:
                        print(f"Pathos Warning: Could not delete temporary audio file {temp_audio_file}: {e}")

                    if transcribed_text and not transcribed_text.startswith("[STT") and not transcribed_text.startswith("[Audio File"):
                        print(f"Pathos (You said): \"{transcribed_text}\"")
                        print("Pathos: Thinking...")
                        llm_response = engine.get_response(transcribed_text)
                        print(f"Pathos (Response): {llm_response}")

                        if voice_interface.tts_client:
                            is_error_response = any([
                                llm_response.startswith("Pathos: Sorry, I tried but failed"),
                                llm_response.startswith("Pathos: Could not get status"),
                                llm_response.startswith("Pathos: Home Assistant tool call was missing"),
                                llm_response.startswith("Pathos (error):") # General LLM errors
                            ])
                            if not is_error_response:
                                tts_output_file = os.path.join(project_root, "pathos_response.mp3")
                                if voice_interface.text_to_speech(llm_response, output_filename=tts_output_file):
                                    print("Pathos: (Played response audio)")
                                else:
                                    print("Pathos: (Failed to play response audio)")
                    elif transcribed_text:
                         print(f"Pathos: {transcribed_text}") # Print STT error string
                    else:
                        print("Pathos: Could not understand command (STT failed or produced no text).")
                else:
                    print("Pathos: Failed to record command audio.")

                print(f"\nPathos: Restarting audio stream for wake word detection...")
                if not voice_interface.start_audio_stream():
                    print("Pathos: Critical - Failed to restart audio stream. Exiting always-listening mode.")
                    break
                else:
                    print(f"Pathos: Listening again for wake word(s): {voice_interface.porcupine_keywords_list}...")

            # time.sleep(0.01) # Optional: small sleep if loop is too tight

    except KeyboardInterrupt:
        print("\nPathos: Always-listening mode interrupted by user.")
    except Exception as e:
        print(f"Pathos: An unexpected error occurred in always-listening mode: {e}")
    finally:
        print("Pathos: Stopping audio stream and cleaning up Porcupine for this mode...")
        voice_interface.stop_audio_stream() # Ensure stream is stopped
        # Porcupine instance itself is managed by the VoiceIO object passed in;
        # its lifecycle is tied to VoiceIO. delete_porcupine() is called when main.py exits.
        # However, if this mode specifically initialized it or has unique control, cleanup here.
        # The current VoiceIO.delete_porcupine() also calls stop_audio_stream.
        # No explicit call to voice_interface.delete_porcupine() here, let main.py's finally handle it.
        print("Pathos: Exited always-listening mode.")

if __name__ == '__main__':
    run_assistant()
