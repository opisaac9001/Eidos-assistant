import yaml
import os

class LLMEngine:
    def __init__(self, persona_config_path="persona_config.yaml"):
        # Construct the absolute path to the persona config file
        # Assuming persona_config.yaml is in the same directory as this script (core/)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.persona_config_path = os.path.join(base_dir, persona_config_path)
        self.persona = None
        self.system_prompt = "You are a helpful AI assistant." # Default prompt
        self.load_persona()
        if self.persona: # If persona loaded successfully
            self.system_prompt = self._construct_system_prompt()

    def _construct_system_prompt(self) -> str:
        """Constructs the system prompt based on the loaded persona."""
        if not self.persona:
            return "You are a helpful AI assistant." # Default if no persona

        name = self.get_persona_attribute('identity.name') or "Assistant"
        background = self.get_persona_attribute('identity.background_story') or "I am a large language model."
        tone = self.get_persona_attribute('tone') or "helpful"

        concise_pref = self.get_persona_attribute('preferences.prefers_concise_answers')
        if concise_pref is None: # Handles case where the key might be missing entirely
            conciseness = "detailed" # Default if preference not specified
        else:
            conciseness = "concise" if concise_pref else "detailed"

        prompt = f"You are {name}, a {tone} assistant. "
        prompt += f"Your background is: '{background}'. "
        prompt += f"You prefer {conciseness} answers. "
        # Future: Add more persona elements like signature phrases or quirks if desired

        # Example: Handling a list preference (likes_analogies)
        likes_analogies = self.get_persona_attribute('preferences.likes_analogies')
        if likes_analogies is True: # Explicitly check for True
            prompt += "You like to use analogies in your explanations. "

        return prompt.strip()

    def get_response(self, user_input: str) -> str:
        """
        Generates a response to user input.
        Currently a placeholder that shows persona attributes and system prompt.
        """
        assistant_name = self.get_persona_attribute('identity.name') or "Assistant"
        assistant_tone = self.get_persona_attribute('tone') or "neutral"

        # In a real scenario, self.system_prompt and user_input would go to an LLM.
        # For now, we simulate a response:
        response = f"{assistant_name} ({assistant_tone}): You said '{user_input}'. "\
                   f"I'm still learning how to respond fully! (System prompt: '{self.system_prompt}')"
        return response

    def load_persona(self):
        """Loads the persona configuration from the YAML file."""
        try:
            with open(self.persona_config_path, 'r') as f:
                self.persona = yaml.safe_load(f)
            if not self.persona:
                print(f"Warning: Persona configuration file '{self.persona_config_path}' is empty or invalid.")
                self.persona = {} # Default to an empty persona
        except FileNotFoundError:
            print(f"Error: Persona configuration file not found at '{self.persona_config_path}'.")
            self.persona = {} # Default to an empty persona
        except yaml.YAMLError as e:
            print(f"Error: Could not parse persona configuration file '{self.persona_config_path}'. Invalid YAML: {e}")
            self.persona = {} # Default to an empty persona
        except Exception as e:
            print(f"An unexpected error occurred while loading the persona: {e}")
            self.persona = {}

    def get_persona_attribute(self, attribute_path):
        """
        Retrieves a specific attribute from the loaded persona using a dot-separated path.
        Example: get_persona_attribute("identity.name")
        """
        if not self.persona:
            return None

        keys = attribute_path.split('.')
        value = self.persona
        try:
            for key in keys:
                if isinstance(value, dict):
                    value = value[key]
                elif isinstance(value, list):
                    try:
                        idx = int(key)
                        value = value[idx]
                    except (ValueError, IndexError):
                        return None # Key is not a valid integer index or out of bounds
                else:
                    # Path tries to go deeper, but current value is not a collection
                    return None
            return value
        except (KeyError, TypeError, IndexError):
            return None

if __name__ == '__main__':
    # Example usage (assuming persona_config.yaml is in the same directory)
    print("Attempting to load LLMEngine...")
    # For this example to run directly, persona_config.yaml needs to be in the same dir as llm_engine.py
    # In a real application, paths might be managed differently.
    engine = LLMEngine(persona_config_path="persona_config.yaml")

    if engine.persona:
        print("\nPersona loaded successfully:")
        # print(yaml.dump(engine.persona, indent=2)) # Using yaml.dump for pretty print

        print(f"\nAssistant Name: {engine.get_persona_attribute('identity.name')}")
        print(f"Assistant Tone: {engine.get_persona_attribute('tone')}")
        print(f"Greeting example: {engine.get_persona_attribute('signature_phrases.greeting.0')}")
        print(f"\nSystem Prompt:\n{engine.system_prompt}")
    else:
        print("\nFailed to load persona or persona is empty.")
        print(f"\nDefault System Prompt:\n{engine.system_prompt}")


    print("\nTesting non-existent attribute:")
    print(f"Non-existent: {engine.get_persona_attribute('identity.age')}")

    print("\nTesting get_response method:")
    user_query = "Hello there!"
    simulated_response = engine.get_response(user_query)
    print(f"User Query: \"{user_query}\"")
    print(f"Simulated Response: \"{simulated_response}\"")

    print("\nLLMEngine loading test complete.")
