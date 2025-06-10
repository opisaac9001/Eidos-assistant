import yaml
import os
from openai import OpenAI, APIConnectionError, APIStatusError

class LLMEngine:
    def __init__(self,
                 persona_config_path="persona_config.yaml",
                 api_base_url: str = "http://localhost:11434/v1",
                 api_key: str = "NA"):
        # Construct the absolute path to the persona config file
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.persona_config_path = os.path.join(base_dir, persona_config_path)
        self.persona = None
        self.system_prompt = "You are a helpful AI assistant." # Default prompt

        self.api_base_url = api_base_url
        self.api_key = api_key
        self.client = None

        try:
            self.client = OpenAI(base_url=self.api_base_url, api_key=self.api_key)
            print(f"LLMEngine initialized with API base URL: {self.api_base_url}")
        except Exception as e:
            print(f"Error initializing OpenAI client: {e}")
            # self.client remains None

        self.load_persona() # Load persona after client init attempt
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
        Now attempts to connect to an LLM.
        """
        if not self.client:
            return "Eidos (error): OpenAI client not initialized. Cannot connect to LLM."

        assistant_name = self.get_persona_attribute('identity.name') or "Eidos" # Default to Eidos
        # assistant_tone = self.get_persona_attribute('tone') or "neutral" # Tone is part of system prompt

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input}
        ]

        try:
            completion = self.client.chat.completions.create(
                model="local-model", # Model name is often ignored by local servers but required by API
                messages=messages,
                temperature=0.7,
            )
            response_content = completion.choices[0].message.content
            return response_content.strip()
        except APIConnectionError as e:
            error_msg = f"Error connecting to LLM API at {self.api_base_url}: {e}"
            print(error_msg)
            return f"{assistant_name} (error): {error_msg}"
        except APIStatusError as e:
            error_msg = f"LLM API returned an error: Status {e.status_code}, Response: {e.response}"
            print(error_msg)
            return f"{assistant_name} (error): {error_msg}"
        except Exception as e:
            error_msg = f"An unexpected error occurred during LLM call: {e}"
            print(error_msg)
            return f"{assistant_name} (error): {error_msg}"

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
    print("Attempting to load LLMEngine with default local LLM settings...")
    engine = LLMEngine() # Uses default persona_config.yaml and API URL

    if engine.persona:
        print("\nPersona loaded successfully.")
        print(f"Assistant Name (from persona): {engine.get_persona_attribute('identity.name')}")
        print(f"System Prompt: {engine.system_prompt}")
    else:
        print("\nWarning: Failed to load persona or persona is empty.")
        print(f"Using default system prompt: {engine.system_prompt}")

    if not engine.client:
        print("\nError: OpenAI client failed to initialize. LLM calls will not work.")
    else:
        print("\nOpenAI client initialized.")

    print("\nAttempting to get a response from LLM via get_response():")
    user_query = "Tell me a fun fact about Python programming."
    print(f"User Query: \"{user_query}\"")

    response = engine.get_response(user_query)
    print(f"\nLLM Response (or error):")
    print(response)

    print("\n---")
    print("Note: If the response above is an error (e.g., connection error), ensure your local LLM server ")
    print("(like Ollama with a model such as 'llama2' or 'gemma:2b' pulled and served) is running and accessible ")
    print(f"at the configured API base URL ({engine.api_base_url}).")
    print("If the client failed to initialize, check OpenAI library installation and API key/URL if modified.")
    print("\nLLMEngine direct execution test complete.")
