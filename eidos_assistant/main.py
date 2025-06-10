import sys
import os

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
