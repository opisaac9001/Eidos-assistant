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

if __name__ == '__main__':
    run_assistant()
