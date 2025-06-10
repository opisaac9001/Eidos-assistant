# Eidos Assistant

Eidos Assistant is a conversational AI assistant designed to be extensible and run locally. This project is being developed iteratively.

## Prerequisites

*   Python (version 3.8+ recommended)
*   Pip (Python package installer)
*   Access to a local Large Language Model (LLM) server that is compatible with the OpenAI API.

## Installation

1.  Clone this repository.
2.  Install required Python packages:
    ```bash
    # Placeholder for requirements.txt installation command
    # pip install -r requirements.txt
    # (requirements.txt will be added in a future step)
    # For now, necessary libraries like PyYAML and OpenAI will be installed by specific subtasks.
    ```

## Running the Assistant

Currently, the assistant runs via a command-line interface:

```bash
python eidos_assistant/main.py
```

**Important for Conversational AI:**

To enable full conversational capabilities, you need a local LLM server running that is compatible with the OpenAI API (e.g., Ollama, LM Studio, VLLM).
The assistant is configured by default to attempt to connect to an LLM at `http://localhost:11434/v1` (a common endpoint for Ollama). If your LLM server is running on a different address or port, you will need to configure this in the `LLMEngine` (details to be updated as configuration options are added).

Ensure your LLM server is running *before* starting the Eidos Assistant. If the assistant cannot connect to the LLM, it will indicate an error.

## Project Structure

*   `core/`: Core components like the LLM engine and persona configuration.
*   `core/memory.py`: Manages the assistant's long-term memory.
*   `interface/`: User interface components (e.g., voice I/O).
*   `skills/`: Future directory for assistant skills/plugins.
*   `ingestion/`: Future directory for data ingestion pipelines.
*   `data/`: Data storage (e.g., databases, logs).
*   `data/memory.json`: Stores data like user preferences, facts, and profile information.
*   `main.py`: Main application entry point.

## Using Memory Commands

You can interact with the assistant's long-term memory using special slash commands:

*   `/remember <category>.<key>=<value>`: Stores a piece of information.
    *   Example: `/remember user_profile.name=Alice`
    *   Example: `/remember user_preferences.theme=dark`
    *   If you update `user_profile.name` or `user_preferences.theme`, the assistant's system prompt will be updated immediately to reflect this change.
    *   Values are attempted to be saved as boolean (`true`/`false`), integer, or float if they match, otherwise as string.

*   `/recall <category>.<key>`: Retrieves a piece of information from memory.
    *   Example: `/recall user_profile.name`

*   `/forget <category>.<key>`: Removes a piece of information from memory.
    *   Example: `/forget user_profile.name`
    *   If this affects the system prompt (e.g. forgetting `user_profile.name`), the prompt will be updated.

*   `/system_prompt`: (Debug command) Prints the current system prompt that the LLM engine is using.
