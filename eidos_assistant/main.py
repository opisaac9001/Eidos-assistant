import sys
import os
import re # Added for command parsing

# Add the 'core' directory to sys.path to allow importing LLMEngine
# This assumes main.py is in 'eidos_assistant/' and LLMEngine is in 'eidos_assistant/core/'
current_dir = os.path.dirname(os.path.abspath(__file__))
core_dir = os.path.join(current_dir, 'core')
sys.path.append(core_dir)

try:
    from llm_engine import LLMEngine
except ImportError:
    print("Error: Could not import LLMEngine. Ensure 'llm_engine.py' is in the 'core' directory and core_dir is in sys.path.")
    sys.exit(1)

def run_assistant():
    print("Initializing Eidos Assistant...")

    # The LLMEngine expects persona_config.yaml to be in the same directory as llm_engine.py (core/)
    # It resolves this path internally, so we don't need to pass a modified path here.
    engine = LLMEngine(persona_config_path="persona_config.yaml")

    if not engine.persona:
        print("Error: LLM Engine failed to load persona. Exiting.")
        return

    print(f"Eidos Assistant ({engine.get_persona_attribute('identity.name')}, {engine.get_persona_attribute('tone')}) started.")
    # Access the api_base_url from the engine instance
    print(f"Attempting to connect to LLM at: {engine.api_base_url}")
    print("If this is not your LLM endpoint, you may need to configure it in future versions or directly in code.")
    print("Ensure your OpenAI API-compatible LLM server is running.")
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

                elif command == "/system_prompt": # Added for debugging
                    print(f"Eidos (Debug): Current system prompt is:\n{engine.system_prompt}")

                else:
                    print(f"Eidos: Unknown command '{command}'. Try /remember, /recall, or /forget.")
                continue # Skip sending command to LLM

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
