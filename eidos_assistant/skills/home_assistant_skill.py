import os
import requests
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List

from eidos_assistant.skills.base_skill import BaseSkill, ToolSignature, ToolParameter

class HomeAssistantSkill(BaseSkill):
    def __init__(self):
        """
        Initializes the Home Assistant Skill.
        Loads configuration from environment variables.
        """
        super().__init__(name="HomeAssistantSkill", version="0.1.0")
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        if not load_dotenv(dotenv_path=dotenv_path):
            print(f"Warning: {self.name} - Could not load .env file from {dotenv_path}")
        else:
            print(f"Debug: {self.name} - Successfully loaded .env file from {dotenv_path}")

        self.ha_url = os.getenv("HOME_ASSISTANT_URL", "http://localhost:8123")
        self.ha_token = os.getenv("HOME_ASSISTANT_TOKEN")

        self.headers = {} # Will be set if token is valid
        self.api_available = False # Set by check_api_status or implicitly by successful calls

        if not self.ha_token or self.ha_token == "YOUR_LONG_LIVED_ACCESS_TOKEN_HERE" or self.ha_token.strip() == "":
            print(f"{self.name} Warning: HOME_ASSISTANT_TOKEN is not set, is a placeholder, or empty.")
            print(f"{self.name}: Home Assistant functionality will be disabled.")
            self.ha_token = None # Ensure it's None if invalid
        else:
            self.headers = {
                "Authorization": f"Bearer {self.ha_token}",
                "Content-Type": "application/json",
            }
            print(f"{self.name} Initialized. URL: {self.ha_url}. Token Loaded: Yes")
            # Defer full API status check to when a command is run or via /validate_setup
            # self.check_api_status() # Optionally check on init

    def is_configured(self) -> bool:
        """Checks if the skill has the necessary configuration (token) to operate."""
        return bool(self.ha_token)

    def _make_request(self, method: str, endpoint: str, json_data: Optional[Dict] = None, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """Makes an HTTP request to the Home Assistant API."""
        if not self.is_configured():
            print(f"{self.name} Error: Skill not configured (token missing). Cannot make request.")
            return None

        url = f"{self.ha_url.rstrip('/')}/api/{endpoint.lstrip('/')}"
        try:
            response = requests.request(method, url, headers=self.headers, json=json_data, timeout=timeout)
            response.raise_for_status()
            if response.content:
                return response.json()
            return {} # Return empty dict for success with no content (e.g. some service calls)
        except requests.exceptions.HTTPError as e:
            print(f"{self.name} HTTP error: {e.response.status_code} for URL {url}. Response: {e.response.text[:200]}")
            if e.response.status_code == 401:
                print(f"{self.name} Error: Unauthorized (401). Check your HOME_ASSISTANT_TOKEN.")
            elif e.response.status_code == 404:
                print(f"{self.name} Error: Resource not found (404) at {url}.")
        except requests.exceptions.Timeout:
            print(f"{self.name} Error: Timeout connecting to {url}.")
        except requests.exceptions.RequestException as e:
            print(f"{self.name} Error: Request failed for {url}: {e}")
        except Exception as e:
            print(f"{self.name} Error: An unexpected error occurred during request to {url}: {e}")
        return None

    def check_api_status(self) -> bool:
        """
        Checks if the Home Assistant API is running and accessible.
        Returns True if API is okay, False otherwise.
        """
        if not self.is_configured():
            print(f"{self.name} Error: Cannot check API status, skill not configured (token missing).")
            self.api_available = False
            return False

        response_data = self._make_request("GET", "/") # Check base API endpoint
        if response_data is not None and "message" in response_data: # HA typically returns {"message": "API running."}
            print(f"{self.name}: API status OK. Message: {response_data['message']}")
            self.api_available = True
            return True
        else:
            print(f"{self.name}: API status check failed or unexpected response.")
            self.api_available = False
            return False

    def get_tool_signature(self) -> ToolSignature:
        return {
            "tool_name": "home_assistant_control",
            "description": "Controls and queries Home Assistant entities and services. Requires specifying an action.",
            "parameters": [
                {
                    "name": "action", "type": "string",
                    "description": "The action to perform. Supported: 'get_state', 'call_service', 'list_entities'.",
                    "required": True,
                },
                {
                    "name": "entity_id", "type": "string",
                    "description": "Entity ID (e.g., 'light.living_room'). Required for 'get_state' and often for 'call_service'.",
                    "required": False,
                },
                {
                    "name": "domain", "type": "string",
                    "description": "Service domain (e.g., 'light', 'switch'). Required for 'call_service'.",
                    "required": False,
                },
                {
                    "name": "service", "type": "string",
                    "description": "Service name (e.g., 'turn_on', 'toggle'). Required for 'call_service'.",
                    "required": False,
                },
                {
                    "name": "service_data", "type": "object",
                    "description": "Dictionary for service call data (e.g., {'brightness': 255}). Optional for 'call_service'.",
                    "required": False,
                },
                {
                    "name": "device_type_filter", "type": "string",
                    "description": "Filter by device type (e.g., 'light') for 'list_entities'. Optional.",
                    "required": False,
                }
            ]
        }

    def execute(self, action_param_ignored: Optional[str] = None, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.is_configured():
            return {"error": "Home Assistant skill is not configured (missing token)."}
        if args is None:
            return {"error": "No arguments provided for Home Assistant action."}

        action = args.get("action")
        if not action:
            return {"error": "Home Assistant 'action' not specified in arguments."}

        print(f"{self.name}: Executing action '{action}' with args: {args}")

        if action == "get_state":
            entity_id = args.get("entity_id")
            if not entity_id: return {"error": "entity_id is required for get_state."}
            state = self.get_entity_state(entity_id)
            return state if state is not None else {"error": f"Failed to get state for {entity_id} or entity not found."}

        elif action == "call_service":
            domain = args.get("domain")
            service = args.get("service")
            service_data = args.get("service_data", {})
            entity_id = args.get("entity_id") # Can be part of service_data or separate

            if not domain or not service:
                return {"error": "domain and service are required for call_service."}

            # Ensure entity_id from args is in service_data if not already present
            if entity_id and 'entity_id' not in service_data:
                service_data['entity_id'] = entity_id
            elif not entity_id and 'entity_id' not in service_data:
                 # Some services might not require entity_id (e.g. scene.turn_on if scene_id is in service_data)
                 # Or some might operate on areas. For now, we'll mostly assume entity_id is common.
                 # If it's critical and missing, HA will return an error.
                 pass


            success = self.call_service_internal(domain, service, service_data) # Renamed to avoid confusion with old public method
            if success:
                return {"success": True, "message": f"Service {domain}.{service} called successfully with data: {service_data}."}
            else:
                return {"error": f"Failed to call service {domain}.{service} with data: {service_data}."}

        elif action == "list_entities":
            device_type_filter = args.get("device_type_filter")
            entities = self.list_entities_internal(device_type_filter=device_type_filter) # Renamed
            return {"entities": entities if entities is not None else []}

        else:
            return {"error": f"Unknown Home Assistant action: {action}"}

    # Internal methods that perform the actual API calls
    def get_entity_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Internal: Retrieves the state of a specific entity."""
        print(f"{self.name}: Getting state for entity '{entity_id}'...")
        return self._make_request("GET", f"states/{entity_id}")

    def call_service_internal(self, domain: str, service: str, service_data: Dict[str, Any]) -> bool:
        """Internal: Calls a service in Home Assistant."""
        print(f"{self.name}: Calling service '{domain}.{service}' with data: {service_data}...")
        response_data = self._make_request("POST", f"services/{domain}/{service}", json_data=service_data, timeout=10)
        # Successful service calls usually return a list of states changed, or an empty list/dict.
        # The important part is that _make_request didn't return None (which indicates an error).
        return response_data is not None

    def list_entities_internal(self, device_type_filter: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Internal: Lists entities, optionally filtered by the part before the dot (domain/device type)."""
        print(f"{self.name}: Listing entities (filter: {device_type_filter})...")
        all_states = self._make_request("GET", "states")
        if all_states is None: # Error occurred in _make_request
            return None

        if not isinstance(all_states, list): # Expect a list of states
            print(f"{self.name} Error: Unexpected format for /api/states response. Expected list, got {type(all_states)}")
            return None

        if device_type_filter:
            device_type_filter = device_type_filter.lower()
            return [entity for entity in all_states if entity.get("entity_id", "").startswith(device_type_filter + ".")]
        return all_states


if __name__ == '__main__':
    # Note: __main__ is for basic local testing of the skill.
    # It won't reflect how LLMEngine or main.py use it via execute().
    print("Testing HomeAssistantSkill...")
    # This test assumes .env is in eidos_assistant/ and contains relevant HA variables.
    # The load_dotenv call at the top of the skill class should handle it.

    ha_skill = HomeAssistantSkill()

    if ha_skill.ha_token and ha_skill.ha_token != "YOUR_LONG_LIVED_ACCESS_TOKEN_HERE":
        print(f"Attempting to check Home Assistant API status at: {ha_skill.ha_url}")
        status_ok = ha_skill.check_api_status()
        if status_ok:
            print("Home Assistant API is accessible.")

            print("\n--- Testing get_entity_state ---")
            # Test with a common, often present entity if HA is new, or a known one.
            # Users should change this to a valid entity_id from their HA setup for real testing.
            test_entity_id = "sun.sun"
            print(f"Attempting to get state for entity: '{test_entity_id}'")
            state = ha_skill.get_entity_state(test_entity_id)
            if state:
                print(f"State of '{test_entity_id}': {state}")
                print(f"  Current status: {state.get('state')}")
                print(f"  Attributes: {state.get('attributes')}")
            else:
                print(f"Could not retrieve state for '{test_entity_id}'.")
                print("Ensure the entity ID is correct and your Home Assistant server is accessible with the correct token.")

            print("\n--- Testing get_entity_state with a likely non-existent entity ---")
            non_existent_entity_id = "light.this_light_does_not_exist"
            print(f"Attempting to get state for non-existent entity: '{non_existent_entity_id}'")
            state_non_existent = ha_skill.get_entity_state(non_existent_entity_id)
            if state_non_existent is None:
                print(f"Correctly failed to retrieve state for '{non_existent_entity_id}' (expected failure).")
            else:
                print(f"Unexpectedly retrieved state for '{non_existent_entity_id}': {state_non_existent}")

            print("\n--- Testing call_service (e.g., toggle a light) ---")
            # Users should change this to a valid entity_id from their HA setup for real testing.
            test_service_entity_id = "light.living_room_light_placeholder" # Placeholder
            service_domain = "homeassistant" # Generic domain for 'toggle', 'turn_on', 'turn_off'
            service_name = "toggle"
            service_payload = {"entity_id": test_service_entity_id}

            print(f"Attempting to call service '{service_domain}.{service_name}' for entity: '{test_service_entity_id}'")
            # Note: This is a conceptual test. Calling toggle will actually change the state on a real HA instance.
            # In a sandbox/mocked test, we just check if the call structure is okay.
            service_called_successfully = ha_skill.call_service(service_domain, service_name, service_payload)

            if service_called_successfully:
                print(f"Service '{service_domain}.{service_name}' for '{test_service_entity_id}' called successfully (or at least API accepted the request).")
                print("Check your Home Assistant instance to see if the entity state changed.")
            else:
                print(f"Failed to call service '{service_domain}.{service_name}' for '{test_service_entity_id}'.")
                print("Ensure the entity ID is correct, the service exists, and HA is accessible with the correct token.")
        else:
            print("Home Assistant API is NOT accessible or token is invalid. Check URL, token, and HA server status.")
            print("If this is the first run, ensure your .env file is correctly set up with HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN.")
            print("\nSkipping get_entity_state and call_service tests as API status was not OK or token not configured.")
    else:
        print("Skipping API status check as Home Assistant token is not configured or is placeholder.")
        print("Please set HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN in your .env file for full functionality.")
        print("\nSkipping get_entity_state and call_service tests as token not configured.")

    print("\nHomeAssistantSkill test complete.")
