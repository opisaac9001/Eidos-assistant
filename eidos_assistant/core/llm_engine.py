import yaml
import os # Ensure os is imported for getenv and path operations
from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError
from memory import MemoryManager

# import os # os is already imported below
from dotenv import load_dotenv
import sys # Added for sys.path manipulation

# Attempt to load .env, but proceed gracefully if it fails or python-dotenv has issues.
# The os.getenv calls in __init__ will then rely on system-set env vars or use defaults.
try:
    # Using the original robust path construction, hoping it might work once, else defaults will take over.
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    loaded_env = load_dotenv(dotenv_path=dotenv_path)
    print(f"DEBUG: llm_engine.py - dotenv_path: {dotenv_path}, Loaded .env successfully: {loaded_env}")
except Exception as e:
    print(f"DEBUG: llm_engine.py - Error loading .env file: {e}. Proceeding with defaults or system-set environment variables.")

# Dynamically add skills directory to sys.path for importing HomeAssistantSkill
# This ensures that even if LLMEngine is imported from elsewhere, it can find its skills.
try:
    current_script_dir = os.path.dirname(os.path.abspath(__file__)) # core directory
    project_root_dir = os.path.dirname(current_script_dir) # eidos_assistant directory
    skills_dir_path = os.path.join(project_root_dir, 'skills')
    if skills_dir_path not in sys.path:
        sys.path.insert(0, skills_dir_path) # Insert at beginning for priority
    from home_assistant_skill import HomeAssistantSkill
except ImportError as e:
    print(f"LLMEngine Critical Error: Could not import HomeAssistantSkill. Ensure skills module is in the correct path: {e}")
    HomeAssistantSkill = None # Define as None so type hints/checks for ha_skill don't break if import fails

class LLMEngine:
    def __init__(self,
                 persona_config_path="persona_config.yaml",
                 api_base_url=os.getenv("LLM_API_BASE_URL", "http://localhost:11434/v1"),
                 api_key=os.getenv("LLM_API_KEY", "NotNeededForOllama")): # Changed default to match .env expectation
        # Construct the absolute path to the persona config file
        base_dir = os.path.dirname(os.path.abspath(__file__)) # core directory
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

        # Initialize MemoryManager
        # MemoryManager expects path relative to project root (eidos_assistant/)
        self.memory_manager = MemoryManager(memory_file_path="data/memory.json")

        self.load_persona() # Load persona after client init attempt

        # Construct system prompt after persona and memory are available
        if self.persona:
            self.system_prompt = self._construct_system_prompt()
        else: # Ensure system prompt is constructed even if persona fails but memory might be useful
             self.system_prompt = self._construct_system_prompt()

        # Initialize HomeAssistantSkill
        print("LLMEngine: Initializing HomeAssistantSkill...")
        self.ha_skill = None # Initialize to None
        if HomeAssistantSkill: # Check if import was successful
            try:
                self.ha_skill = HomeAssistantSkill()
                if self.ha_skill.ha_token and self.ha_skill.ha_token != "YOUR_LONG_LIVED_ACCESS_TOKEN_HERE":
                    # Defer check_api_status to when a command is actually run, or user can do it.
                    # For now, just confirm it loaded.
                    # if self.ha_skill.check_api_status(): # This makes init slower
                    # print("LLMEngine: HomeAssistantSkill initialized and API status OK.")
                    print("LLMEngine: HomeAssistantSkill initialized. Call check_api_status() on HA skill for full check.")
                    # else:
                    # print("LLMEngine Warning: HomeAssistantSkill initialized, but API status check failed. HA features may not work.")
                else:
                    print("LLMEngine Warning: HomeAssistantSkill initialized, but HA token not configured. HA features disabled.")
            except Exception as e:
                print(f"LLMEngine Error: Failed to initialize HomeAssistantSkill instance: {e}. HA features will be unavailable.")
                self.ha_skill = None # Ensure it's None on error
        else:
            print("LLMEngine Error: HomeAssistantSkill class not available due to import failure. HA features disabled.")


    def _construct_system_prompt(self) -> str:
        """Constructs the system prompt based on the loaded persona and memory."""
        prompt_parts = []

        # Persona-based parts
        if self.persona:
            name = self.get_persona_attribute('identity.name') or "Assistant"
            background = self.get_persona_attribute('identity.background_story') or "I am a large language model."
            tone = self.get_persona_attribute('tone') or "helpful"

            concise_pref = self.get_persona_attribute('preferences.prefers_concise_answers')
            conciseness = "concise" if concise_pref else "detailed"
            if concise_pref is None: # Handles case where the key might be missing
                conciseness = "detailed"


            prompt_parts.append(f"You are {name}, a {tone} assistant.")
            prompt_parts.append(f"Your background is: '{background}'.")
            prompt_parts.append(f"You prefer {conciseness} answers.")

            likes_analogies = self.get_persona_attribute('preferences.likes_analogies')
            if likes_analogies:
                prompt_parts.append("You like to use analogies in your explanations.")
        else:
            prompt_parts.append("You are a helpful AI assistant.") # Fallback if no persona

        # Memory-based parts
        user_name = self.recall("user_profile", "name")
        if user_name:
            prompt_parts.append(f"You are speaking with {user_name}.")

        user_theme_preference = self.recall("user_preferences", "theme")
        if user_theme_preference and user_name: # Only add if user_name is known
            prompt_parts.append(f"{user_name} prefers a {user_theme_preference} theme.")
        elif user_theme_preference: # If theme known but not user name
             prompt_parts.append(f"The user prefers a {user_theme_preference} theme.")


        return " ".join(prompt_parts).strip()

    def refresh_system_prompt(self):
        """Reconstructs and updates the system prompt, typically after memory changes."""
        self.system_prompt = self._construct_system_prompt()
        # print(f"Debug: System prompt refreshed: {self.system_prompt}") # Optional: for debugging

    # Memory Accessor Methods
    def remember(self, category: str, key: str, value: any) -> bool:
        """Stores a value in memory."""
        return self.memory_manager.set_value(category, key, value)

    def recall(self, category: str, key: str) -> any:
        """Recalls a value from memory."""
        return self.memory_manager.get_value(category, key)

    def forget(self, category: str, key: str) -> bool:
        """Forgets a value from memory."""
        return self.memory_manager.delete_value(category, key)

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
    print("Testing LLMEngine. It will use environment variables if available, or defaults.")
    engine = LLMEngine()
    print(f"LLMEngine is using API Base URL: {engine.api_base_url} (Expected from .env or default)")
    print(f"LLMEngine is using API Key: {engine.api_key} (Expected from .env or default)")

    if engine.persona:
        print("\nPersona loaded successfully.")
        print(f"Assistant Name (from persona): {engine.get_persona_attribute('identity.name')}")
        # System prompt is already printed below and after modifications
    else:
        print("\nWarning: Failed to load persona or persona is empty.")
        # Even if persona fails, system_prompt is built from memory/defaults

    # System prompt is printed below, and also after it's modified by memory operations.
    # print(f"Initial System prompt (after persona and memory init): {engine.system_prompt}")

    if not engine.client:
        print("\nError: OpenAI client failed to initialize. LLM calls will not work.")
    else:
        print("\nOpenAI client initialized.") # This is already printed by __init__ if successful

    print(f"\nInitial system prompt: {engine.system_prompt}") # Print current system prompt

    print(f"\nRemembering user name 'Tester'... Result: {engine.remember('user_profile', 'name', 'Tester')}")
    engine.refresh_system_prompt()
    print(f"System prompt after remembering name: {engine.system_prompt}")

    print(f"Recalling user name: {engine.recall('user_profile', 'name')}")

    print(f"Remembering user theme 'dark'... Result: {engine.remember('user_preferences', 'theme', 'dark')}")
    engine.refresh_system_prompt()
    print(f"System prompt after remembering theme: {engine.system_prompt}")

    print(f"\nAttempting to get a response from LLM (will use updated prompt):")
    user_query = "Tell me a fun fact about Python programming."
    print(f"User Query: \"{user_query}\"")

    response = engine.get_response(user_query)
    print(f"\nLLM Response (or error):")
    print(response)

    print(f"\nForgetting user name... Result: {engine.forget('user_profile', 'name')}")
    engine.refresh_system_prompt()
    print(f"System prompt after forgetting name: {engine.system_prompt}")

    print(f"Forgetting user theme... Result: {engine.forget('user_preferences', 'theme')}")
    engine.refresh_system_prompt()
    print(f"System prompt after forgetting theme: {engine.system_prompt}")


    print("\n---")
    print("Note: If the response above is an error (e.g., connection error), ensure your local LLM server ")
    print("(like Ollama with a model such as 'llama2' or 'gemma:2b' pulled and served) is running and accessible ")
    print(f"at the configured API base URL ({engine.api_base_url}).")
    print("The data/memory.json file will reflect the last state of memory operations if they succeeded.")

    print("\n--- LLMEngine Home Assistant Skill Test ---")
    if hasattr(engine, 'ha_skill') and engine.ha_skill:
        print(f"LLMEngine has HomeAssistantSkill initialized. API available (checked by HA_Skill init or next call): {engine.ha_skill.api_available}")
        # Further tests would require a running HA instance.
    else:
        print("LLMEngine: HomeAssistantSkill not available or failed to initialize.")

    print("\nLLMEngine direct execution test complete.")
