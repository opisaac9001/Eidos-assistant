import yaml
import os
from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError
from memory import MemoryManager
import json
import sys
from typing import Dict, List, Any, Union

# Attempt to load .env
try:
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(dotenv_path=dotenv_path)
    print(f"DEBUG: llm_engine.py - dotenv_path: {dotenv_path}, Loaded .env successfully.")
except Exception as e:
    print(f"DEBUG: llm_engine.py - Error loading .env file: {e}.")

# Add skills directory to sys.path
try:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.dirname(current_script_dir)
    skills_dir_path = os.path.join(project_root_dir, 'skills')
    if skills_dir_path not in sys.path:
        sys.path.insert(0, skills_dir_path)

    from home_assistant_skill import HomeAssistantSkill
    from weather_skill import WeatherSkill
    from web_search_skill import WebSearchSkill
    from news_skill import NewsSkill
except ImportError as e:
    print(f"LLMEngine Critical Error: Could not import one or more skill modules. Error: {e}")
    HomeAssistantSkill = None
    WeatherSkill = None
    WebSearchSkill = None
    NewsSkill = None

# Attempt to import KnowledgeBase
try:
    from .knowledge_base import KnowledgeBase
except ImportError as e:
    print(f"LLMEngine Critical Error: Could not import KnowledgeBase. Error: {e}")
    KnowledgeBase = None

# Attempt to import BaseSkill and signature TypedDicts
try:
    from base_skill import BaseSkill, ToolSignature, ToolParameter
except ImportError as e:
    print(f"LLMEngine Critical Error: Could not import BaseSkill or TypedDicts from base_skill.py. Error: {e}")
    BaseSkill = None
    ToolSignature = Dict[str, Any] # Fallback
    ToolParameter = Dict[str, Any] # Fallback


class LLMEngine:
    def __init__(self,
                 persona_config_path="persona_config.yaml",
                 api_base_url=os.getenv("LLM_API_BASE_URL", "http://localhost:11434/v1"),
                 api_key=os.getenv("LLM_API_KEY", "NotNeededForOllama")):

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.persona_config_path = os.path.join(base_dir, persona_config_path)
        self.persona = None

        self.api_base_url = api_base_url
        self.api_key = api_key
        self.client = None
        try:
            self.client = OpenAI(base_url=self.api_base_url, api_key=self.api_key)
            print(f"LLMEngine initialized with API base URL: {self.api_base_url}")
        except Exception as e:
            print(f"Error initializing OpenAI client: {e}")

        self.memory_manager = MemoryManager(memory_file_path="data/memory.json")
        self.load_persona()

        self.skills: Dict[str, BaseSkill] = {}
        self.tool_signatures: List[ToolSignature] = []

        self._initialize_and_register_skills()
        self.system_prompt = self._construct_system_prompt()

    def register_skill(self, skill_instance: BaseSkill):
        if not BaseSkill or not isinstance(skill_instance, BaseSkill):
            print(f"LLMEngine Error: Attempted to register an object that is not a valid BaseSkill: {type(skill_instance)}")
            return
        try:
            signatures_data = skill_instance.get_tool_signature()
            signatures_list: List[ToolSignature] = []
            if isinstance(signatures_data, dict):
                signatures_list = [signatures_data] # type: ignore
            elif isinstance(signatures_data, list):
                signatures_list = signatures_data # type: ignore
            else:
                print(f"LLMEngine Warning: Skill {type(skill_instance).__name__} provided an invalid signature type ({type(signatures_data)}). Skipping.")
                return

            for sig in signatures_list:
                if not isinstance(sig, dict):
                    print(f"LLMEngine Warning: Skill {type(skill_instance).__name__} provided an invalid signature item (not a dict). Skipping: {sig}")
                    continue
                tool_name = sig.get("tool_name")
                if not tool_name:
                    print(f"LLMEngine Warning: Skill {type(skill_instance).__name__} provided a signature without a tool_name. Skipping.")
                    continue
                if tool_name in self.skills:
                    print(f"LLMEngine Warning: Tool '{tool_name}' from skill {type(skill_instance).__name__} is already registered. Overwriting.")

                self.skills[tool_name] = skill_instance
                self.tool_signatures.append(sig)
                print(f"LLMEngine: Registered tool '{tool_name}' from skill {type(skill_instance).__name__}.")
        except Exception as e:
            print(f"LLMEngine Error: Failed to register skill {type(skill_instance).__name__}. Error: {e}")

    def _initialize_and_register_skills(self):
        if HomeAssistantSkill:
            print("LLMEngine: Initializing HomeAssistantSkill...")
            try:
                self.ha_skill = HomeAssistantSkill() # Legacy attribute
                # TODO: When HomeAssistantSkill is refactored: self.register_skill(self.ha_skill)
                if not self.ha_skill.ha_token or self.ha_skill.ha_token == "YOUR_LONG_LIVED_ACCESS_TOKEN_HERE":
                    print("LLMEngine Warning: HomeAssistantSkill token not configured.")
                else:
                    print("LLMEngine: HomeAssistantSkill initialized (legacy).")
            except Exception as e:
                print(f"LLMEngine Error: Failed to initialize HomeAssistantSkill: {e}")
                self.ha_skill = None
        else:
            self.ha_skill = None

        if KnowledgeBase:
            print("LLMEngine: Initializing KnowledgeBase...")
            try:
                project_root_for_kb = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                kb_persist_directory = os.path.join(project_root_for_kb, "data", "kb_chroma_db")
                self.knowledge_base = KnowledgeBase(persist_directory=kb_persist_directory)
            except Exception as e:
                print(f"LLMEngine Error: Failed to initialize KnowledgeBase: {e}")
                self.knowledge_base = None
        else:
            self.knowledge_base = None

        if WeatherSkill:
            print("LLMEngine: Initializing WeatherSkill...")
            try:
                weather_skill_instance = WeatherSkill()
                self.register_skill(weather_skill_instance) # Register the refactored skill
                # self.weather_skill = None # Remove legacy attribute
            except Exception as e:
                print(f"LLMEngine Error: Failed to initialize or register WeatherSkill: {e}")
        # Ensure legacy attribute is not present or None if class is unavailable
        if hasattr(self, 'weather_skill'): # Check if it was ever defined
            self.weather_skill = None


        if WebSearchSkill:
            print("LLMEngine: Initializing WebSearchSkill...")
            try:
                self.web_search_skill = WebSearchSkill() # Legacy attribute
                # TODO: When WebSearchSkill is refactored: self.register_skill(self.web_search_skill)
                print("LLMEngine: WebSearchSkill initialized (legacy).")
            except Exception as e:
                print(f"LLMEngine Error: Failed to initialize WebSearchSkill: {e}")
                self.web_search_skill = None
        else:
            self.web_search_skill = None

        if NewsSkill:
            print("LLMEngine: Initializing NewsSkill...")
            try:
                self.news_skill = NewsSkill() # Legacy attribute
                # TODO: When NewsSkill is refactored: self.register_skill(self.news_skill)
                print("LLMEngine: NewsSkill initialized (legacy).")
            except Exception as e:
                print(f"LLMEngine Error: Failed to initialize NewsSkill: {e}")
                self.news_skill = None
        else:
            self.news_skill = None

    def _construct_system_prompt(self) -> str:
        prompt_parts = []
        if self.persona:
            name = self.get_persona_attribute('identity.name') or "Assistant"
            background = self.get_persona_attribute('identity.background_story') or "I am a large language model."
            tone = self.get_persona_attribute('tone') or "helpful"
            concise_pref = self.get_persona_attribute('preferences.prefers_concise_answers')
            conciseness = "concise" if concise_pref else "detailed"
            if concise_pref is None: conciseness = "detailed"
            prompt_parts.append(f"You are {name}, a {tone} assistant. Your background is: '{background}'. You prefer {conciseness} answers.")
            if self.get_persona_attribute('preferences.likes_analogies'):
                prompt_parts.append("You like to use analogies in your explanations.")
        else:
            prompt_parts.append("You are a helpful AI assistant.")

        prompt_parts.append("You have access to a knowledge base. When context from this knowledge base is provided with a question, please use it to formulate your answer.")

        user_name = self.recall("user_profile", "name")
        if user_name: prompt_parts.append(f"You are speaking with {user_name}.")
        user_theme_preference = self.recall("user_preferences", "theme")
        if user_theme_preference: prompt_parts.append(f"The user prefers a {user_theme_preference} theme.")

        prompt_parts.append("\n\n--- Available Tools ---")
        prompt_parts.append("To use a tool, you MUST respond ONLY with a JSON object with 'tool_name' and 'parameters' (a dictionary of arguments).")
        if not self.tool_signatures:
            prompt_parts.append("No tools are currently available for you to use via the new framework.")
        else:
            prompt_parts.append("Here are the tools you can use (new framework):")
            for sig in self.tool_signatures:
                prompt_parts.append(f"\nTool: {sig.get('tool_name', 'Unnamed Tool')}")
                prompt_parts.append(f"  Description: {sig.get('description', 'No description.')}")
                param_details = []
                for param in sig.get('parameters', []):
                    param_name = param.get('name', 'unknown_param')
                    param_type = param.get('type', 'unknown_type')
                    param_desc_text = param.get('description', 'No description.')
                    param_desc_str = f"{param_name} ({param_type}): {param_desc_text}"
                    if not param.get('required', True):
                        param_desc_str += " (optional)"
                    param_details.append(param_desc_str)
                if param_details:
                    prompt_parts.append("  Parameters:")
                    for pd in param_details: prompt_parts.append(f"    - {pd}")
                else:
                    prompt_parts.append("  Parameters: None")
                prompt_parts.append("  JSON format for you to output:")
                prompt_parts.append("  {")
                prompt_parts.append(f"    \"tool_name\": \"{sig.get('tool_name', 'Unnamed Tool')}\",")
                prompt_parts.append("    \"parameters\": {")
                example_params = [f"      \"{p.get('name', 'arg')}\": \"<value_for_{p.get('name', 'arg')}>\"" for p in sig.get('parameters', [])]
                if example_params: prompt_parts.append(",\n".join(example_params))
                else: prompt_parts.append("      // No parameters or provide as empty object if none needed")
                prompt_parts.append("    }")
                prompt_parts.append("  }")
        prompt_parts.append("--- End Available Tools ---")

        prompt_parts.append("\n\n--- Legacy Tool Instructions (to be removed after skill refactor) ---")
        prompt_parts.append("\n\n--- Home Assistant Control ---")
        prompt_parts.append("If the user's request is about controlling Home Assistant, use JSON: {\"tool_name\": \"home_assistant\", \"action\": \"<action_name>\", ...}")
        prompt_parts.append("Actions: call_service, get_state, list_entities. Refer to previous detailed examples for parameters.")
        prompt_parts.append("--- End Home Assistant Control ---")
        # Weather legacy instructions removed
        prompt_parts.append("\n\n--- Web Search ---")
        prompt_parts.append("If you need to find current information via web search, use JSON: {\"tool_name\": \"web_search\", \"action\": \"search\", \"query\": \"<query>\"}")
        prompt_parts.append("--- End Web Search ---")
        prompt_parts.append("\n\n--- News Headlines ---")
        prompt_parts.append("If the user asks for news, use JSON: {\"tool_name\": \"news\", \"action\": \"fetch_news\", \"category\": \"<category>\", \"num_headlines\": \"<num>\"}")
        prompt_parts.append("--- End News Headlines ---")
        prompt_parts.append("\n--- End Legacy Tool Instructions ---")
        return " ".join(prompt_parts).strip()

    def refresh_system_prompt(self):
        self.system_prompt = self._construct_system_prompt()

    def remember(self, category: str, key: str, value: any) -> bool:
        return self.memory_manager.set_value(category, key, value)

    def recall(self, category: str, key: str) -> any:
        return self.memory_manager.get_value(category, key)

    def forget(self, category: str, key: str) -> bool:
        return self.memory_manager.delete_value(category, key)

    def get_response(self, user_input: str) -> str:
        if not self.client: return "Eidos (error): OpenAI client not initialized."
        assistant_name = self.get_persona_attribute('identity.name') or "Eidos"
        final_user_content = user_input
        if self.knowledge_base:
            retrieved_docs = self.knowledge_base.query(user_input, n_results=3)
            if retrieved_docs:
                formatted_context = "\n\n---\n\n".join(retrieved_docs)
                context_header = "Based on the following information from my knowledge base, please answer the user's question.\n\nRelevant Information:\n"
                final_user_content = f"{context_header}{formatted_context}\n\n---\nUser's original question: {user_input}"
                print(f"LLMEngine DEBUG: Using augmented prompt with KB context for query: '{user_input[:50]}...'")

        messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": final_user_content}]
        try:
            completion = self.client.chat.completions.create(model="local-model", messages=messages, temperature=0.7)
            llm_response_content = completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"LLMEngine Error during LLM call: {e}")
            return f"{assistant_name}: Error communicating with LLM."

        if llm_response_content:
            try:
                cleaned_response_content = llm_response_content
                if llm_response_content.startswith("```json"):
                    cleaned_response_content = llm_response_content.split("```json", 1)[1].strip()
                    if cleaned_response_content.endswith("```"):
                        cleaned_response_content = cleaned_response_content[:-3].strip()
                data = json.loads(cleaned_response_content)
                tool_name = data.get("tool_name")
                assistant_name_prefix = f"{assistant_name}: "

                if tool_name and BaseSkill and self.skills.get(tool_name):
                    skill_to_execute = self.skills[tool_name]
                    print(f"LLMEngine: Detected call for registered tool: '{tool_name}' with parameters: {data.get('parameters')}")
                    try:
                        tool_args = data.get("parameters", {})
                        if tool_name == "web_search" and "query" in tool_args:
                           tool_args["original_user_query_for_synthesis"] = user_input

                        # The 'action' parameter for skill.execute() is taken from the LLM's JSON if present.
                        # If not present, it defaults to None. Skills must handle this.
                        action_from_llm = data.get("action")
                        result = skill_to_execute.execute(action=action_from_llm, args=tool_args)

                        if tool_name == "web_search" and isinstance(result, dict) and result.get("synthesis_needed"):
                            synthesis_prompt_content = result["synthesis_prompt_content"]
                            original_query_for_synthesis = result.get("original_query", user_input)
                            print(f"LLMEngine: Synthesizing answer from web search results for: '{original_query_for_synthesis[:50]}...'")
                            synthesis_messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": synthesis_prompt_content}]
                            try:
                                synthesis_completion = self.client.chat.completions.create(model="local-model", messages=synthesis_messages, temperature=0.7)
                                synthesized_answer = synthesis_completion.choices[0].message.content.strip()
                                return f"{assistant_name_prefix}{synthesized_answer}"
                            except Exception as e:
                                print(f"LLMEngine: Error during synthesis LLM call: {e}")
                                return f"{assistant_name_prefix}I found information, but had trouble processing it."
                        elif tool_name == "get_weather" and isinstance(result, dict): # Specific formatting for weather
                            if "error" in result:
                                return f"{assistant_name_prefix}{result.get('message', 'An error occurred with the weather tool.')}"
                            temp_unit = "°C" if result.get('units') == "metric" else "°F"
                            wind_speed_unit = "m/s" if result.get('units') == "metric" else "mph"
                            return (f"{assistant_name_prefix}The current weather in {result['city']}, {result['country']} is: "
                                    f"{result['temperature']}{temp_unit} (feels like {result['feels_like']}{temp_unit}). "
                                    f"Description: {result['description']}. "
                                    f"Humidity: {result['humidity']}%. "
                                    f"Wind speed: {result['wind_speed']} {wind_speed_unit}.")
                        elif result is not None:
                            return f"{assistant_name_prefix}{str(result)}"
                        else:
                            return f"{assistant_name_prefix}The {tool_name} tool executed but returned no information."
                    except Exception as e:
                        print(f"LLMEngine: Error executing registered tool '{tool_name}': {e}")
                        return f"{assistant_name_prefix}Error with the {tool_name} tool."

                # Legacy hardcoded tool handling
                elif isinstance(data, dict) and tool_name == "home_assistant" and self.ha_skill:
                    action = data.get("action"); entity_id = data.get("entity_id")
                    if action == "call_service":
                        domain, service, payload = data.get("domain"), data.get("service"), data.get("service_data", {})
                        payload["entity_id"] = entity_id
                        if domain and service and entity_id:
                            if self.ha_skill.call_service(domain, service, payload): return f"{assistant_name_prefix}OK, I've actioned '{service}' on '{entity_id}'."
                            else: return f"{assistant_name_prefix}Failed to perform '{service}' on '{entity_id}'."
                        else: return f"{assistant_name_prefix}Missing domain, service, or entity_id for Home Assistant."
                    elif action == "get_state":
                        if entity_id:
                            state_info = self.ha_skill.get_entity_state(entity_id)
                            if state_info: return f"{assistant_name_prefix}'{entity_id}' is currently '{state_info.get('state', 'unknown')}'."
                            else: return f"{assistant_name_prefix}Could not get state for '{entity_id}'."
                        else: return f"{assistant_name_prefix}Missing entity_id for Home Assistant get_state."
                    elif action == "list_entities":
                        entities = self.ha_skill.list_entities()
                        if entities:
                            names = [f"{e.get('attributes', {}).get('friendly_name', e.get('entity_id'))} ({e.get('entity_id')})" for e in entities]
                            return f"{assistant_name_prefix}Found entities: {', '.join(names[:10])}{', ...and more' if len(names) > 10 else '.'}"
                        else: return f"{assistant_name_prefix}No Home Assistant entities found or error."
                    else: return f"{assistant_name_prefix}Unknown Home Assistant action: '{action}'."

                # Legacy WebSearch (Note: Weather legacy block removed as it's now a BaseSkill)
                elif isinstance(data, dict) and tool_name == "web_search" and self.web_search_skill:
                    action = data.get("action")
                    if action == "search":
                        search_query = data.get("query")
                        if not search_query: return f"{assistant_name_prefix}Search query missing."
                        search_results = self.web_search_skill.search(search_query, num_results=3)
                        if search_results is None: return f"{assistant_name_prefix}Web search error."
                        if not search_results: return f"{assistant_name_prefix}No web results for '{search_query}'."
                        formatted_results = "\n\n".join([f"Title: {r['title']}\nSnippet: {r['snippet']}\nURL: {r['url']}" for r in search_results])
                        synthesis_prompt = (f"User's original question: '{user_input}'\n\nSearch Results:\n{formatted_results}\n\nSynthesize an answer:")
                        print(f"LLMEngine: Synthesizing answer from web search results (legacy path) for: '{user_input[:50]}...'")
                        synthesis_messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": synthesis_prompt}]
                        try:
                            s_completion = self.client.chat.completions.create(model="local-model", messages=synthesis_messages, temperature=0.7)
                            return f"{assistant_name_prefix}{s_completion.choices[0].message.content.strip()}"
                        except Exception as e:
                            print(f"LLMEngine: Error during synthesis LLM call (legacy web_search): {e}")
                            return f"{assistant_name_prefix}Found info, but error processing it."
                    else: return f"{assistant_name_prefix}Unknown Web Search action (legacy): '{action}'."

                elif isinstance(data, dict) and tool_name == "news" and self.news_skill:
                    action = data.get("action")
                    if action == "fetch_news":
                        category = data.get("category"); num_headlines_str = data.get("num_headlines", "5")
                        try: num_headlines = int(num_headlines_str)
                        except ValueError: num_headlines = 5
                        headlines = self.news_skill.fetch_news(category=category, num_headlines=num_headlines)
                        if headlines:
                            response_parts = [f"{assistant_name_prefix}Here are headlines for '{category or 'general'}':"]
                            for i, h in enumerate(headlines): response_parts.append(f"\n{i+1}. {h.get('title')} ({h.get('published')})")
                            return "".join(response_parts)
                        elif headlines == []: return f"{assistant_name_prefix}No news found for '{category or 'general'}'."
                        else: return f"{assistant_name_prefix}Error fetching news."
                    else: return f"{assistant_name_prefix}Unknown News action (legacy): '{action}'."
                else:
                    return llm_response_content
            except json.JSONDecodeError:
                return llm_response_content
            except Exception as e:
                print(f"LLMEngine: Error processing potential tool call: {e}")
                return f"{assistant_name}: Error processing response."
        else:
            return f"{assistant_name}: No response from LLM."

    def load_persona(self):
        try:
            with open(self.persona_config_path, 'r') as f:
                self.persona = yaml.safe_load(f)
            if not self.persona:
                print(f"Warning: Persona configuration file '{self.persona_config_path}' is empty or invalid.")
                self.persona = {}
        except FileNotFoundError:
            print(f"Error: Persona file not found at '{self.persona_config_path}'.")
            self.persona = {}
        except yaml.YAMLError as e:
            print(f"Error: Could not parse persona file. Invalid YAML: {e}")
            self.persona = {}
        except Exception as e:
            print(f"An unexpected error occurred while loading persona: {e}")
            self.persona = {}

    def get_persona_attribute(self, attribute_path):
        if not self.persona: return None
        keys = attribute_path.split('.')
        value = self.persona
        try:
            for key in keys: value = value[key]
            return value
        except (KeyError, TypeError, IndexError): return None

if __name__ == '__main__':
    print("Testing LLMEngine...")
    engine = LLMEngine()
    print(f"API Base URL: {engine.api_base_url}")
    print(f"API Key: {engine.api_key}")
    if engine.persona: print(f"Persona Name: {engine.get_persona_attribute('identity.name')}")
    else: print("Persona not loaded.")
    if not engine.client: print("OpenAI client NOT initialized.")
    else: print("OpenAI client initialized.")

    print(f"\nInitial System Prompt:\n{engine.system_prompt}")

    # Conceptual tests for registered vs legacy skills
    print("\n--- Skill Initialization & Registration Status ---")
    if "get_weather" in engine.skills and isinstance(engine.skills.get("get_weather"), WeatherSkill): # type: ignore
        print("WeatherSkill ('get_weather') is registered in new framework.")
    elif hasattr(engine, 'weather_skill') and engine.weather_skill:
        print("WeatherSkill is using legacy attribute 'self.weather_skill'.")
    else:
        print("WeatherSkill is not available.")

    # ... similar checks for other skills once they are refactored ...

    print("\n--- Conceptual Test for 'get_weather' tool ---")
    simulated_llm_get_weather_json = '''
    {
      "tool_name": "get_weather",
      "parameters": {"city": "Paris", "units": "imperial"}
    }
    '''
    print(f"If LLM produced for 'get_weather' tool: {simulated_llm_get_weather_json.strip()}")
    if "get_weather" in engine.skills:
        print("Expected: LLMEngine dispatches to WeatherSkill.execute() via new framework.")
    elif hasattr(engine, 'weather_skill') and engine.weather_skill: # Legacy fallback check
        print("Expected: LLMEngine dispatches to WeatherSkill via legacy 'weather' tool_name and self.weather_skill.")
    else:
        print("Expected: Error or no action as WeatherSkill is not available.")

    # Test legacy "weather" tool name if it still exists in prompt
    simulated_llm_legacy_weather_json = '''
    {
      "tool_name": "weather",
      "action": "get_current_weather",
      "city": "London"
    }
    '''
    print(f"\nIf LLM produced for legacy 'weather' tool: {simulated_llm_legacy_weather_json.strip()}")
    if hasattr(engine, 'weather_skill') and engine.weather_skill:
         print("Expected: LLMEngine dispatches to WeatherSkill via legacy 'weather' tool_name and self.weather_skill.")
    elif "get_weather" in engine.skills:
        print("Expected: This legacy call might fail or be handled if skill name 'weather' is aliased or also registered.")
    else:
        print("Expected: Error or no action as WeatherSkill is not available by any means.")

    print("\nLLMEngine direct execution test complete.")
