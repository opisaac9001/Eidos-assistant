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
    from weather_skill import WeatherSkill
    from web_search_skill import WebSearchSkill # Added WebSearchSkill import
except ImportError as e:
    # Updated error message to reflect multiple possible missing skills
    print(f"LLMEngine Critical Error: Could not import one or more skill modules (HomeAssistantSkill, WeatherSkill, WebSearchSkill). Ensure skills are in the correct path: {e}")
    if 'HomeAssistantSkill' not in locals():
        HomeAssistantSkill = None
    if 'WeatherSkill' not in locals():
        WeatherSkill = None
    if 'WebSearchSkill' not in locals():
        WebSearchSkill = None

# Attempt to import KnowledgeBase from the same directory (core)
try:
    from .knowledge_base import KnowledgeBase
except ImportError as e:
    print(f"LLMEngine Critical Error: Could not import KnowledgeBase. Ensure knowledge_base.py is in the core directory: {e}")
    KnowledgeBase = None # Define as None if import fails


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

        # Initialize KnowledgeBase
        print("LLMEngine: Initializing KnowledgeBase...")
        self.knowledge_base = None # Initialize to None
        if KnowledgeBase: # Check if import was successful
            try:
                # Determine project root for default KB persistence directory
                # __file__ is core/llm_engine.py -> os.path.dirname is core/ -> os.path.dirname again is eidos_assistant/
                project_root_for_kb = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                kb_persist_directory = os.path.join(
                    project_root_for_kb,
                    "data",
                    "kb_chroma_db"
                )
                self.knowledge_base = KnowledgeBase(persist_directory=kb_persist_directory)
                # KnowledgeBase __init__ already prints success/failure details including path
                # print(f"LLMEngine: KnowledgeBase initialized. Persistence directory: {kb_persist_directory}")
            except Exception as e:
                print(f"LLMEngine Error: Failed to initialize KnowledgeBase: {e}. RAG features will be unavailable.")
                self.knowledge_base = None # Ensure it's None on error
        else:
            print("LLMEngine Error: KnowledgeBase class not available due to import failure. RAG features disabled.")

        # Initialize WeatherSkill
        print("LLMEngine: Initializing WeatherSkill...")
        self.weather_skill = None # Initialize to None
        if WeatherSkill: # Check if import was successful
            try:
                self.weather_skill = WeatherSkill()
                # WeatherSkill __init__ already prints API key status
                if not self.weather_skill.api_key or self.weather_skill.api_key == "YOUR_OPENWEATHERMAP_API_KEY_HERE":
                    print("LLMEngine Warning: WeatherSkill initialized, but API key not configured or is placeholder. Weather features likely disabled.")
                else:
                    print("LLMEngine: WeatherSkill initialized with API key.")
            except Exception as e:
                print(f"LLMEngine Error: Failed to initialize WeatherSkill: {e}. Weather features will be unavailable.")
                self.weather_skill = None # Ensure it's None on error
        else:
            print("LLMEngine Error: WeatherSkill class not available due to import failure. Weather features disabled.")

        # Initialize WebSearchSkill
        print("LLMEngine: Initializing WebSearchSkill...")
        self.web_search_skill = None
        if WebSearchSkill: # Check if import was successful
            try:
                self.web_search_skill = WebSearchSkill()
                # WebSearchSkill __init__ prints its own status
                print("LLMEngine: WebSearchSkill initialized.")
            except Exception as e:
                print(f"LLMEngine Error: Failed to initialize WebSearchSkill: {e}. Web search features will be unavailable.")
                self.web_search_skill = None
        else:
            print("LLMEngine Error: WebSearchSkill class not available due to import failure. Web search features disabled.")

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

        # Knowledge Base Instruction
        prompt_parts.append("You have access to a knowledge base. When context from this knowledge base is provided with a question, please use it to formulate your answer.")

        # Memory-based parts
        user_name = self.recall("user_profile", "name")
        if user_name:
            prompt_parts.append(f"You are speaking with {user_name}.")

        user_theme_preference = self.recall("user_preferences", "theme")
        if user_theme_preference and user_name: # Only add if user_name is known
            prompt_parts.append(f"{user_name} prefers a {user_theme_preference} theme.")
        elif user_theme_preference: # If theme known but not user name
             prompt_parts.append(f"The user prefers a {user_theme_preference} theme.")

        # Home Assistant Tool Instructions
        prompt_parts.append("\n\n--- Home Assistant Control ---")
        prompt_parts.append("If the user's request is about controlling a smart home device or checking its status, you MUST respond ONLY with a JSON object in the following format. Do not include any other text, explanations, or conversational filler before or after the JSON object.")
        prompt_parts.append("\nTo call a service (e.g., turn on/off, toggle, set brightness):")
        prompt_parts.append("{")
        prompt_parts.append("  \"tool_name\": \"home_assistant\",")
        prompt_parts.append("  \"action\": \"call_service\",")
        prompt_parts.append("  \"domain\": \"<domain_of_entity_e.g., light, switch, climate>\",")
        prompt_parts.append("  \"service\": \"<service_to_call_e.g., turn_on, turn_off, toggle, set_temperature>\",")
        prompt_parts.append("  \"entity_id\": \"<full_entity_id_e.g., light.living_room_lamp>\",")
        prompt_parts.append("  \"service_data\": { /* Optional: additional data for the service, e.g., {\"brightness_pct\": 80} or {\"temperature\": 22} */ }")
        prompt_parts.append("}")
        prompt_parts.append("\nTo get the state of a device:")
        prompt_parts.append("{")
        prompt_parts.append("  \"tool_name\": \"home_assistant\",")
        prompt_parts.append("  \"action\": \"get_state\",")
        prompt_parts.append("  \"entity_id\": \"<full_entity_id_e.g., sensor.bedroom_temperature>\" ")
        prompt_parts.append("}")
        prompt_parts.append("\nTo list all available entities:")
        prompt_parts.append("{")
        prompt_parts.append("  \"tool_name\": \"home_assistant\",")
        prompt_parts.append("  \"action\": \"list_entities\"")
        prompt_parts.append("}")
        prompt_parts.append("\nExamples of when to use this JSON format:")
        prompt_parts.append("User: \"Turn on the kitchen light.\"")
        prompt_parts.append("You: {\"tool_name\": \"home_assistant\", \"action\": \"call_service\", \"domain\": \"light\", \"service\": \"turn_on\", \"entity_id\": \"light.kitchen_light\", \"service_data\": {}}")
        prompt_parts.append("User: \"Is the front door locked?\"")
        prompt_parts.append("You: {\"tool_name\": \"home_assistant\", \"action\": \"get_state\", \"entity_id\": \"lock.front_door\"}")
        prompt_parts.append("User: \"Set the living room thermostat to 20 degrees.\"")
        prompt_parts.append("You: {\"tool_name\": \"home_assistant\", \"action\": \"call_service\", \"domain\": \"climate\", \"service\": \"set_temperature\", \"entity_id\": \"climate.living_room\", \"service_data\": {\"temperature\": 20}}")
        prompt_parts.append("User: \"Toggle the office fan.\"")
        prompt_parts.append("You: {\"tool_name\": \"home_assistant\", \"action\": \"call_service\", \"domain\": \"switch\", \"service\": \"toggle\", \"entity_id\": \"switch.office_fan\", \"service_data\": {}}")
        prompt_parts.append("User: \"What devices can you see in Home Assistant?\" or \"List all my entities.\"")
        prompt_parts.append("You: {\"tool_name\": \"home_assistant\", \"action\": \"list_entities\"}")
        prompt_parts.append("\nIf the request is NOT about Home Assistant, or if you are unsure of the entity_id, domain, or service, respond normally as a helpful assistant without using the JSON format.")
        prompt_parts.append("--- End Home Assistant Control ---")

        # Weather Tool Instructions
        prompt_parts.append("\n\n--- Weather Information ---")
        prompt_parts.append("If the user asks about the current weather, you MUST respond ONLY with a JSON object in the following format:")
        prompt_parts.append("{")
        prompt_parts.append("  \"tool_name\": \"weather\",")
        prompt_parts.append("  \"action\": \"get_current_weather\",")
        prompt_parts.append("  \"city\": \"<city_name_e.g., London, Paris, New York>\",")
        prompt_parts.append("  \"units\": \"<metric_or_imperial (optional, defaults to metric)>\"") # Corrected trailing quote
        prompt_parts.append("}")
        prompt_parts.append("\nExample: User: \"What's the weather in Berlin?\"") # Corrected quote placement
        prompt_parts.append("You: {\"tool_name\": \"weather\", \"action\": \"get_current_weather\", \"city\": \"Berlin\"}")
        prompt_parts.append("User: \"How hot is it in Phoenix in Fahrenheit?\"")
        prompt_parts.append("You: {\"tool_name\": \"weather\", \"action\": \"get_current_weather\", \"city\": \"Phoenix\", \"units\": \"imperial\"}")
        prompt_parts.append("If the request is NOT about current weather, respond normally.")
        prompt_parts.append("--- End Weather Information ---")

        # Web Search Tool Instructions
        prompt_parts.append("\n\n--- Web Search ---")
        prompt_parts.append("If you need to find current information or information not in your training data or local knowledge base, you can request a web search. Respond ONLY with a JSON object in the following format:")
        prompt_parts.append("{")
        prompt_parts.append("  \"tool_name\": \"web_search\",")
        prompt_parts.append("  \"action\": \"search\",")
        prompt_parts.append("  \"query\": \"<your_search_query_string>\"") # Corrected trailing quote
        prompt_parts.append("}")
        prompt_parts.append("\nExample: User: \"What is the latest news about Project Gemini?\"")
        prompt_parts.append("You: {\"tool_name\": \"web_search\", \"action\": \"search\", \"query\": \"latest news Project Gemini\"}")
        prompt_parts.append("After the search results are provided, you will be asked to synthesize an answer based on them.")
        prompt_parts.append("--- End Web Search ---")

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

        final_user_content = user_input # Default to original user input
        # Augment with Knowledge Base context if available
        if self.knowledge_base:
            # Query the knowledge base, n_results can be tuned
            retrieved_docs = self.knowledge_base.query(user_input, n_results=3)
            if retrieved_docs: # If documents were found
                formatted_context = "\n\n---\n\n".join(retrieved_docs) # Join chunks with a clear separator

                # Construct the augmented prompt for the LLM
                context_header = "Based on the following information from my knowledge base, please answer the user's question.\n\nRelevant Information:\n"
                final_user_content = f"{context_header}{formatted_context}\n\n---\nUser's original question: {user_input}"

                # Optional: Print a debug message
                print(f"LLMEngine DEBUG: Using augmented prompt with KB context for query: '{user_input[:50]}...'")
                # print(f"LLMEngine DEBUG: Context provided: {formatted_context[:300]}...") # For more detailed debugging

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": final_user_content} # Use the potentially augmented input
        ]

        try:
            completion = self.client.chat.completions.create(
                model="local-model", # Model name is often ignored by local servers but required by API
                messages=messages,
                temperature=0.7,
            )
            response_content = completion.choices[0].message.content
            llm_response_content = completion.choices[0].message.content.strip()
        except APIConnectionError as e:
            error_msg = f"Error connecting to LLM API at {self.api_base_url}: {e}"
            print(error_msg)
            llm_response_content = f"{assistant_name} (error): {error_msg}"
        except APIStatusError as e:
            error_msg = f"LLM API returned an error: Status {e.status_code}, Response: {e.response}"
            print(error_msg)
            llm_response_content = f"{assistant_name} (error): {error_msg}"
        except Exception as e:
            error_msg = f"An unexpected error occurred during LLM call: {e}"
            print(error_msg)
            llm_response_content = f"{assistant_name} (error): {error_msg}"

        # NEW LOGIC STARTS HERE, processing llm_response_content
        if llm_response_content:
            try:
                cleaned_response_content = llm_response_content
                if llm_response_content.startswith("```json"):
                    cleaned_response_content = llm_response_content.split("```json", 1)[1].strip()
                    if cleaned_response_content.endswith("```"):
                        cleaned_response_content = cleaned_response_content[:-3].strip()

                data = json.loads(cleaned_response_content)

                if isinstance(data, dict) and data.get("tool_name") == "home_assistant":
                    print(f"LLMEngine: Detected Home Assistant tool call: {data}")
                    action = data.get("action")
                    entity_id = data.get("entity_id")

                    if not self.ha_skill:
                        return "Pathos: I want to use a Home Assistant skill, but it's not available or configured."

                    if action == "call_service":
                        domain = data.get("domain")
                        service = data.get("service")
                        service_data_payload = data.get("service_data", {})

                        final_service_data = {"entity_id": entity_id}
                        if isinstance(service_data_payload, dict):
                            final_service_data.update(service_data_payload)

                        if domain and service and entity_id: # entity_id already included in final_service_data
                            success = self.ha_skill.call_service(domain, service, final_service_data)
                            if success:
                                friendly_service_name = service.replace("_", " ")
                                return f"Pathos: Okay, I've actioned '{friendly_service_name}' for '{entity_id}'."
                            else:
                                return f"Pathos: Sorry, I tried but failed to perform '{service}' on '{entity_id}' via Home Assistant."
                        else:
                            return "Pathos: Home Assistant tool call was missing domain, service, or entity_id."

                    elif action == "get_state":
                        if entity_id:
                            state_info = self.ha_skill.get_entity_state(entity_id)
                            if state_info:
                                current_state = state_info.get('state', 'unknown')
                                return f"Pathos: According to Home Assistant, '{entity_id}' is currently '{current_state}'."
                            else:
                                return f"Pathos: Sorry, I couldn't get the current state for '{entity_id}' from Home Assistant."
                        else:
                            return "Pathos: Home Assistant 'get_state' tool call was missing entity_id."
                    elif action == "list_entities":
                        if not self.ha_skill: # Should have been caught earlier, but double check
                            return "Pathos: I want to list Home Assistant entities, but the skill is not available."

                        entities = self.ha_skill.list_entities() # This now returns list[dict] or None

                        if entities is not None:
                            if entities: # List is not None and not empty
                                entity_list_str = []
                                for entity_item in entities: # Renamed to avoid conflict
                                    # Using .get for safety, though the skill should provide these
                                    entity_id_str = entity_item.get('entity_id', 'Unknown ID')
                                    friendly_name_str = entity_item.get('friendly_name', entity_id_str) # Default to ID if no friendly name
                                    if friendly_name_str != entity_id_str:
                                        entity_list_str.append(f"{entity_id_str} ({friendly_name_str})")
                                    else:
                                        entity_list_str.append(entity_id_str)

                                # Simple truncation for very long lists
                                max_entities_to_list = 20 # Max entities to list directly
                                if len(entity_list_str) > max_entities_to_list:
                                    listed_entities = ", ".join(entity_list_str[:max_entities_to_list]) + f", and {len(entity_list_str) - max_entities_to_list} more."
                                else:
                                    listed_entities = ", ".join(entity_list_str)

                                return f"Pathos: I found the following entities in Home Assistant: {listed_entities}. You can ask me for the state of any of these or ask me to control them."
                            else: # List is empty
                                return "Pathos: I didn't find any entities in Home Assistant."
                        else: # entities is None, meaning an error occurred in the skill
                            return "Pathos: Sorry, I encountered an error trying to list entities from Home Assistant."
                    else:
                        return f"Pathos: Unknown Home Assistant action: '{action}'."

                elif isinstance(data, dict) and data.get("tool_name") == "weather":
                    print(f"LLMEngine: Detected Weather tool call: {data}")
                    action = data.get("action")

                    if not self.weather_skill:
                        return "Pathos: I want to get weather information, but the WeatherSkill is not available or configured."

                    if action == "get_current_weather":
                        city = data.get("city")
                        units = data.get("units", "metric") # Default to metric if not specified
                        if not city:
                            return "Pathos: Weather 'get_current_weather' tool call was missing the city."

                        weather_info = self.weather_skill.get_current_weather(city, units)
                        if weather_info:
                            temp_unit = "°C" if weather_info['units'] == "metric" else "°F"
                            wind_speed_unit = "m/s" if weather_info['units'] == "metric" else "mph"
                            response_str = (
                                f"Pathos: The current weather in {weather_info['city']}, {weather_info['country']} is: "
                                f"{weather_info['temperature']}{temp_unit} (feels like {weather_info['feels_like']}{temp_unit}). "
                                f"Description: {weather_info['description']}. "
                                f"Humidity: {weather_info['humidity']}%. "
                                f"Wind speed: {weather_info['wind_speed']} {wind_speed_unit}."
                            )
                            return response_str
                        else:
                            # The skill's get_current_weather method already prints detailed errors
                            return f"Pathos: Sorry, I couldn't retrieve the weather information for '{city}'."
                    else:
                        return f"Pathos: Unknown Weather action: '{action}'."

                elif isinstance(data, dict) and data.get("tool_name") == "web_search":
                    print(f"LLMEngine: Detected Web Search tool call: {data}")
                    action = data.get("action")
                    assistant_name_prefix = f"{self.get_persona_attribute('identity.name') or 'Pathos'}: " # Get assistant name for responses

                    if not self.web_search_skill:
                        return f"{assistant_name_prefix}I want to search the web, but the WebSearchSkill is not available."

                    if action == "search":
                        search_query = data.get("query")
                        if not search_query:
                            return f"{assistant_name_prefix}Web 'search' tool call was missing the search query."

                        print(f"LLMEngine: Performing web search for: '{search_query}'...")
                        # Using num_results=3 as a sensible default for LLM context
                        search_results = self.web_search_skill.search(search_query, num_results=3)

                        if search_results is None: # Error occurred during search
                             return f"{assistant_name_prefix}I encountered an error while trying to search the web for '{search_query}'."
                        if not search_results: # Empty list, no results found
                            return f"{assistant_name_prefix}I searched the web for '{search_query}', but couldn't find any relevant results."

                        # Format results for synthesis
                        formatted_results_for_synthesis = "\n\n".join([
                            f"Title: {res['title']}\nSnippet: {res['snippet']}\nURL: {res['url']}"
                            for res in search_results
                        ])

                        # Prepare prompt for LLM to synthesize an answer from search results
                        # user_input here is the original user query that triggered the web_search tool call.
                        synthesis_prompt_content = (
                            f"User's original question: '{user_input}'\n\n"
                            f"I have performed a web search and found the following information:\n--- Search Results ---\n{formatted_results_for_synthesis}\n--- End Search Results ---\n\n"
                            "Please synthesize a comprehensive answer to the user's original question based ONLY on these search results. "
                            "Do not use your general knowledge unless the search results are insufficient or empty. "
                            "If the results are irrelevant or don't help answer the question, say so."
                        )

                        print(f"LLMEngine: Synthesizing answer from web search results for original query: '{user_input[:50]}...'")

                        # Make a second LLM call for synthesis
                        synthesis_messages = [
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": synthesis_prompt_content}
                        ]
                        try:
                            synthesis_completion = self.client.chat.completions.create(
                                model="local-model", messages=synthesis_messages, temperature=0.7
                            )
                            synthesized_answer = synthesis_completion.choices[0].message.content.strip()
                            return f"{assistant_name_prefix}{synthesized_answer}"
                        except Exception as e:
                            print(f"LLMEngine: Error during synthesis LLM call: {e}")
                            return f"{assistant_name_prefix}I found some information, but had trouble processing it to form an answer."
                    else:
                        return f"{assistant_name_prefix}Unknown Web Search action: '{action}'."
                else:
                    # Not a HA, Weather, or Web Search tool call, or not properly formatted JSON for it. Return original LLM text.
                    return llm_response_content

            except json.JSONDecodeError:
                # Not JSON, or malformed JSON not intended as a tool call. Return original LLM text.
                return llm_response_content
            except Exception as e:
                print(f"LLMEngine: Error processing potential tool call: {e}")
                return f"Pathos: I encountered an issue trying to process that: {e}"
        else:
            return "Pathos: I didn't receive a response from the language model."


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

    # Test 4: Simulate LLM responding with "list_entities"
    simulated_llm_json_output_list_entities = '''
    {
      "tool_name": "home_assistant",
      "action": "list_entities"
    }
    '''
    print(f"\nIf LLM produced: {simulated_llm_json_output_list_entities.strip()}")
    # Conceptual: In a real test via get_response, this would trigger ha_skill.list_entities()
    # and Pathos would respond with the list or an error/empty message.
    # For this __main__ block, we're just showing the simulated LLM output.
    # A direct call to engine.get_response(simulated_llm_json_output_list_entities) could be made
    # if the ha_skill is mocked or a live HA instance is expected for testing.
    # For now, this remains a conceptual print to show the LLM's part.
    if engine.ha_skill:
        print("Expected Pathos response (if HA skill is connected and returns entities): A list of entities.")
        print("Expected Pathos response (if HA skill is connected and returns no entities): 'Pathos: I didn't find any entities in Home Assistant.'")
        print("Expected Pathos response (if HA skill errors): 'Pathos: Sorry, I encountered an error trying to list entities from Home Assistant.'")
    else:
        print("Expected Pathos response (if HA skill is not available): 'Pathos: I want to list Home Assistant entities, but the skill is not available.'")

    print("\n--- LLMEngine KnowledgeBase Test ---")
    if hasattr(engine, 'knowledge_base') and engine.knowledge_base:
        print(f"LLMEngine has KnowledgeBase initialized.")
        if engine.knowledge_base.client:
            print(f"KnowledgeBase client type: {type(engine.knowledge_base.client)}")
            if engine.knowledge_base.persist_directory:
                 print(f"KnowledgeBase persistence directory: {engine.knowledge_base.resolved_persist_directory}")
            if engine.knowledge_base.collection:
                 print(f"KnowledgeBase collection name: {engine.knowledge_base.collection.name}")
            else:
                 print(f"KnowledgeBase collection: N/A (should be initialized)")
    else:
        print("LLMEngine: KnowledgeBase not available or failed to initialize.")

    print("\n--- LLMEngine Weather Skill Test ---")
    if hasattr(engine, 'weather_skill') and engine.weather_skill:
        print("LLMEngine has WeatherSkill initialized.")
        if not engine.weather_skill.api_key or engine.weather_skill.api_key == "YOUR_OPENWEATHERMAP_API_KEY_HERE":
            print("WeatherSkill API key not configured or is placeholder. Live tests will likely fail or use mocked data if skill handles it.")
        else:
            print(f"WeatherSkill API key loaded: {engine.weather_skill.api_key[:4]}...{engine.weather_skill.api_key[-4:]}")
    else:
        print("LLMEngine: WeatherSkill not available or failed to initialize.")

    simulated_llm_weather_json = '''
    {
      "tool_name": "weather",
      "action": "get_current_weather",
      "city": "London",
      "units": "metric"
    }
    '''
    print(f"\nIf LLM produced: {simulated_llm_weather_json.strip()}")
    # Conceptual test description:
    if hasattr(engine, 'weather_skill') and engine.weather_skill:
        if engine.weather_skill.api_key and engine.weather_skill.api_key != "YOUR_OPENWEATHERMAP_API_KEY_HERE":
            print("Expected Pathos response (if API key valid & city found): Formatted weather string for London.")
        else: # API key missing or placeholder
             print("Expected Pathos response: Error message about API key or failure to retrieve weather (skill should handle this).")
    else: # Skill not available
        print("Expected Pathos response: Error message about WeatherSkill not being available.")

    print("\n--- LLMEngine WebSearch Skill Test (Conceptual) ---")
    if hasattr(engine, 'web_search_skill') and engine.web_search_skill:
        print("LLMEngine has WebSearchSkill initialized.")
    else:
        print("LLMEngine: WebSearchSkill not available or failed to initialize.")

    simulated_llm_web_search_json = '''
    {
      "tool_name": "web_search",
      "action": "search",
      "query": "latest AI advancements"
    }
    '''
    print(f"\nIf LLM produced: {simulated_llm_web_search_json.strip()}")
    if hasattr(engine, 'web_search_skill') and engine.web_search_skill:
        print("Expected Pathos behavior: Perform web search, then make a second LLM call to synthesize results, then return synthesized answer.")
        print("(Actual search and synthesis would require live calls and a running LLM for the second step).")
    else:
        print("Expected Pathos response: Error message about WebSearchSkill not being available.")


    print("\nLLMEngine direct execution test complete.")
