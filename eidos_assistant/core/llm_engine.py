import yaml
import os

class LLMEngine:
    def __init__(self, persona_config_path="persona_config.yaml"):
        # Construct the absolute path to the persona config file
        # Assuming persona_config.yaml is in the same directory as this script (core/)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.persona_config_path = os.path.join(base_dir, persona_config_path)
        self.persona = None
        self.load_persona()

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
        print(f"Greeting example: {engine.get_persona_attribute('signature_phrases.greeting.0')}") # Accessing first greeting
    else:
        print("\nFailed to load persona or persona is empty.")

    print("\nTesting non-existent attribute:")
    print(f"Non-existent: {engine.get_persona_attribute('identity.age')}")

    print("\nLLMEngine loading test complete.")
