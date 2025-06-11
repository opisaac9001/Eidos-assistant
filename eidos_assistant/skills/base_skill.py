from abc import ABC, abstractmethod
from typing import Any, Dict, List, TypedDict, Literal

# For defining the structure of parameters within the tool signature
class ToolParameter(TypedDict, total=False): # total=False means not all keys are required
    name: str
    type: Literal["string", "integer", "number", "boolean", "array", "object"]
    description: str
    required: bool
    # For 'array' type, specify item type; for 'object', describe properties (not fully modeled here for simplicity)
    items: Dict[str, str] # e.g., {"type": "string"} for array of strings
    # For 'object' type, properties could be a dict of ToolParameter-like structures (recursive)
    # properties: Dict[str, 'ToolParameter'] # This would need forward declaration or careful typing

class ToolSignature(TypedDict):
    tool_name: str
    description: str
    parameters: List[ToolParameter]
    # Optional: Define specific actions if a tool has multiple sub-functions
    # actions: List[Dict[str, Any]] # Each dict could define an action name, description, and its specific params

class BaseSkill(ABC):
    """
    Abstract base class for all skills.
    Skills must implement methods to provide their signature to the LLM
    and to execute their functionality based on arguments.
    """

    def __init__(self):
        """
        Basic initializer for BaseSkill.
        Subclasses can extend this.
        """
        pass

    @abstractmethod
    def get_tool_signature(self) -> ToolSignature | List[ToolSignature]:
        """
        Returns the tool signature (or a list of signatures if the skill provides multiple tools)
        that describes the skill's capabilities to an LLM.

        The signature should follow a structure similar to OpenAPI function descriptions
        or JSON Schema, enabling the LLM to understand how to use the tool.

        Example structure for a single tool:
        {
            "tool_name": "weather_tool",
            "description": "Fetches the current weather for a specified city.",
            "parameters": [
                {
                    "name": "city",
                    "type": "string",
                    "description": "The name of the city for which to get the weather.",
                    "required": True
                },
                {
                    "name": "units",
                    "type": "string",
                    "description": "Units for temperature: 'metric' (Celsius) or 'imperial' (Fahrenheit). Defaults to 'metric'.",
                    "required": False
                }
            ]
            # If the tool had distinct actions, they could be part of the signature,
            # or the skill could return multiple ToolSignatures.
            # For example, a HomeAssistant skill might have:
            # "actions": [
            #     {"name": "get_state", "description": "Get state of an entity", "parameters": [...]},
            #     {"name": "call_service", "description": "Call a service on an entity", "parameters": [...]}
            # ]
            # In this case, the 'action' would be a primary parameter passed to execute().
        }

        If a skill provides multiple distinct tools/actions that should be advertised separately
        to the LLM, this method can return a list of such signature dictionaries.
        """
        pass

    @abstractmethod
    def execute(self, action: str | None, args: Dict[str, Any]) -> Any:
        """
        Executes the skill's functionality.

        Args:
            action (str | None): The specific action to perform if the skill supports multiple actions
                                 (e.g., "get_state", "call_service" for a Home Assistant skill).
                                 This corresponds to an action defined within or alongside the tool signature.
                                 Can be None if the tool has only one primary function.
            args (Dict[str, Any]): A dictionary of arguments for the action,
                                   as expected by the skill based on its signature.
                                   Argument names should match the 'name' field in the
                                   parameters list of the tool signature.

        Returns:
            Any: The result of the skill's execution. This could be a string, a dictionary,
                 a list, or any other type. The LLMEngine will typically process this
                 result (e.g., format it into a string for the user or use it to inform
                 a subsequent LLM call for synthesis).
                 If an error occurs during execution that the skill cannot recover from,
                 it might return None or raise an exception (which should ideally be caught
                 and handled by the LLMEngine's tool processing logic).
        """
        pass

if __name__ == '__main__':
    # This is an abstract class and cannot be instantiated directly.
    # The following is for demonstration of how a concrete skill might use it.

    class MockSkill(BaseSkill):
        def get_tool_signature(self) -> ToolSignature:
            return {
                "tool_name": "mock_tool",
                "description": "A mock tool for demonstration.",
                "parameters": [
                    {
                        "name": "message",
                        "type": "string",
                        "description": "A message to echo.",
                        "required": True
                    },
                    {
                        "name": "repeat",
                        "type": "integer",
                        "description": "How many times to repeat the message.",
                        "required": False
                    }
                ]
            }

        def execute(self, action: str | None, args: Dict[str, Any]) -> str:
            # This mock tool doesn't use 'action', assuming one primary function.
            message = args.get("message", "No message provided")
            repeat_count = args.get("repeat", 1)

            if not isinstance(repeat_count, int) or repeat_count < 1:
                repeat_count = 1

            result_parts = [message] * repeat_count
            return " ".join(result_parts)

    print("--- Testing MockSkill (derived from BaseSkill) ---")
    mock_skill = MockSkill()

    # Get signature
    signature = mock_skill.get_tool_signature()
    print("\nTool Signature:")
    import json # For pretty printing the dict
    print(json.dumps(signature, indent=2))

    # Execute tool
    print("\nExecution Test 1 (message only):")
    execution_args1 = {"message": "Hello from MockSkill"}
    result1 = mock_skill.execute(action=None, args=execution_args1)
    print(f"Result: {result1}")

    print("\nExecution Test 2 (message and repeat):")
    execution_args2 = {"message": "Test", "repeat": 3}
    result2 = mock_skill.execute(action=None, args=execution_args2)
    print(f"Result: {result2}")

    print("\nExecution Test 3 (missing required arg - handled by mock):")
    execution_args3 = {"repeat": 2}
    result3 = mock_skill.execute(action=None, args=execution_args3)
    print(f"Result: {result3}")

    print("\nBaseSkill demonstration complete.")
