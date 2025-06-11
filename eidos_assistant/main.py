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
                else:
                    print(f"Eidos: Unknown command '{command}'. Try /remember, /recall, /forget, /say, /system_prompt, /listen, /always_listen, /ha_status, /ha_toggle, /ha_list_entities, /kb_add_file, /kb_add_directory, or /weather.")
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
