import os
import requests
from dotenv import load_dotenv

class HomeAssistantSkill:
    def __init__(self):
        """
        Initializes the Home Assistant Skill.
        Loads configuration from environment variables.
        """
        # Load .env file from project root (eidos_assistant/.env)
        # Assumes this skill file is in eidos_assistant/skills/
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        if not load_dotenv(dotenv_path=dotenv_path):
            print(f"Warning: HomeAssistantSkill - Could not load .env file from {dotenv_path}")
        else:
            print(f"Debug: HomeAssistantSkill - Successfully loaded .env file from {dotenv_path}")

        self.ha_url = os.getenv("HOME_ASSISTANT_URL", "http://localhost:8123") # Default if not in .env
        self.ha_token = os.getenv("HOME_ASSISTANT_TOKEN", None)

        self.headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json",
        }

        self.api_available = False # Will be set by check_api_status

        if not self.ha_token or self.ha_token == "YOUR_LONG_LIVED_ACCESS_TOKEN_HERE":
            print("HomeAssistantSkill Warning: HOME_ASSISTANT_TOKEN is not set or is a placeholder.")
            print("Home Assistant functionality will be disabled.")
        else:
            # Automatically check API status on init, but don't prevent instantiation
            # self.api_available = self.check_api_status() # Can be called explicitly later if needed
            print(f"HomeAssistantSkill Initialized. URL: {self.ha_url}. Token Loaded: {'Yes' if self.ha_token else 'No'}")
            print("Call check_api_status() to verify connection to Home Assistant.")


    def check_api_status(self) -> bool:
        """
        Checks if the Home Assistant API is running and accessible.
        Returns True if API is okay, False otherwise.
        """
        if not self.ha_token or self.ha_token == "YOUR_LONG_LIVED_ACCESS_TOKEN_HERE":
            print("HomeAssistantSkill Error: Cannot check API status, token not configured or is placeholder.")
            self.api_available = False
            return False

        api_url = f"{self.ha_url.rstrip('/')}/api/"
        print(f"HomeAssistantSkill: Checking API status at {api_url}...")

        try:
            response = requests.get(api_url, headers=self.headers, timeout=5)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)

            # Check content for expected message if possible, some HA versions might differ slightly
            # For now, a 200 OK is a good sign.
            if response.status_code == 200:
                # Example: response.json() might be {"message": "API running."}
                # For now, just checking status code is enough.
                print(f"HomeAssistantSkill: API status OK (HTTP {response.status_code}). Response: {response.text[:100]}...")
                self.api_available = True
                return True
            else:
                # This case might not be reached if raise_for_status() handles it
                print(f"HomeAssistantSkill: API status check failed. Status: {response.status_code}, Response: {response.text}")
                self.api_available = False
                return False
        except requests.exceptions.Timeout:
            print(f"HomeAssistantSkill: API status check timed out for {api_url}.")
            self.api_available = False
            return False
        except requests.exceptions.RequestException as e:
            print(f"HomeAssistantSkill: Error connecting to Home Assistant API at {api_url}: {e}")
            self.api_available = False
            return False
        except Exception as e:
            print(f"HomeAssistantSkill: An unexpected error occurred during API status check: {e}")
            self.api_available = False
            return False

    def get_entity_state(self, entity_id: str) -> dict | None:
        """
        Retrieves the state of a specific entity from Home Assistant.
        Returns the entity's state dictionary or None on error.
        """
        if not self.api_available and not self.check_api_status(): # Check status if not known to be available
             print(f"HomeAssistantSkill Error: API not available. Cannot get entity state for {entity_id}.")
             return None
        # Re-check token specifically for this action too, in case check_api_status wasn't called or state changed
        if not self.ha_token or self.ha_token == "YOUR_LONG_LIVED_ACCESS_TOKEN_HERE":
            print(f"HomeAssistantSkill Error: Token not configured. Cannot get entity state for {entity_id}.")
            return None

        entity_api_url = f"{self.ha_url.rstrip('/')}/api/states/{entity_id}"
        print(f"HomeAssistantSkill: Getting state for entity '{entity_id}' from {entity_api_url}...")

        try:
            response = requests.get(entity_api_url, headers=self.headers, timeout=5)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)

            entity_state = response.json()
            print(f"HomeAssistantSkill: Successfully retrieved state for '{entity_id}'. State: {entity_state.get('state')}")
            return entity_state

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"HomeAssistantSkill: Entity '{entity_id}' not found (HTTP 404).")
            else:
                print(f"HomeAssistantSkill: HTTP error getting state for '{entity_id}': {e}")
        except requests.exceptions.Timeout:
            print(f"HomeAssistantSkill: Timeout getting state for '{entity_id}'.")
        except requests.exceptions.RequestException as e:
            print(f"HomeAssistantSkill: Error getting state for '{entity_id}': {e}")
        except Exception as e:
            print(f"HomeAssistantSkill: An unexpected error occurred while getting state for '{entity_id}': {e}")

        return None

    def list_entities(self) -> list[dict] | None:
        """
        Retrieves a list of all entities and their basic information from Home Assistant.
        Returns a list of entity dictionaries or None on error.
        """
        if not self.api_available and not self.check_api_status():
            print("HomeAssistantSkill Error: API not available. Cannot list entities.")
            return None
        if not self.ha_token or self.ha_token == "YOUR_LONG_LIVED_ACCESS_TOKEN_HERE":
            print("HomeAssistantSkill Error: Token not configured. Cannot list entities.")
            return None

        entities_api_url = f"{self.ha_url.rstrip('/')}/api/states"
        print(f"HomeAssistantSkill: Listing entities from {entities_api_url}...")

        try:
            response = requests.get(entities_api_url, headers=self.headers, timeout=10) # Increased timeout for potentially large response
            response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)

            all_entities_data = response.json()
            processed_entities = []
            for entity_data in all_entities_data:
                entity_id = entity_data.get('entity_id', 'Unknown Entity ID')
                state = entity_data.get('state', 'Unknown State')
                friendly_name = entity_data.get('attributes', {}).get('friendly_name', entity_id) # Default to entity_id if no friendly_name
                processed_entities.append({
                    'entity_id': entity_id,
                    'state': state,
                    'friendly_name': friendly_name
                })

            print(f"HomeAssistantSkill: Successfully retrieved and processed {len(processed_entities)} entities.")
            return processed_entities

        except requests.exceptions.HTTPError as e:
            print(f"HomeAssistantSkill: HTTP error listing entities: {e}")
        except requests.exceptions.Timeout:
            print(f"HomeAssistantSkill: Timeout listing entities from {entities_api_url}.")
        except requests.exceptions.RequestException as e:
            print(f"HomeAssistantSkill: Error listing entities: {e}")
        except Exception as e: # Catch any other unexpected errors
            print(f"HomeAssistantSkill: An unexpected error occurred while listing entities: {e}")

        return None # Return None in case of any exception

    def call_service(self, domain: str, service: str, service_data: dict) -> bool:
        """
        Calls a service in Home Assistant (e.g., to turn on a light, toggle a switch).
        Returns True on success, False on error.
        """
        if not self.api_available and not self.check_api_status(): # Check status if not known to be available
            print(f"HomeAssistantSkill Error: API not available. Cannot call service {domain}.{service}.")
            return False
        if not self.ha_token or self.ha_token == "YOUR_LONG_LIVED_ACCESS_TOKEN_HERE":
            print(f"HomeAssistantSkill Error: Token not configured. Cannot call service {domain}.{service}.")
            return False

        service_api_url = f"{self.ha_url.rstrip('/')}/api/services/{domain}/{service}"
        print(f"HomeAssistantSkill: Calling service '{domain}.{service}' at {service_api_url} with data: {service_data}...")

        try:
            response = requests.post(service_api_url, headers=self.headers, json=service_data, timeout=10) # Longer timeout for actions
            response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)

            # A 200 OK response usually means the service call was accepted by Home Assistant.
            # The response body contains a list of states of entities that were changed by the service call,
            # or an empty list if no entities were changed or the service doesn't report state changes this way.
            print(f"HomeAssistantSkill: Service call '{domain}.{service}' successful (HTTP {response.status_code}).")
            # print(f"Response data: {response.json()}") # Optional: log the response data
            return True

        except requests.exceptions.HTTPError as e:
            print(f"HomeAssistantSkill: HTTP error calling service '{domain}.{service}': {e}")
            print(f"Response content: {e.response.text}")
        except requests.exceptions.Timeout:
            print(f"HomeAssistantSkill: Timeout calling service '{domain}.{service}'.")
        except requests.exceptions.RequestException as e:
            print(f"HomeAssistantSkill: Error calling service '{domain}.{service}': {e}")
        except Exception as e:
            print(f"HomeAssistantSkill: An unexpected error occurred while calling service '{domain}.{service}': {e}")

        return False

if __name__ == '__main__':
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

            print("\n--- Testing list_entities ---")
            entities = ha_skill.list_entities()
            if entities is not None: # Check if it's not None (could be empty list on success)
                print(f"Found {len(entities)} entities.")
                if not entities: # Specifically check for an empty list
                    print("  No entities found on the Home Assistant instance.")
                else:
                    # Print details of the first few entities as an example
                    entities_to_show = 5
                    for i, entity in enumerate(entities[:entities_to_show]):
                        print(f"  Entity {i+1}: ID={entity.get('entity_id')}, State='{entity.get('state')}', FriendlyName='{entity.get('friendly_name')}'")
                    if len(entities) > entities_to_show:
                        print(f"  ... and {len(entities) - entities_to_show} more.")
            else: # This means entities is None, indicating an error during the call
                print("Could not retrieve entities list (call returned None). Check logs for errors.")

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
