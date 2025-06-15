from typing import Dict, Any, Optional, List
from duckduckgo_search import DDGS
from eidos_assistant.skills.base_skill import BaseSkill, ToolSignature, ToolParameter

class WebSearchSkill(BaseSkill):
    def __init__(self, default_num_results: int = 3):
        super().__init__(name="WebSearchSkill", version="0.1.0")
        self.default_num_results = default_num_results
        print("WebSearchSkill initialized.")

    def get_tool_signature(self) -> ToolSignature:
        return {
            "tool_name": "perform_web_search",
            "description": "Performs a web search using DuckDuckGo and returns a list of search results. This is a general web search.",
            "parameters": [
                {
                    "name": "query",
                    "type": "string",
                    "description": "The search query.",
                    "required": True,
                },
                {
                    "name": "num_results",
                    "type": "integer",
                    "description": f"The maximum number of search results to return (default: {self.default_num_results}).",
                    "required": False,
                }
            ]
        }

    def execute(self, action: Optional[str] = None, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if args is None:
            args = {}

        query = args.get("query")
        num_results = args.get("num_results", self.default_num_results)

        if not isinstance(num_results, int) or num_results <= 0:
            num_results = self.default_num_results

        if not query or not isinstance(query, str) or not query.strip():
            return {"error": "Search query cannot be empty."}

        print(f"WebSearchSkill: Performing search for '{query}' (max {num_results} results)...")

        try:
            # Use DDGS().text() for general web search results
            # results_list = DDGS().text(keywords=query, max_results=num_results)
            # DDGS().text returns a list of dicts like:
            # [{'title': '...', 'href': '...', 'body': '...'}, ...]

            # Using DDGS().news() if we want news-specific results, but the tool is general.
            # results_list = DDGS().news(keywords=query, maxresults=num_results)
            # [{'date': '...', 'title': '...', 'body': '...', 'url': '...', 'source': '...'}, ...]

            # For general web search, DDGS().text is more appropriate.
            # The results are dictionaries with 'title', 'href', 'body'.
            with DDGS() as ddgs: # Using context manager for DDGS if it supports it (good practice)
                                 # The library's typical usage is direct instantiation.
                results_list: Optional[List[Dict[str, str]]] = ddgs.text(keywords=query, max_results=num_results)


            if results_list is None: # Should not happen with ddgs.text if no exception, but good to check
                results_list = []

            if not results_list:
                return {
                    "synthesis_needed": True,
                    "synthesis_prompt_content": f"No search results found for query: '{query}'"
                }

            # Format results for the synthesis prompt
            search_results_str_parts = []
            for i, r in enumerate(results_list):
                title = r.get('title', 'N/A')
                href = r.get('href', 'N/A')
                body = r.get('body', 'N/A')
                search_results_str_parts.append(f"Result {i+1}:\nTitle: {title}\nURL: {href}\nSnippet: {body}")

            search_results_str = "\n\n".join(search_results_str_parts)

            # This is the content that will be fed into the synthesis prompt by LLMEngine
            synthesis_content = (
                f"Search Query: \"{query}\"\n\n"
                f"Found {len(results_list)} results:\n\n{search_results_str}"
            )

            return {
                "synthesis_needed": True,
                "synthesis_prompt_content": synthesis_content,
                "original_query_for_synthesis": query # Pass the original query along for context
            }

        except Exception as e:
            print(f"WebSearchSkill Error: Exception during web search for '{query}': {e}")
            import traceback
            traceback.print_exc()
            return {"error": f"Failed to perform web search for '{query}'. Exception: {str(e)}"}

if __name__ == '__main__':
    print("Testing WebSearchSkill...")
    skill = WebSearchSkill(default_num_results=2)

    print("\n--- Tool Signature ---")
    signature = skill.get_tool_signature()
    print(signature)

    print("\n--- Performing Web Search (Normal) ---")
    # Test case 1: Valid query
    search_args_valid = {"query": "latest AI advancements"}
    result_valid = skill.execute(args=search_args_valid)
    if "error" in result_valid:
        print(f"Error: {result_valid['error']}")
    elif result_valid.get("synthesis_needed"):
        print("Search successful, synthesis needed.")
        print("Content for synthesis prompt:")
        print(result_valid.get("synthesis_prompt_content"))
        print(f"Original query for synthesis: {result_valid.get('original_query_for_synthesis')}")


    print("\n--- Performing Web Search (Empty Query) ---")
    # Test case 2: Empty query
    search_args_empty = {"query": ""}
    result_empty = skill.execute(args=search_args_empty)
    if "error" in result_empty:
        print(f"Error (expected): {result_empty['error']}")
    else:
        print(f"Unexpected success for empty query: {result_empty}")

    print("\n--- Performing Web Search (No Results Expected) ---")
    # Test case 3: Query likely to yield no results
    search_args_no_results = {"query": "asdfqwerzxcvasdfqwerzxcvuniquequery"}
    result_no_results = skill.execute(args=search_args_no_results)
    if "error" in result_no_results:
        print(f"Error: {result_no_results['error']}")
    elif result_no_results.get("synthesis_needed"):
        print("Search successful (even if no results found), synthesis needed.")
        print("Content for synthesis prompt:")
        print(result_no_results.get("synthesis_prompt_content"))

    print("\nWebSearchSkill test complete.")
