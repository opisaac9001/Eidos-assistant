import yaml
import os # Ensure os is imported for getenv and path operations
from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError
from memory import MemoryManager

import json # Added for parsing LLM responses for tool calls
# import os # os is already imported below
from dotenv import load_dotenv
import sys # Added for sys.path manipulation

# Attempt to load .env, but proceed gracefully if it fails or python-dotenv has issues.
# The os.getenv calls in __init__ will then rely on system-set env vars or use defaults.
try:
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    loaded_env = load_dotenv(dotenv_path=dotenv_path)
    if loaded_env:
        print(f"DEBUG: llm_engine.py - Successfully loaded .env file from {dotenv_path}")
    else:
        print(f"DEBUG: llm_engine.py - .env file not found at {dotenv_path} or is empty. Relying on system env vars or defaults.")
except Exception as e:
    print(f"DEBUG: llm_engine.py - Error loading .env file: {e}. Proceeding with defaults or system-set environment variables.")

# Attempt to import Llama from llama_cpp
try:
    from llama_cpp import Llama
except ImportError:
    print("LLMEngine Warning: llama_cpp library not found. 'local_llama_cpp' engine will be unavailable.")
    Llama = None # Define Llama as None if import fails

# Dynamically add skills directory to sys.path for importing HomeAssistantSkill
# This ensures that even if LLMEngine is imported from elsewhere, it can find its skills.
try:
    current_script_dir = os.path.dirname(os.path.abspath(__file__)) # core directory
    project_root_dir = os.path.dirname(current_script_dir) # eidos_assistant directory
    skills_dir_path = os.path.join(project_root_dir, 'skills')
    if skills_dir_path not in sys.path:
        sys.path.insert(0, skills_dir_path) # Insert at beginning for priority
    from home_assistant_skill import HomeAssistantSkill
    from news_skill import NewsSkill
    from web_search_skill import WebSearchSkill
except ImportError as e:
    print(f"LLMEngine Critical Error: Could not import one or more skill modules. Ensure 'skills' directory and its contents are correct: {e}")
    if 'HomeAssistantSkill' not in locals(): HomeAssistantSkill = None
    if 'NewsSkill' not in locals(): NewsSkill = None
    if 'WebSearchSkill' not in locals(): WebSearchSkill = None

class LLMEngine:
    def __init__(self, persona_config_path="persona_config.yaml"):
        # Construct the absolute path to the persona config file
        base_dir = os.path.dirname(os.path.abspath(__file__)) # core directory
        self.persona_config_path = os.path.join(base_dir, persona_config_path)
        self.persona = None
        self.system_prompt = "You are a helpful AI assistant." # Default prompt

        # Load LLM engine type and specific configurations
        self.llm_engine_type = os.getenv("LLM_ENGINE_TYPE", "openai").lower()

        self.client = None      # For OpenAI client
        self.local_llm = None   # For Llama object

        if self.llm_engine_type == "openai":
            self.api_base_url = os.getenv("LLM_API_BASE_URL", "http://localhost:11434/v1")
            self.api_key = os.getenv("LLM_API_KEY", "NotNeededForOllama")
            self.temperature = float(os.getenv("OPENAI_TEMPERATURE", 0.7))
            self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", 150))
            try:
                self.client = OpenAI(base_url=self.api_base_url, api_key=self.api_key)
                print(f"LLMEngine initialized with OpenAI client. API base URL: {self.api_base_url}")
            except Exception as e:
                print(f"Error initializing OpenAI client: {e}")
        elif self.llm_engine_type == "local_llama_cpp":
            if Llama is None:
                print("LLMEngine Error: LLM_ENGINE_TYPE is 'local_llama_cpp', but llama_cpp library failed to import. Local LLM unavailable.")
            else:
                self.local_llm_model_path = os.getenv("LOCAL_LLM_MODEL_PATH")
                self.local_llm_n_gpu_layers = int(os.getenv("LOCAL_LLM_N_GPU_LAYERS", 0))
                self.local_llm_n_ctx = int(os.getenv("LOCAL_LLM_N_CTX", 2048))
                self.local_llm_chat_format = os.getenv("LOCAL_LLM_CHAT_FORMAT", None) # Auto-detect if None
                self.temperature = float(os.getenv("LOCAL_LLM_TEMPERATURE", 0.7)) # Reuse for consistency
                self.max_tokens = int(os.getenv("LOCAL_LLM_MAX_TOKENS", 150)) # Reuse for consistency

                if not self.local_llm_model_path:
                    print("LLMEngine Error: LLM_ENGINE_TYPE is 'local_llama_cpp', but LOCAL_LLM_MODEL_PATH is not set in .env.")
                elif not os.path.exists(self.local_llm_model_path):
                    print(f"LLMEngine Error: LOCAL_LLM_MODEL_PATH '{self.local_llm_model_path}' does not exist.")
                else:
                    try:
                        print(f"LLMEngine: Initializing Llama model from {self.local_llm_model_path}...")
                        print(f"  Config: n_gpu_layers={self.local_llm_n_gpu_layers}, n_ctx={self.local_llm_n_ctx}, chat_format='{self.local_llm_chat_format or 'auto'}'")
                        self.local_llm = Llama(
                            model_path=self.local_llm_model_path,
                            n_gpu_layers=self.local_llm_n_gpu_layers,
                            n_ctx=self.local_llm_n_ctx,
                            verbose=False # Set to True for more detailed llama.cpp output
                        )
                        print("LLMEngine: Llama model initialized successfully.")
                    except Exception as e:
                        print(f"LLMEngine Error: Failed to initialize Llama model: {e}")
                        self.local_llm = None # Ensure it's None on error
        else:
            print(f"LLMEngine Warning: Unknown LLM_ENGINE_TYPE '{self.llm_engine_type}'. LLM functionality will be unavailable.")

        # Initialize MemoryManager
        self.memory_manager = MemoryManager(memory_file_path="data/memory.json")

        # Skill Management
        self.skills = {} # Dictionary to hold skill instances
        # Removed direct skill assignments like self.ha_skill, self.news_skill etc.
        # All skills are now managed via the self.skills dictionary and BaseSkill interface.
        self._initialize_and_register_skills()

        self.load_persona()
        self.system_prompt = self._construct_system_prompt() # Construct system prompt after persona, memory, and skills

    def _initialize_and_register_skills(self):
        """Initializes and registers available skills."""
        print("LLMEngine: Initializing and registering skills...")

        # HomeAssistantSkill
        if HomeAssistantSkill:
            try:
                ha_skill_instance = HomeAssistantSkill()
                if hasattr(ha_skill_instance, 'is_configured') and ha_skill_instance.is_configured():
                    self.register_skill(ha_skill_instance)
                else:
                    print("LLMEngine Warning: HomeAssistantSkill not configured (token missing or invalid). Not registered as a usable skill.")
            except Exception as e:
                print(f"LLMEngine Error: Failed to initialize or register HomeAssistantSkill: {e}")
        else:
            print("LLMEngine Info: HomeAssistantSkill class not available. Skipping registration.")

        # NewsSkill
        if NewsSkill:
            try:
                news_skill_instance = NewsSkill()
                self.register_skill(news_skill_instance) # Register using the new method
                print("LLMEngine: NewsSkill registered.")
            except Exception as e:
                print(f"LLMEngine Error: Failed to initialize or register NewsSkill: {e}")
        else:
            print("LLMEngine Info: NewsSkill class not available. Skipping registration.")

        if WebSearchSkill: # Check if WebSearchSkill was imported successfully
            try:
                web_search_skill_instance = WebSearchSkill()
                self.register_skill(web_search_skill_instance)
                print("LLMEngine: WebSearchSkill registered.")
            except Exception as e:
                print(f"LLMEngine Error: Failed to initialize or register WebSearchSkill: {e}")
        else:
            print("LLMEngine Info: WebSearchSkill class not available. Skipping registration.")

        # TODO: Add other skills here in the future

    def register_skill(self, skill_instance: Any): # Using Any for now, should be BaseSkill
        """Registers a skill instance if it has a valid tool signature."""
        if hasattr(skill_instance, 'get_tool_signature'):
            try:
                signature = skill_instance.get_tool_signature()
                tool_name = signature.get("tool_name")
                if tool_name:
                    self.skills[tool_name] = skill_instance
                    print(f"LLMEngine: Skill '{tool_name}' registered successfully.")
                else:
                    print(f"LLMEngine Warning: Skill object {type(skill_instance).__name__} has no 'tool_name' in its signature.")
            except Exception as e:
                print(f"LLMEngine Error: Could not get tool signature for skill {type(skill_instance).__name__}: {e}")
        else:
            print(f"LLMEngine Warning: Skill object {type(skill_instance).__name__} does not have 'get_tool_signature' method.")


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

        # Add registered skill/tool signatures to the system prompt
        if self.skills:
            prompt_parts.append("\n\n--- Available Tools ---")
            prompt_parts.append("If the user's request matches one of the following tools, you MUST respond ONLY with a JSON object matching the tool's 'parameters' schema. Do not include any other text, explanations, or conversational filler before or after the JSON object.")
            prompt_parts.append("Do NOT try to use a tool if the user is just asking about its functionality or how to use it.")

            for tool_name, skill_instance in self.skills.items():
                # All skills, including home_assistant_control, are now described by their signature.
                signature = skill_instance.get_tool_signature()
                prompt_parts.append(f"\nTool: {tool_name}")
                prompt_parts.append(f"  Description: {signature['description']}")
                prompt_parts.append("  Parameters (as a JSON object): {")
                for param in signature.get("parameters", []):
                    param_type = param.get('type', 'string')
                    is_required = param.get('required', False)
                    description = param.get('description', '')
                    req_str = "REQUIRED" if is_required else "OPTIONAL"
                    prompt_parts.append(f"    \"{param['name']}\": \"<{param_type}> ({req_str}) {description}\",")
                # Remove trailing comma from last parameter if any
                if signature.get("parameters"):
                    prompt_parts[-1] = prompt_parts[-1].rstrip(',')
                prompt_parts.append("  }")
                prompt_parts.append(f"  Example JSON for {tool_name}: {{ \"tool_name\": \"{tool_name}\", \"parameters\": {{...}} }}") # Generic example
            prompt_parts.append("--- End Available Tools ---")


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
        Generates a response to user input using the configured LLM engine.
        """
        assistant_name = self.get_persona_attribute('identity.name') or "Pathos" # Changed default
        llm_response_content = ""

        # Construct messages list (common for both engines)
        # TODO: Implement actual conversation history management
        messages = [{"role": "system", "content": self.system_prompt}]
        if conversation_history: # Assuming conversation_history is a list of {"role": ..., "content": ...}
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_input})

        if self.llm_engine_type == "openai":
            if not self.client:
                return f"{assistant_name} (error): OpenAI client not initialized. Cannot connect to LLM."
            try:
                completion = self.client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL_NAME", "local-model"), # Allow model override via env
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    # stream=False # Add stream=True for streaming if desired later
                )
                llm_response_content = completion.choices[0].message.content.strip()
            except APIConnectionError as e:
                error_msg = f"Error connecting to OpenAI API at {self.api_base_url}: {e}"
                print(error_msg)
                llm_response_content = f"{assistant_name} (error): {error_msg}"
            except APIStatusError as e:
                error_msg = f"OpenAI API returned an error: Status {e.status_code}, Response: {e.response}"
                print(error_msg)
                llm_response_content = f"{assistant_name} (error): {error_msg}"
            except Exception as e:
                error_msg = f"An unexpected error occurred during OpenAI LLM call: {e}"
                print(error_msg)
                llm_response_content = f"{assistant_name} (error): {error_msg}"

        elif self.llm_engine_type == "local_llama_cpp":
            if not self.local_llm:
                return f"{assistant_name} (error): Llama CPP model not initialized. Cannot generate response."
            try:
                # Note: llama-cpp-python's chat_format handling is important.
                # If self.local_llm_chat_format is None, it tries to auto-detect from model.
                # If system prompt is part of the model's trained format (e.g. some instruct models),
                # it might be better to not pass it explicitly here if the model adds it.
                # For now, we pass it, assuming most general chat models expect it.
                completion = self.local_llm.create_chat_completion(
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    stop=None,  # Add stop words if needed
                    stream=False, # Add stream=True for streaming if desired later
                    # Pass chat_format only if explicitly set, otherwise let llama_cpp try to determine it
                    **( {"chat_format": self.local_llm_chat_format} if self.local_llm_chat_format else {} )
                )
                if completion and completion['choices'] and completion['choices'][0]['message'] and 'content' in completion['choices'][0]['message']:
                    llm_response_content = completion['choices'][0]['message']['content'].strip()
                else:
                    llm_response_content = f"{assistant_name} (error): Received an unexpected response structure from Llama CPP."
                    print(f"LLMEngine (Llama CPP) unexpected response: {completion}")

            except Exception as e:
                error_msg = f"An unexpected error occurred during Llama CPP call: {e}"
                import traceback
                traceback.print_exc()
                llm_response_content = f"{assistant_name} (error): {error_msg}"
        else:
            return f"{assistant_name} (error): LLM_ENGINE_TYPE '{self.llm_engine_type}' is not recognized or engine failed to initialize."

        # Tool call processing (remains largely the same, uses llm_response_content)
        if llm_response_content:
            try:
                cleaned_response_content = llm_response_content
                if llm_response_content.startswith("```json"):
                    cleaned_response_content = llm_response_content.split("```json", 1)[1].strip()
                    if cleaned_response_content.endswith("```"):
                        cleaned_response_content = cleaned_response_content[:-3].strip()

                data = json.loads(cleaned_response_content)

                if isinstance(data, dict) and data.get("tool_name") in self.skills:
                    tool_name = data["tool_name"]
                    skill_instance = self.skills[tool_name]
                    skill_args = data.get("parameters", {})

                    print(f"LLMEngine: Detected call for skill '{tool_name}' with args: {skill_args}")
                    try:
                        # Pass the 'action' from skill_args if present (mainly for home_assistant_control)
                        skill_action = skill_args.get("action") if tool_name == "home_assistant_control" else None
                        skill_result_data = skill_instance.execute(action=skill_action, args=skill_args)

                        if isinstance(skill_result_data, dict) and skill_result_data.get("synthesis_needed"):
                            print(f"LLMEngine: Skill '{tool_name}' requires synthesis. Preparing follow-up LLM call.")
                            original_user_query_for_synthesis = skill_result_data.get("original_query_for_synthesis", user_input)
                            skill_result_content = skill_result_data.get("synthesis_prompt_content", "No content from tool for synthesis.")

                            synthesis_prompt = (
                                f"User's original query: \"{original_user_query_for_synthesis}\"\n\n"
                                f"I have performed an action using the '{tool_name}' tool and found the following information:\n"
                                f"--- Tool Results ---\n{skill_result_content}\n--- End Tool Results ---\n\n"
                                f"Based *only* on these tool results and the original query, please provide a concise answer to the user's original query. "
                                f"Do not use any prior knowledge. If the results do not provide enough information to answer, say so."
                            )

                            print(f"LLMEngine: Synthesis prompt for LLM:\n{synthesis_prompt[:500]}...")

                            synthesis_messages = [
                                {"role": "system", "content": self.system_prompt},
                                {"role": "user", "content": synthesis_prompt}
                            ]

                            if self.llm_engine_type == "openai" and self.client:
                                synth_completion = self.client.chat.completions.create(
                                    model=os.getenv("OPENAI_MODEL_NAME", "local-model"),
                                    messages=synthesis_messages,
                                    temperature=self.temperature,
                                    max_tokens=self.max_tokens
                                )
                                return synth_completion.choices[0].message.content.strip()
                            elif self.llm_engine_type == "local_llama_cpp" and self.local_llm:
                                synth_completion = self.local_llm.create_chat_completion(
                                    messages=synthesis_messages,
                                    temperature=self.temperature,
                                    max_tokens=self.max_tokens,
                                     **( {"chat_format": self.local_llm_chat_format} if self.local_llm_chat_format else {} )
                                )
                                return synth_completion['choices'][0]['message']['content'].strip()
                            else:
                                return "Pathos: LLM for synthesis not available."
                        else:
                            return self._handle_skill_result(tool_name, skill_result_data)

                    except Exception as e:
                        print(f"LLMEngine: Error executing skill '{tool_name}': {e}")
                        import traceback
                        traceback.print_exc()
                        return f"Pathos: I encountered an error trying to use the {tool_name} tool: {e}"
                else: # Not a recognized JSON tool call.
                    return llm_response_content

            except json.JSONDecodeError:
                # Not JSON, return original LLM text.
                return llm_response_content
            except Exception as e:
                print(f"LLMEngine: Error processing potential tool call: {e}")
                return f"Pathos: I encountered an issue trying to process that: {e}"
        else:
            return "Pathos: I didn't receive a response from the language model."

    def _handle_skill_result(self, tool_name: str, result: Dict[str, Any]) -> str:
        """Handles the result from a skill execution for user presentation."""
        if isinstance(result, dict) and 'error' in result:
            return f"Pathos: Error using {tool_name}: {result['error']}"

        # Simple conversion to string for now. Can be customized per tool later.
        # For NewsSkill, this will make the LLM summarize the dictionary of headlines.
        # Or, the LLM might be instructed by the tool's description to directly use the info.
        # For now, just returning a summary of the result.
        # If the LLM is good, it might summarize this dict appropriately.
        # If not, the system prompt for tools needs to be clearer on how the LLM should use the tool's JSON output.
        # Current system prompt for tools says "If the user's request matches... respond ONLY with a JSON object..."
        # This means the LLM *itself* is forming the JSON to call the tool.
        # The output of tool.execute() is then *given back to the LLM* as the next user message (or part of it).
        # So, this function's output here is effectively what the LLM sees as the "tool's response".
        # It should be a string that the LLM can understand and use to form its final answer to the user.

        # Thus, converting the dict to a JSON string is appropriate for the LLM to consume.
        if isinstance(result, dict):
            return f"Tool {tool_name} executed and returned: {json.dumps(result)}"
        else:
            return f"Tool {tool_name} executed and returned an unexpected format: {result}"


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

    print("\n--- LLMEngine Home Assistant Tool Call Processing Test (Conceptual) ---")
    # These tests assume the LLM would respond with the JSON string.
    # We are testing LLMEngine's ability to parse this and call ha_skill.
    # Actual HA interaction depends on HA server and token.

    print("\nTo test natural language HA commands (e.g., 'turn on light.dummy_light'):")
    print("1. Ensure your LLM server is running and configured in .env.")
    print("2. Ensure your Home Assistant server is running and configured in .env with a valid token.")
    print("3. The LLM must be prompted (via system prompt) to return JSON for HA commands.")
    print("4. Then, in main.py, type 'turn on light.dummy_light'.")

    # Example of what the LLM *should* output for "turn on light.test":
    simulated_llm_json_output_turn_on = '''
    {
      "tool_name": "home_assistant",
      "action": "call_service",
      "domain": "light",
      "service": "turn_on",
      "entity_id": "light.test_light_from_llm",
      "service_data": {}
    }
    '''
    print(f"\nIf LLM produced: {simulated_llm_json_output_turn_on.strip()}")
    # To directly test the parsing logic, we would need to refactor _process_llm_tool_call
    # For now, this part of the test in __main__ remains conceptual for full get_response.

    # Test 2: Simulate LLM responding with "get_state"
    simulated_llm_json_output_get_state = '''
    {
      "tool_name": "home_assistant",
      "action": "get_state",
      "entity_id": "sensor.test_sensor_from_llm"
    }
    '''
    print(f"\nIf LLM produced: {simulated_llm_json_output_get_state.strip()}")

    # Test 3: Simulate LLM responding with malformed JSON for HA
    # (This would be caught by the JSONDecodeError in get_response and treated as text)
    simulated_malformed_json = '{\"tool_name\": \"home_assistant\", \"action\": \"call_service\", \"entity_id\": light.test_malformed'
    print(f"\nIf LLM produced malformed JSON like: {simulated_malformed_json}")
    print("(LLMEngine should treat this as a normal text response if JSON parsing fails.)")

    print("\nLLMEngine direct execution test complete.")
