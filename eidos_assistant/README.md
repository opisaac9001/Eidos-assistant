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
*   `interface/`: User interface components (e.g., voice I/O).
*   `skills/`: Future directory for assistant skills/plugins.
*   `ingestion/`: Future directory for data ingestion pipelines.
*   `data/`: Data storage (e.g., databases, logs).
*   `main.py`: Main application entry point.
