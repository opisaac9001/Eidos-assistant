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
    # Import validation utility functions
    from validation_utils import (
        check_ffmpeg_accessible,
        list_microphones,
        check_picovoice_config,
        check_llm_setup, # Renamed from check_llm_server_connectivity
        check_tts_setup
    )
except ImportError as e:
    print(f"Error: Could not import required modules. Check paths. Details: {e}")
    sys.exit(1)

def run_assistant():
    print("Initializing Pathos Assistant...") # Eidos -> Pathos

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
    print(f"Pathos Assistant ({engine.get_persona_attribute('identity.name') or 'DefaultName'}, {engine.get_persona_attribute('tone') or 'default tone'}) started.") # Eidos -> Pathos
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
                print("Exiting Pathos Assistant. Goodbye!") # Eidos -> Pathos
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
                            print(f"Pathos: Okay, I've remembered that {category}.{key} is {value}.")  # Eidos -> Pathos
                            # Refresh system prompt if a known prompt-affecting key is changed
                            if (category == "user_profile" and key == "name") or \
                               (category == "user_preferences" and key == "theme"):
                                engine.refresh_system_prompt()
                                print(f"Pathos: My system prompt has been updated.") # Eidos -> Pathos
                        else:
                            print(f"Pathos: I couldn't remember that. There might have been an issue.") # Eidos -> Pathos
                    else:
                        print("Pathos: Usage: /remember <category>.<key>=<value> (e.g., /remember user_profile.name=Alice)") # Eidos -> Pathos

                elif command == "/recall":
                    match = re.match(r"(\w+)\.(\w+)", args_str)
                    if match:
                        category, key = match.groups()
                        value = engine.recall(category, key)
                        if value is not None:
                            print(f"Pathos: I recall {category}.{key} is: {value}") # Eidos -> Pathos
                        else:
                            print(f"Pathos: I don't have anything stored for {category}.{key}.") # Eidos -> Pathos
                    else:
                        print("Pathos: Usage: /recall <category>.<key> (e.g., /recall user_profile.name)") # Eidos -> Pathos

                elif command == "/forget":
                    match = re.match(r"(\w+)\.(\w+)", args_str)
                    if match:
                        category, key = match.groups()
                        if engine.forget(category, key):
                            print(f"Pathos: Okay, I've forgotten {category}.{key}.") # Eidos -> Pathos
                            if (category == "user_profile" and key == "name") or \
                               (category == "user_preferences" and key == "theme"):
                                engine.refresh_system_prompt()
                                print(f"Pathos: My system prompt has been updated.") # Eidos -> Pathos
                        else:
                            print(f"Pathos: I couldn't forget that, or it wasn't stored.") # Eidos -> Pathos
                    else:
                        print("Pathos: Usage: /forget <category>.<key> (e.g., /forget user_profile.name)") # Eidos -> Pathos

                elif command == "/system_prompt":
                    print(f"Pathos (Debug): Current system prompt is:\n{engine.system_prompt}") # Eidos -> Pathos

                elif command == "/say":
                    text_to_speak = args_str.strip()
                    if not text_to_speak:
                        print("Pathos: Usage: /say <text you want me to speak>")
                    else:
                        print(f"Pathos: Attempting to generate speech for: '{text_to_speak[:50]}...'")
                        output_filename = "eidos_tts_output.mp3" # Consider making this configurable or unique

                        # VoiceIO.text_to_speech now returns bool, prints details internally.
                        success = voice_interface.text_to_speech(text_to_speak, output_filename=output_filename)

                        if success:
                            # The file path is constructed inside text_to_speech, so we don't have it here directly
                            # unless we change text_to_speech to return it.
                            # For now, the internal print about saving is sufficient.
                            print(f"Pathos: Speech generation was successful (output: {output_filename}). Playback attempted.")
                            print(f"Pathos: Please check console output from VoiceIO for details on saving and playback status.")
                        else:
                            # Generic error message; specific details are printed by VoiceIO.text_to_speech
                            print(f"Pathos: Sorry, I couldn't generate or play speech. See console for error details from VoiceIO.")

                elif command == "/listen":
                    audio_file_path = args_str.strip()
                    if not audio_file_path:
                        print("Pathos: Usage: /listen <path_to_audio_file> (e.g., /listen my_audio.wav)")
                    else:
                        print(f"Pathos: Attempting to transcribe audio from: '{audio_file_path}'...")
                        transcribed_text = voice_interface.speech_to_text(audio_file_path) # This now returns detailed errors

                        # Check for specific error prefixes returned by the updated speech_to_text
                        if transcribed_text.startswith("[STT Model Not Loaded") or \
                           transcribed_text.startswith("[STT Error: ffmpeg not found") or \
                           transcribed_text.startswith("[STT Error: ffmpeg found but") or \
                           transcribed_text.startswith("[STT Error: ffmpeg check timed out") or \
                           transcribed_text.startswith("[Audio File Not Found") or \
                           transcribed_text.startswith("[STT Transcription Error"):
                            print(f"Pathos STT Error: {transcribed_text}")
                        elif transcribed_text: # Success
                            print(f"Pathos STT: Transcribed text: \"{transcribed_text}\"")
                            # Optional: Feed to LLM
                            # print("Pathos: Processing transcribed text with LLM...")
                            # assistant_response = engine.get_response(transcribed_text)
                            # print(f"Pathos: {assistant_response}")
                        else: # Should ideally be covered by specific error messages now
                            print(f"Pathos STT: Transcription failed or produced no text. Ensure the audio file is valid and all dependencies (Whisper, ffmpeg) are correctly set up. Check console for details.")

                elif command == "/always_listen":
                    print("Pathos: Preparing for always-listening mode...")
                    run_always_listening_mode(engine, voice_interface)
                    print("Pathos: Exited always-listening mode. Returning to standard input.") # Eidos -> Pathos

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

                elif command == "/validate_setup":
                    print("\nPathos: --- Validating Setup ---") # Eidos -> Pathos

                    # 1. Check FFmpeg
                    ffmpeg_ok, ffmpeg_msg = check_ffmpeg_accessible()
                    print(f"  [FFmpeg Check] Status: {'OK' if ffmpeg_ok else 'FAIL'}")
                    print(f"    Details: {ffmpeg_msg}")

                    # 2. List Microphones (PyAudio/PortAudio check)
                    mics_ok, mics_msg_or_list = list_microphones()
                    print(f"\n  [Microphone Check] Status: {'OK' if mics_ok else 'FAIL'}")
                    if isinstance(mics_msg_or_list, list):
                        if mics_msg_or_list:
                            print(f"    Available input devices:")
                            for mic_name in mics_msg_or_list:
                                print(f"      - {mic_name}")
                        # If the list is empty but mics_ok is true, it means PyAudio worked but found no devices.
                        # The function list_microphones itself returns a specific message for this.
                        # So, if it's an empty list here, it implies the function considered it a success but no mics.
                        # However, the current list_microphones returns a string message in this case.
                        # Let's adjust to consistently handle string messages for "OK but no mics" or "FAIL".
                    else: # It's an error message string
                        print(f"    Details: {mics_msg_or_list}")

                    # 3. Check Picovoice (Porcupine) Configuration
                    print(f"\n  [Picovoice/Porcupine Check]")
                    picovoice_results = check_picovoice_config(voice_interface)
                    if not picovoice_results: # Should not happen if function is well-behaved
                        print(f"    Status: FAIL")
                        print(f"    Details: Could not retrieve Picovoice configuration details.")
                    for ok, msg in picovoice_results:
                        print(f"    - Status: {'OK' if ok else 'FAIL'}")
                        print(f"      Details: {msg}")

                    # 4. Check LLM Setup
                    llm_ok, llm_msg = check_llm_setup(engine) # Call the new function
                    print(f"\n  [LLM Setup Check] Status: {'OK' if llm_ok else 'FAIL'}") # Updated title
                    print(f"    Engine Type: {getattr(engine, 'llm_engine_type', 'Unknown')}") # Display engine type
                    print(f"    Details: {llm_msg}")

                    # 5. Check TTS Setup
                    tts_ok, tts_msg = check_tts_setup(voice_interface) # Call the new function
                    print(f"\n  [TTS Setup Check] Status: {'OK' if tts_ok else 'FAIL'}") # Updated title
                    print(f"    Engine Type: {getattr(voice_interface, 'tts_engine_type', 'Unknown')}") # Display engine type
                    print(f"    Details: {tts_msg}")

                    print("\n--- Validation Complete ---")

                else:
                    print(f"Pathos: Unknown command '{command}'. Try /remember, /recall, /forget, /say, /system_prompt, /listen, /always_listen, /ha_status, /ha_toggle, or /validate_setup.") # Eidos -> Pathos
                continue # Skip sending command to LLM

            # Only try to get LLM response if client is available
            if not engine.client:
                print("Pathos (Error): LLM client not available. Cannot process general queries.") # Eidos -> Pathos
                continue

            assistant_response = engine.get_response(user_input)
            print(f"Pathos: {assistant_response}") # Eidos -> Pathos

        except KeyboardInterrupt:
            print("\nExiting Pathos Assistant due to interrupt. Goodbye!")
            break
        except Exception as e:
            print(f"An unexpected error occurred in main loop: {e}") # Added "in main loop" for clarity
            # Optionally, decide if the loop should break on all errors
            # break
    # Ensure Porcupine is cleaned up if it was initialized
    finally:
        if 'voice_interface' in locals() and hasattr(voice_interface, 'delete_porcupine') and voice_interface.porcupine:
             voice_interface.delete_porcupine()
        print("Pathos Assistant session ended.") # Eidos -> Pathos


def run_always_listening_mode(engine, voice_interface):
    print("\n--- Pathos Always-Listening Mode ---")

    # 1. Pre-checks for essential components
    print("Pathos: Performing pre-checks for always-listening mode...")

    if not voice_interface.porcupine:
        print("Pathos Error: Porcupine Wake Word engine not initialized in VoiceIO.")
        print("  Please ensure PICOVOICE_ACCESS_KEY is correct in .env, keyword files are accessible,")
        print("  and there were no Porcupine errors on startup (check console logs).")
        print("Pathos: Exiting always-listening mode.")
        return

    if not voice_interface.stt_model:
        print("Pathos Warning: Whisper STT model not loaded in VoiceIO.")
        print("  Transcription of commands will fail. Only wake word detection can function if STT is not fixed.")
        print("  Ensure 'openai-whisper' and its dependencies (like PyTorch) are installed, and 'ffmpeg' is available.")
        # Not returning, as wake word might still be testable.

    # Check ffmpeg (important for STT that follows wake word)
    ffmpeg_ok, ffmpeg_msg = check_ffmpeg_accessible() # Using the imported validation function
    if not ffmpeg_ok:
        print(f"Pathos Warning: FFmpeg check failed: {ffmpeg_msg}")
        print("  Transcription of commands (STT) after wake word will likely fail. Please install/fix ffmpeg.")
        # Not returning, to allow wake word testing.
    else:
        # This check is a bit verbose if already shown in /validate_setup, but good for this specific mode
        print(f"Pathos: FFmpeg check successful: {ffmpeg_msg.splitlines()[0]}") # Show only first line


    # Check for microphones (essential for any audio input)
    mics_ok, mics_msg_or_list = list_microphones() # Using the imported validation function
    if not mics_ok or not isinstance(mics_msg_or_list, list) or not mics_msg_or_list:
        print(f"Pathos Error: Microphone check failed or no microphones found: {mics_msg_or_list}")
        print("  Cannot start always-listening mode without a working microphone and PyAudio/PortAudio setup.")
        print("  Run `/validate_setup` for more details or check `setup.sh` guidance.")
        print("Pathos: Exiting always-listening mode.")
        return
    else:
        # Log found microphones for debugging, but maybe not all to console if many.
        print(f"Pathos: Microphones found (first one listed for brevity): {mics_msg_or_list[0]}")


    # 2. Attempt to start audio stream
    print("Pathos: Attempting to start audio stream for wake word detection...")
    if not voice_interface.start_audio_stream():
        # VoiceIO.start_audio_stream() now has improved internal error messages.
        print("Pathos: Failed to start audio stream (see VoiceIO errors above). Exiting always-listening mode.")
        return

    print(f"Pathos: Listening for wake word(s): {voice_interface.porcupine_keywords_list or 'None Configured! Check .env'}.")
    print("Pathos: Press Ctrl+C to exit always-listening mode.")

    try:
        while True:
            audio_frame_pcm = voice_interface.read_audio_stream_chunk()
            if not audio_frame_pcm:
                time.sleep(0.05) # Avoid tight loop if read fails or stream is temporarily unavailable
                continue

            keyword_index = voice_interface.process_audio_chunk_for_wakeword(audio_frame_pcm)

            if keyword_index >= 0:
                if not voice_interface.porcupine_keywords_list or keyword_index >= len(voice_interface.porcupine_keywords_list):
                    print(f"Pathos Error: Detected keyword index {keyword_index} out of bounds for configured keywords: {voice_interface.porcupine_keywords_list}.")
                    if voice_interface.tts_client: voice_interface.text_to_speech("An internal error occurred with wake word configuration.")
                    continue

                detected_keyword = voice_interface.porcupine_keywords_list[keyword_index]
                print(f"\nPathos: Wake word '{detected_keyword}' detected!")

                voice_interface.stop_audio_stream()

                project_root = os.path.dirname(os.path.abspath(__file__))
                temp_audio_file = os.path.join(project_root, "temp_user_command.wav")

                print("Pathos: Listening for your command...")
                recorded_file_path = voice_interface.record_audio_for_stt(duration_seconds=4, temp_filename=temp_audio_file)

                if recorded_file_path:
                    print(f"Pathos: Processing command from {recorded_file_path}...")
                    transcribed_text = voice_interface.speech_to_text(recorded_file_path)

                    try:
                        if os.path.exists(recorded_file_path): os.remove(recorded_file_path)
                    except OSError as e: print(f"Pathos Warning: Could not delete temporary audio file {recorded_file_path}: {e}")

                    if transcribed_text.startswith(("[STT Model Not Loaded", "[STT Error: ffmpeg not found", "[STT Error: ffmpeg found but",
                                                    "[STT Error: ffmpeg check timed out", "[Audio File Not Found", "[STT Transcription Error")) : # Tuple for startswith
                        print(f"Pathos STT Error: {transcribed_text}")
                        if voice_interface.tts_client: voice_interface.text_to_speech("Sorry, I had trouble understanding. Please check the console.")
                    elif transcribed_text:
                        print(f"Pathos (You said): \"{transcribed_text}\"")
                        print("Pathos: Thinking...")
                        llm_response = engine.get_response(transcribed_text)
                        print(f"Pathos (Response): {llm_response}")

                        if voice_interface.tts_client:
                            is_error_response = any([llm_response.startswith(err_prefix) for err_prefix in
                                                     ("Pathos: Sorry, I tried but failed", "Pathos: Could not get status",
                                                      "Pathos: Home Assistant tool call was missing", "Pathos (error):")]) # Tuple for any
                            if not is_error_response:
                                tts_output_file = os.path.join(project_root, "pathos_response.mp3")
                                voice_interface.text_to_speech(llm_response, output_filename=tts_output_file)
                            else: print("Pathos: (Skipping TTS for error-like LLM response)")
                        else: print("Pathos: (TTS client not available to speak response)")
                    else:
                        print("Pathos: Could not understand command (STT failed or produced no text). Please try speaking clearly.")
                        if voice_interface.tts_client: voice_interface.text_to_speech("Sorry, I didn't catch that. Could you please repeat?")
                else:
                    print("Pathos: Failed to record command audio. Check microphone and PyAudio setup. See console for VoiceIO errors.")
                    if voice_interface.tts_client: voice_interface.text_to_speech("I had a problem with the microphone while trying to listen.")

                print(f"\nPathos: Restarting audio stream for wake word detection...")
                if not voice_interface.start_audio_stream():
                    print("Pathos: Critical - Failed to restart audio stream after command. Exiting always-listening mode.")
                    break
                else:
                    print(f"Pathos: Listening again for wake word(s): {voice_interface.porcupine_keywords_list or 'None Configured! Check .env'}.")

    except KeyboardInterrupt:
        print("\nPathos: Always-listening mode interrupted by user (Ctrl+C).")
    except Exception as e:
        print(f"Pathos: An unexpected error occurred in always-listening mode: {e}")
        import traceback # Import here to avoid top-level if only used in except
        traceback.print_exc()
    finally:
        print("Pathos: Stopping audio stream and cleaning up resources for always-listening mode...")
        voice_interface.stop_audio_stream()
        print("Pathos: Exited always-listening mode's main loop.")


if __name__ == '__main__':
    run_assistant()
