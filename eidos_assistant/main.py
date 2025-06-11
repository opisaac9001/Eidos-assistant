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

    try: # Moved try block to encompass the while loop for proper finally execution
        while True:
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
                elif command == "/kb_add_file":
                    file_path = args_str.strip()
                    if not file_path:
                        print("Pathos: Usage: /kb_add_file <file_path>")
                    elif not engine.knowledge_base:
                        print("Pathos: Knowledge Base is not available or not configured.")
                    elif not os.path.exists(file_path) or not os.path.isfile(file_path):
                        print(f"Pathos: File not found or is not a file: {file_path}")
                    else:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            document_id = os.path.basename(file_path)
                            print(f"Pathos: Adding file '{file_path}' (ID: {document_id}) to Knowledge Base...")
                            engine.knowledge_base.add_document(document_content=content, document_id=document_id)
                            # KB.add_document() prints its own status.
                            print(f"Pathos: Processing for '{document_id}' complete. Check logs from KnowledgeBase.")
                        except Exception as e:
                            print(f"Pathos: Error reading or processing file {file_path}: {e}")

                elif command == "/kb_add_directory":
                    directory_path = args_str.strip()
                    if not directory_path:
                        print("Pathos: Usage: /kb_add_directory <directory_path>")
                    elif not engine.knowledge_base:
                        print("Pathos: Knowledge Base is not available or not configured.")
                    elif not os.path.exists(directory_path) or not os.path.isdir(directory_path):
                        print(f"Pathos: Directory not found or is not a directory: {directory_path}")
                    else:
                        print(f"Pathos: Scanning directory '{directory_path}' for documents to add...")
                        added_count = 0
                        skipped_count = 0
                        supported_extensions = ['.txt', '.md']
                        for root_dir, _, files_in_dir in os.walk(directory_path):
                            for file_item in files_in_dir:
                                if any(file_item.lower().endswith(ext) for ext in supported_extensions):
                                    current_file_path = os.path.join(root_dir, file_item)
                                    try:
                                        with open(current_file_path, 'r', encoding='utf-8') as f:
                                            content = f.read()
                                        # Use relative path from the input directory_path as document_id
                                        document_id = os.path.relpath(current_file_path, directory_path)
                                        print(f"Pathos: Adding file '{current_file_path}' (ID: {document_id}) to Knowledge Base...")
                                        engine.knowledge_base.add_document(document_content=content, document_id=document_id)
                                        added_count += 1
                                    except Exception as e:
                                        print(f"Pathos: Error reading or processing file {current_file_path}: {e}")
                                        skipped_count += 1
                                else:
                                    # Silently skip non-supported files or print a debug message if desired
                                    # print(f"Skipping non-supported file: {file_item}")
                                    skipped_count +=1
                        print(f"Pathos: Directory scan complete. Added {added_count} documents. Skipped/failed {skipped_count} files.")
                elif command == "/weather":
                    args_list = args_str.strip().split()
                    city_parts = []
                    units = "metric" # Default

                    # Basic parsing for city name and --units flag
                    # This is a simple parser; more complex libraries like argparse could be used for more robust CLI
                    idx = 0
                    while idx < len(args_list):
                        part = args_list[idx]
                        if part.lower() == "--units":
                            if idx + 1 < len(args_list) and args_list[idx+1].lower() in ["imperial", "metric"]:
                                units = args_list[idx+1].lower()
                                idx += 1 # Skip next part as it's consumed
                            else:
                                # If just --units is provided, or invalid unit, could default or error
                                # For now, let's assume if --units is there, next should be unit, or it's an error in usage
                                # However, the initial problem statement implied --units imperial, so let's stick to that simplicity:
                                # if next part is imperial, set it, otherwise it might be part of city or ignored.
                                # A better parser would handle this more gracefully.
                                pass # Handled by the check below if 'imperial' or 'metric' is explicitly found
                        elif part.lower() == "imperial":
                            units = "imperial"
                        elif part.lower() == "metric":
                            units = "metric" # Allow explicit metric
                        else:
                            city_parts.append(part)
                        idx += 1

                    city_name = " ".join(city_parts)

                    if not city_name:
                        print("Pathos: Usage: /weather <city_name> [--units imperial|metric]")
                    elif not engine.weather_skill:
                        print("Pathos: Weather skill is not available or not configured.")
                    elif not engine.weather_skill.api_key or engine.weather_skill.api_key == "YOUR_OPENWEATHERMAP_API_KEY_HERE":
                        print("Pathos: Weather skill API key not configured. Please set OPENWEATHERMAP_API_KEY in your .env file.")
                    else:
                        print(f"Pathos: Getting current weather for '{city_name}' (units: {units})...")
                        weather_data = engine.weather_skill.get_current_weather(city_name, units)
                        if weather_data:
                            temp_unit = "°C" if weather_data['units'] == "metric" else "°F"
                            wind_speed_unit = "m/s" if weather_data['units'] == "metric" else "mph"
                            output = (
                                f"Weather in {weather_data['city']}, {weather_data['country']}:\n"
                                f"  Temperature: {weather_data['temperature']}{temp_unit} (Feels like: {weather_data['feels_like']}{temp_unit})\n"
                                f"  Condition:   {weather_data['description']}\n"
                                f"  Humidity:    {weather_data['humidity']}%\n"
                                f"  Wind Speed:  {weather_data['wind_speed']} {wind_speed_unit}"
                            )
                            print(output)
                        else:
                            print(f"Pathos: Could not retrieve weather for '{city_name}'. The skill might have logged more details.")
                elif command == "/search":
                    search_query = args_str.strip()
                    if not search_query:
                        print("Pathos: Usage: /search <your search query>")
                    elif not engine.web_search_skill:
                        print("Pathos: Web Search skill is not available.")
                    else:
                        print(f"Pathos: Searching the web for: '{search_query}'...")
                        results = engine.web_search_skill.search(search_query, num_results=5)
                        if results: # Check if results is not None and not empty
                            print("Pathos: Web Search Results:")
                            for i, result in enumerate(results):
                                print(f"--- Result {i+1} ---")
                                print(f"  Title: {result.get('title', 'N/A')}")
                                print(f"  Snippet: {result.get('snippet', 'N/A')}")
                                print(f"  URL: {result.get('url', 'N/A')}")
                            print("--- End of Results ---")
                        elif results == []: # Explicitly check for empty list (no results found)
                            print("Pathos: No results found for your query.")
                        else: # Results is None (an error occurred in the skill)
                            print(f"Pathos: An error occurred while searching for '{search_query}'. Check skill logs.")
                elif command == "/news":
                    args_list = args_str.strip().split()
                    category_from_args = None
                    limit_from_args = 5 # Default limit

                    category_parts_temp = []
                    i = 0
                    while i < len(args_list):
                        part = args_list[i]
                        if part.lower() == "--limit":
                            if i + 1 < len(args_list):
                                try:
                                    limit_from_args = int(args_list[i+1])
                                    i += 1 # consume the number
                                except ValueError:
                                    print(f"Pathos: Invalid number for --limit ('{args_list[i+1]}'). Using default {limit_from_args}.")
                            else:
                                print("Pathos: --limit specified without a number. Using default.")
                        else:
                            category_parts_temp.append(part)
                        i += 1

                    if category_parts_temp:
                        category_from_args = " ".join(category_parts_temp)
                        if category_from_args.lower() == "all":
                            category_from_args = None # Pass None to skill to fetch all

                    if not engine.news_skill:
                        print("Pathos: News skill is not available.")
                    else:
                        cat_display_name = category_from_args if category_from_args else "All Categories"
                        print(f"Pathos: Fetching news headlines (Category: {cat_display_name}, Limit: {limit_from_args})...")
                        headlines = engine.news_skill.fetch_news(category=category_from_args, num_headlines=limit_from_args)

                        if headlines:
                            print(f"Pathos: Recent Headlines (Category: {cat_display_name}):")
                            for idx, headline_item in enumerate(headlines):
                                print(f"--- Headline {idx+1} ---")
                                print(f"  Title: {headline_item.get('title', 'N/A')}")
                                print(f"  Published: {headline_item.get('published', 'N/A')}")
                                print(f"  Source: {headline_item.get('source_feed', 'N/A')}")
                                print(f"  Link: {headline_item.get('link', '#')}")
                                summary = headline_item.get('summary', 'N/A')
                                print(f"  Summary: {summary[:200]}{'...' if len(summary) > 200 else ''}")
                            print("--- End of Headlines ---")
                        elif headlines == []: # Empty list, no error but no results
                            print(f"Pathos: No news headlines found for '{cat_display_name}'.")
                        else: # None, an error occurred
                            print("Pathos: An error occurred while fetching news headlines. Skill might have logged details.")
                else:
                    print(f"Eidos: Unknown command '{command}'. Try /remember, /recall, /forget, /say, /system_prompt, /listen, /always_listen, /ha_status, /ha_toggle, /ha_list_entities, /kb_add_file, /kb_add_directory, /weather, /search, or /news.")
                continue # Skip sending command to LLM

            # Only try to get LLM response if client is available
            if not engine.client:
                print("Eidos (Error): LLM client not available. Cannot process general queries.")
                continue

            assistant_response = engine.get_response(user_input)
            print(f"Eidos: {assistant_response}")

    except KeyboardInterrupt:
        print("\nExiting Eidos Assistant due to interrupt. Goodbye!")
    except Exception as e:
        print(f"An unexpected error occurred in the main loop: {e}")
    finally:
        # This cleanup runs after the main loop exits (normally or due to exception/KeyboardInterrupt)
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
    # run_assistant() # Commented out for dedicated RAG testing

    print("\n--- Starting Eidos RAG System Test ---")
    # This test sequence assumes LLMEngine and KnowledgeBase are correctly initialized.
    # LLMEngine's __init__ will try to load .env for API keys, model names, etc.
    # KnowledgeBase's __init__ (called by LLMEngine) sets up ChromaDB.

    engine = LLMEngine() # Initialize the engine

    if not engine.knowledge_base:
        print("FATAL: KnowledgeBase not initialized in LLMEngine. Cannot proceed with RAG tests.")
        sys.exit(1)

    # Ensure the KB is clean for the test, if it's persistent and data might exist.
    # The KB by default persists to eidos_assistant/data/kb_chroma_db/
    # We should clear it before adding test documents.
    print("\nClearing existing KnowledgeBase collection for a clean test run...")
    if engine.knowledge_base.collection: # Check if collection exists
        # A more direct way to clear a collection in ChromaDB is to delete and recreate it.
        # Or, if the KB has a method like clear_collection() or delete_all_documents().
        # The KnowledgeBase class has `delete_collection` and `clear_all_data_and_shutdown_persistent_client`
        # For a full reset of this specific test, deleting the collection is good.
        # If this test suite is the ONLY user of this collection name, then deleting is fine.
        # Otherwise, be careful. Let's assume for this test, we can delete the default collection.
        try:
            collection_name = engine.knowledge_base.collection_name
            engine.knowledge_base.delete_collection() # Deletes the collection
            # Recreate it for the test
            engine.knowledge_base.collection = engine.knowledge_base.client.get_or_create_collection(
                name=collection_name
            )
            print(f"KnowledgeBase collection '{collection_name}' cleared and recreated for test.")
        except Exception as e:
            print(f"Error clearing/recreating collection: {e}. Test results may be affected by old data.")

    # Define paths to sample files (relative to project root: eidos_assistant/)
    # The script main.py is in eidos_assistant/, so relative paths like "data/..." are correct.
    sky_doc_path = "data/test_doc_sky.txt"
    eidos_doc_path = "data/test_doc_eidos.md"

    # --- Test Ingestion ---
    print("\n--- Testing Document Ingestion ---")
    documents_to_ingest = {
        "test_doc_sky": sky_doc_path,
        "test_doc_eidos": eidos_doc_path
    }

    for doc_id, file_path in documents_to_ingest.items():
        if not os.path.exists(file_path):
            print(f"ERROR: Test file not found: {file_path}. Skipping ingestion for this file.")
            continue
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Using the custom doc_id for clarity in tests
            print(f"Ingesting document: '{file_path}' with ID: '{doc_id}'")
            engine.knowledge_base.add_document(document_content=content, document_id=doc_id)
            # add_document in KnowledgeBase should print its own chunking/success info.
        except Exception as e:
            print(f"Error ingesting document {file_path}: {e}")

    # --- Test Queries ---
    print("\n--- Testing Queries ---")
    test_queries = [
        "What color is the sky during the day?",
        "What can be seen at night according to the documents?",
        "Tell me about Eidos Assistant's features.",
        "What is the capital of Canada?" # General knowledge, expect no KB context
    ]

    if not engine.client:
        print("\nWARNING: LLM client not initialized in LLMEngine. Query responses will be error messages.")
        print("Ensure your LLM server is running and accessible.")

    for i, query_text in enumerate(test_queries):
        print(f"\n--- Query {i+1}: \"{query_text}\" ---")
        # The get_response method will internally try to use KB context
        response = engine.get_response(query_text)
        print(f"Pathos (Response to Query {i+1}): {response}")
        time.sleep(1) # Small delay if hitting a rate-limited local LLM

    # --- Cleanup ---
    # This cleanup is important if the KB is persistent.
    # The default KB path is 'eidos_assistant/data/kb_chroma_db'
    print("\n--- Test Cleanup ---")
    if engine.knowledge_base and engine.knowledge_base.persist_directory:
        print(f"Attempting to clean up KnowledgeBase data from: {engine.knowledge_base.resolved_persist_directory}")
        try:
            # This method in KnowledgeBase should handle deleting the collection and rmtree
            engine.knowledge_base.clear_all_data_and_shutdown_persistent_client()
            print("KnowledgeBase persistence directory should now be cleaned up.")
        except Exception as e:
            print(f"Error during KnowledgeBase cleanup: {e}")
            print(f"Manual cleanup of '{engine.knowledge_base.resolved_persist_directory}' might be needed.")
    else:
        print("KnowledgeBase is in-memory or was not initialized with a persist_directory. No disk cleanup needed by main.py for KB.")

    # Also remove the test doc files created for this test run
    try:
        if os.path.exists(sky_doc_path):
            os.remove(sky_doc_path)
            print(f"Test file '{sky_doc_path}' removed.")
        if os.path.exists(eidos_doc_path):
            os.remove(eidos_doc_path)
            print(f"Test file '{eidos_doc_path}' removed.")
    except Exception as e:
        print(f"Error removing test document files: {e}")


    print("\n--- Eidos RAG System Test Complete ---")


    print("\n\n--- Starting Eidos WeatherSkill Integration Test ---")

    # LLMEngine (engine) is already initialized from the RAG test.
    # It would have also initialized WeatherSkill.

    print("\nIMPORTANT: For live weather API calls, ensure OPENWEATHERMAP_API_KEY is set in your .env file.")
    if not engine.weather_skill:
        print("FATAL: WeatherSkill not initialized in LLMEngine. Cannot proceed with WeatherSkill tests.")
        sys.exit(1)

    if not engine.weather_skill.api_key or engine.weather_skill.api_key == "YOUR_OPENWEATHERMAP_API_KEY_HERE":
        print("WARNING: WeatherSkill API key not configured. Live API calls will fail.")
    else:
        print(f"WeatherSkill API key found: {engine.weather_skill.api_key[:4]}...{engine.weather_skill.api_key[-4:]}")

    def print_formatted_weather(weather_data):
        if not weather_data:
            print("No weather data to format or an error occurred.")
            return
        temp_unit = "°C" if weather_data.get('units') == "metric" else "°F"
        wind_speed_unit = "m/s" if weather_data.get('units') == "metric" else "mph"
        output = (
            f"Weather in {weather_data.get('city', 'N/A')}, {weather_data.get('country', 'N/A')}:\n"
            f"  Temperature: {weather_data.get('temperature', 'N/A')}{temp_unit} (Feels like: {weather_data.get('feels_like', 'N/A')}{temp_unit})\n"
            f"  Condition:   {weather_data.get('description', 'N/A')}\n"
            f"  Humidity:    {weather_data.get('humidity', 'N/A')}%\n"
            f"  Wind Speed:  {weather_data.get('wind_speed', 'N/A')} {wind_speed_unit}"
        )
        print(output)

    # --- Direct Skill Invocation Tests ---
    print("\n--- Testing Direct Skill Invocation ---")

    print("\n--- Test Case 1: /weather London ---")
    weather_data_london = engine.weather_skill.get_current_weather("London", "metric")
    print_formatted_weather(weather_data_london)
    if not weather_data_london:
         print("(Failed to get weather for London - check API key or network if this was unexpected)")


    print("\n--- Test Case 2: /weather \"New York\" --units imperial ---")
    weather_data_ny = engine.weather_skill.get_current_weather("New York", "imperial")
    print_formatted_weather(weather_data_ny)
    if not weather_data_ny:
        print("(Failed to get weather for New York - check API key or network if this was unexpected)")

    print("\n--- Test Case 3: /weather InvalidCityName123 ---")
    weather_data_invalid = engine.weather_skill.get_current_weather("InvalidCityName123", "metric")
    if weather_data_invalid:
        print_formatted_weather(weather_data_invalid) # Should ideally not happen
    else:
        print("Correctly failed or could not get weather for InvalidCityName123 (skill should have printed error).")

    # --- LLM Integration Tests (Simulating LLM JSON output) ---
    print("\n--- Testing LLM Integration (Simulated LLM JSON) ---")

    if not engine.client:
        print("\nWARNING: LLM client (OpenAI client) not initialized in LLMEngine. ")
        print("Simulated LLM JSON tests will still run the skill logic, but a real LLM query would fail.")

    print("\n--- Test Case 4: LLM Query - Weather in Berlin (metric) ---")
    simulated_llm_output_berlin = '{"tool_name": "weather", "action": "get_current_weather", "city": "Berlin", "units": "metric"}'
    print(f"Simulating LLM output: {simulated_llm_output_berlin}")
    response_berlin = engine.get_response(simulated_llm_output_berlin)
    print(f"Pathos response: {response_berlin}")

    print("\n--- Test Case 5: LLM Query - Weather in Phoenix (imperial) ---")
    simulated_llm_output_phoenix = '{"tool_name": "weather", "action": "get_current_weather", "city": "Phoenix", "units": "imperial"}'
    print(f"Simulating LLM output: {simulated_llm_output_phoenix}")
    response_phoenix = engine.get_response(simulated_llm_output_phoenix)
    print(f"Pathos response: {response_phoenix}")

    print("\n--- Eidos WeatherSkill Integration Test Complete ---")


    print("\n\n--- Starting Eidos WebSearchSkill Integration Test ---")
    # LLMEngine (engine) is already initialized.

    print("\nIMPORTANT: WebSearchSkill uses DuckDuckGo and requires network access. Results may vary or fail based on network conditions.")
    if not engine.web_search_skill:
        print("FATAL: WebSearchSkill not initialized in LLMEngine. Cannot proceed with WebSearchSkill tests.")
        sys.exit(1) # Exit if the skill isn't even there

    def print_search_results(results, header="Web Search Results:"):
        if results is None: # None indicates an error during search
            print(f"{header} Search failed or an error occurred.")
            return
        if not results: # Empty list indicates no results found
            print(f"{header} No results found.")
            return
        print(header)
        for i, res in enumerate(results):
            print(f"  --- Result {i+1} ---")
            print(f"  Title: {res.get('title', 'N/A')}")
            print(f"  Snippet: {res.get('snippet', 'N/A')[:150]}...") # Show more snippet
            print(f"  URL: {res.get('url', 'N/A')}")
        print("  --- End of Results ---")

    # --- Direct Skill Invocation Tests ---
    print("\n--- Testing Direct Skill Invocation (WebSearchSkill) ---")

    print("\n--- Test Case 1: Search 'python programming benefits' ---")
    direct_results1 = engine.web_search_skill.search("python programming benefits", num_results=2)
    print_search_results(direct_results1, "Direct search for 'python programming benefits':")

    print("\n--- Test Case 2: Search for gibberish 'ajskdfhaksjdfhasdkjfhasd' ---")
    direct_results2 = engine.web_search_skill.search("ajskdfhaksjdfhasdkjfhasd", num_results=3)
    print_search_results(direct_results2, "Direct search for 'ajskdfhaksjdfhasdkjfhasd':")


    # --- LLM Integration Tests (Simulating LLM JSON output and Synthesis) ---
    print("\n--- Testing LLM Integration with WebSearchSkill (Simulated LLM JSON & Synthesis) ---")

    if not engine.client:
        print("\nWARNING: LLM client (OpenAI client) not initialized in LLMEngine. ")
        print("LLM synthesis part of the test will likely fail or return error messages.")

    original_user_query_for_web_search = "Who is the current prime minister of Canada?"
    print(f"\n--- Test Case 3: LLM Query - '{original_user_query_for_web_search}' (expecting web search) ---")

    # Step A: Simulate the LLM deciding to use the web_search tool.
    # The LLMEngine's get_response method is designed to handle this:
    # If it receives a JSON from the LLM that's a web_search request, it will perform the search,
    # then construct a new prompt with results, and call the LLM *again* for synthesis.

    simulated_llm_search_request_json = f'{{"tool_name": "web_search", "action": "search", "query": "{original_user_query_for_web_search}"}}'
    print(f"Simulated first LLM output (request to search): {simulated_llm_search_request_json}")

    # This single call to get_response should trigger the whole two-step process if an LLM is available for the synthesis part.
    # The `user_input` for this `get_response` call is the original user query, which `get_response` will use
    # if it needs to construct the synthesis prompt.
    print("\nCalling engine.get_response() with the simulated search JSON...")
    final_answer_from_search = engine.get_response(simulated_llm_search_request_json)
    # This response *should* be the synthesized answer from the second LLM call if all went well.
    # The LLM Engine's get_response will have print statements indicating the search and synthesis steps.
    print(f"\nPathos final synthesized response after web search: {final_answer_from_search}")

    print("\n--- Eidos WebSearchSkill Integration Test Complete ---")


    print("\n\n--- Starting Eidos NewsSkill Integration Test ---")
    # LLMEngine (engine) is already initialized.

    print("\nIMPORTANT: NewsSkill uses feedparser and requires network access to fetch RSS feeds. Results may vary or fail based on network conditions or feed availability.")
    if not engine.news_skill: # Check if the legacy attribute exists, or use new framework check if applicable
        # If NewsSkill were refactored and registered, this check would be:
        # if "get_news" not in engine.skills: # Assuming "get_news" is its tool_name
        print("FATAL: NewsSkill not initialized in LLMEngine (or not registered if refactored). Cannot proceed with NewsSkill tests.")
        # For now, assuming legacy self.news_skill attribute for testing this specific skill as it's not refactored yet.
        if not hasattr(engine, 'news_skill') or not engine.news_skill:
             sys.exit(1)


    def print_formatted_headlines(headlines, category_title="News"):
        if headlines is None: # None indicates an error during fetch
            print(f"Failed to fetch headlines for {category_title} or an error occurred.")
            return
        if not headlines: # Empty list indicates no results found
            print(f"No headlines found for {category_title}.")
            return

        print(f"\nRecent Headlines for {category_title} (found {len(headlines)}):")
        for i, h in enumerate(headlines):
            print(f"  {i+1}. Title: {h.get('title', 'N/A')}")
            print(f"     Published: {h.get('published', 'N/A')}")
            print(f"     Source: {h.get('source_feed', 'N/A')}")
            print(f"     Link: {h.get('link', '#')}")
            summary = h.get('summary', 'N/A')
            print(f"     Summary: {summary[:150] + '...' if len(summary) > 150 else summary}")
            print("  ---")

    # --- Direct Skill Invocation Tests (using legacy self.news_skill) ---
    print("\n--- Testing Direct Skill Invocation (NewsSkill - Legacy Access) ---")

    if hasattr(engine, 'news_skill') and engine.news_skill:
        print("\n--- Test Case 1: /news (all categories, 5 headlines) ---")
        headlines1 = engine.news_skill.fetch_news(category=None, num_headlines=5)
        print_formatted_headlines(headlines1, "All Categories (Default Limit 5)")

        print("\n--- Test Case 2: /news Tech News --limit 2 ---")
        headlines2 = engine.news_skill.fetch_news(category="Tech News", num_headlines=2)
        print_formatted_headlines(headlines2, "Tech News (Limit 2)")

        print("\n--- Test Case 3: /news NonExistentCategory --limit 3 ---")
        headlines3 = engine.news_skill.fetch_news(category="NonExistentCategory", num_headlines=3)
        print_formatted_headlines(headlines3, "NonExistentCategory (Fallback to All, Limit 3)")
    else:
        print("Skipping direct NewsSkill tests as legacy self.news_skill is not available.")


    # --- LLM Integration Tests (Simulating LLM JSON output) ---
    print("\n--- Testing LLM Integration with NewsSkill (Simulated LLM JSON) ---")

    if not engine.client:
        print("\nWARNING: LLM client (OpenAI client) not initialized in LLMEngine. ")
        print("Simulated LLM JSON tests will still run the skill logic, but a real LLM query for other purposes would fail.")

    print("\n--- Test Case 4: LLM Query - 'Any science news?' (expecting 2 headlines) ---")
    # This simulated JSON should match what the LLM is prompted to produce for the NewsSkill
    # (i.e. tool_name: "news", action: "fetch_news")
    simulated_llm_news_request_json = '{"tool_name": "news", "action": "fetch_news", "category": "Science News", "num_headlines": "2"}'
    print(f"Simulated LLM output (request for news): {simulated_llm_news_request_json}")

    response_science_news = engine.get_response(simulated_llm_news_request_json)
    print(f"Pathos response: {response_science_news}")

    print("\n--- Eidos NewsSkill Integration Test Complete ---")


    print("\n\n--- Starting Eidos NewsSkill Integration Test ---")
    # LLMEngine (engine) is already initialized.

    print("\nIMPORTANT: NewsSkill uses feedparser and requires network access to fetch RSS feeds. Results may vary or fail based on network conditions or feed availability.")
    if not engine.news_skill:
        print("FATAL: NewsSkill not initialized in LLMEngine. Cannot proceed with NewsSkill tests.")
        sys.exit(1) # Exit if the skill isn't even there

    def print_formatted_headlines(headlines, category_title="News"):
        if headlines is None: # None indicates an error during fetch
            print(f"Failed to fetch headlines for {category_title} or an error occurred.")
            return
        if not headlines: # Empty list indicates no results found
            print(f"No headlines found for {category_title}.")
            return

        print(f"\nRecent Headlines for {category_title} (found {len(headlines)}):")
        for i, h in enumerate(headlines):
            print(f"  {i+1}. Title: {h.get('title', 'N/A')}")
            print(f"     Published: {h.get('published', 'N/A')}")
            print(f"     Source: {h.get('source_feed', 'N/A')}")
            print(f"     Link: {h.get('link', '#')}")
            summary = h.get('summary', 'N/A')
            print(f"     Summary: {summary[:150] + '...' if len(summary) > 150 else summary}")
            print("  ---")

    # --- Direct Skill Invocation Tests ---
    print("\n--- Testing Direct Skill Invocation (NewsSkill) ---")

    print("\n--- Test Case 1: /news (all categories, 5 headlines) ---")
    headlines1 = engine.news_skill.fetch_news(category=None, num_headlines=5)
    print_formatted_headlines(headlines1, "All Categories (Default Limit 5)")

    print("\n--- Test Case 2: /news Tech News --limit 2 ---")
    headlines2 = engine.news_skill.fetch_news(category="Tech News", num_headlines=2)
    print_formatted_headlines(headlines2, "Tech News (Limit 2)")

    print("\n--- Test Case 3: /news NonExistentCategory --limit 3 ---")
    # NewsSkill's current logic defaults to "All Feeds" if category is not found
    headlines3 = engine.news_skill.fetch_news(category="NonExistentCategory", num_headlines=3)
    print_formatted_headlines(headlines3, "NonExistentCategory (Fallback to All, Limit 3)")


    # --- LLM Integration Tests (Simulating LLM JSON output) ---
    print("\n--- Testing LLM Integration with NewsSkill (Simulated LLM JSON) ---")

    if not engine.client:
        print("\nWARNING: LLM client (OpenAI client) not initialized in LLMEngine. ")
        print("Simulated LLM JSON tests will still run the skill logic, but a real LLM query for other purposes would fail.")

    print("\n--- Test Case 4: LLM Query - 'Any science news?' (expecting 2 headlines) ---")
    simulated_llm_news_request_json = '{"tool_name": "news", "action": "fetch_news", "category": "Science News", "num_headlines": "2"}'
    print(f"Simulated LLM output (request for news): {simulated_llm_news_request_json}")

    # This call to get_response should trigger NewsSkill and format the output.
    # No second LLM call is made by NewsSkill integration itself, it just returns formatted text.
    response_science_news = engine.get_response(simulated_llm_news_request_json)
    print(f"Pathos response: {response_science_news}")

    print("\n--- Eidos NewsSkill Integration Test Complete ---")
