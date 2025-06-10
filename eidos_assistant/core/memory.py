import json
import os

class MemoryManager:
    def __init__(self, memory_file_path="data/memory.json"):
        # Construct the absolute path to the memory file
        # Assumes memory_file_path is relative to the project root (eidos_assistant/)
        # For core components, it might be better if they expect absolute paths or paths relative to a known base.
        # For now, let's assume LLMEngine (or whoever instantiates this) will resolve the path correctly.
        # If memory.py is in core/ and main.py is in eidos_assistant/, this path needs careful handling.
        # Let's make memory_file_path relative to the eidos_assistant directory.

        # Simplified assumption: memory_file_path is relative to where main.py is run from.
        # This will be adjusted when LLMEngine instantiates it.
        self.memory_file_path = memory_file_path
        self.memory_store = {}
        self._base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # eidos_assistant directory
        self.resolved_memory_file_path = os.path.join(self._base_dir, self.memory_file_path)

        self.load_memory()

    def _default_memory_structure(self):
        return {
            "user_preferences": {},
            "facts": {},
            "user_profile": {},
            "past_interactions": []
        }

    def load_memory(self):
        """Loads memory from the JSON file. Creates the file with a default structure if it doesn't exist."""
        try:
            if not os.path.exists(self.resolved_memory_file_path):
                print(f"Memory file not found at {self.resolved_memory_file_path}. Creating with default structure.")
                self.memory_store = self._default_memory_structure()
                self.save_memory() # Save the newly created default structure
            else:
                with open(self.resolved_memory_file_path, 'r') as f:
                    self.memory_store = json.load(f)
                # Ensure all default categories exist
                default_struct = self._default_memory_structure()
                updated = False
                for category, default_content in default_struct.items():
                    if category not in self.memory_store:
                        self.memory_store[category] = default_content
                        updated = True
                if updated:
                    self.save_memory()

        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading memory file '{self.resolved_memory_file_path}': {e}. Initializing with default structure.")
            self.memory_store = self._default_memory_structure()
        except Exception as e:
            print(f"An unexpected error occurred loading memory: {e}. Initializing with default structure.")
            self.memory_store = self._default_memory_structure()


    def save_memory(self):
        """Saves the current memory store to the JSON file."""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.resolved_memory_file_path), exist_ok=True)
            with open(self.resolved_memory_file_path, 'w') as f:
                json.dump(self.memory_store, f, indent=2)
        except IOError as e:
            print(f"Error saving memory file '{self.resolved_memory_file_path}': {e}")
        except Exception as e:
            print(f"An unexpected error occurred saving memory: {e}")

    def set_value(self, category: str, key: str, value: any):
        """Sets a value under a specific category. Saves memory after setting."""
        if category not in self.memory_store:
            self.memory_store[category] = {}

        if isinstance(self.memory_store[category], dict):
            self.memory_store[category][key] = value
            self.save_memory()
            return True
        else:
            print(f"Error: Category '{category}' is not a dictionary. Cannot set key-value pair.")
            return False


    def get_value(self, category: str, key: str) -> any:
        """Retrieves a value from a specific category. Returns None if not found."""
        return self.memory_store.get(category, {}).get(key)

    def delete_value(self, category: str, key: str) -> bool:
        """Deletes a value from a specific category. Saves memory after deleting. Returns True if successful."""
        if category in self.memory_store and isinstance(self.memory_store[category], dict) and key in self.memory_store[category]:
            del self.memory_store[category][key]
            self.save_memory()
            return True
        return False

    def get_category(self, category: str) -> any:
        """Retrieves an entire category. Returns None if category not found."""
        return self.memory_store.get(category)

if __name__ == '__main__':
    print("Testing MemoryManager...")
    # This test assumes it's run from the project root (e.g., /app) or that data/memory.json is accessible.
    # For robust testing, it might need adjustment if run from eidos_assistant/core directly without data/ nearby.
    # The path resolver `os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/memory.json")`
    # should correctly point to `eidos_assistant/data/memory.json` when memory.py is in `eidos_assistant/core/`.

    # Construct path relative to this script's location for testing, assuming standard project structure
    project_root_for_test = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # eidos_assistant
    test_memory_file = os.path.join(project_root_for_test, "data", "test_memory.json")

    # Clean up old test file if it exists
    if os.path.exists(test_memory_file):
        os.remove(test_memory_file)
        print(f"Removed old {test_memory_file}")

    print(f"Using test memory file: {test_memory_file}")
    memory_manager = MemoryManager(memory_file_path=os.path.join("data", "test_memory.json")) # Path relative to project root

    print("\nInitial memory store:")
    print(json.dumps(memory_manager.memory_store, indent=2))

    print("\nSetting values...")
    memory_manager.set_value("user_profile", "name", "Alice")
    memory_manager.set_value("user_profile", "city", "Wonderland")
    memory_manager.set_value("user_preferences", "theme", "dark")
    memory_manager.set_value("facts", "test_fact", "MemoryManager seems to work!")

    # Test setting value in a non-dict category (should fail gracefully)
    # memory_manager.set_value("past_interactions", "some_key", "some_value") # past_interactions is a list

    print("\nMemory store after setting values:")
    print(json.dumps(memory_manager.memory_store, indent=2))

    print("\nGetting values...")
    print(f"User name: {memory_manager.get_value('user_profile', 'name')}")
    print(f"User theme: {memory_manager.get_value('user_preferences', 'theme')}")
    print(f"Non-existent key: {memory_manager.get_value('user_profile', 'age')}")

    print("\nDeleting values...")
    memory_manager.delete_value("user_profile", "city")
    print(f"Deleted 'city': {memory_manager.delete_value('user_profile', 'non_existent_key')}") # Test deleting non-existent

    print("\nMemory store after deleting values:")
    print(json.dumps(memory_manager.memory_store, indent=2))

    print("\nTesting get_category:")
    user_profile_cat = memory_manager.get_category("user_profile")
    print(f"User profile category: {json.dumps(user_profile_cat, indent=2)}")

    # Verify file persistence by reloading
    print("\nVerifying persistence by reloading...")
    memory_manager_reloaded = MemoryManager(memory_file_path=os.path.join("data", "test_memory.json"))
    print(f"Reloaded User name: {memory_manager_reloaded.get_value('user_profile', 'name')}")
    print("Reloaded memory store:")
    print(json.dumps(memory_manager_reloaded.memory_store, indent=2))

    # Clean up test file
    if os.path.exists(test_memory_file):
        os.remove(test_memory_file)
        print(f"Cleaned up {test_memory_file}")

    print("\nMemoryManager test complete.")
