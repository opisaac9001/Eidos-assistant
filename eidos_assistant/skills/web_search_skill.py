from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException # For more specific error handling if desired

class WebSearchSkill:
    def __init__(self):
        """
        Initializes the Web Search Skill.
        """
        # DDGS can be instantiated on-the-fly per search, or once here if preferred.
        # For simplicity and to ensure fresh state if any internal settings were to change,
        # instantiating per search is fine.
        self.ddgs_client = DDGS() # Can initialize proxies, headers, timeout here if needed globally
        print("WebSearchSkill initialized.")

    def search(self, query: str, num_results: int = 3) -> list[dict] | None:
        """
        Performs a web search using DuckDuckGo.

        Args:
            query (str): The search query.
            num_results (int, optional): The maximum number of results to return. Defaults to 3.

        Returns:
            list[dict] | None: A list of search result dictionaries,
                                each containing 'title', 'snippet', and 'url'.
                                Returns None if an error occurs during the search.
        """
        if not query or not query.strip():
            print("WebSearchSkill Error: Query cannot be empty.")
            return [] # Return empty list for empty query, or None if preferred

        print(f"WebSearchSkill: Performing search for '{query}' (max {num_results} results)...")

        try:
            # DDGS().text() returns a list of dictionaries like:
            # [{'title': '...', 'href': '...', 'body': '...'}, ...]
            # No need to specify region, safe_search, or timelimit for basic use.
            # backend="api" is default and generally good. "html" or "lite" are alternatives.
            results = self.ddgs_client.text(
                keywords=query,
                max_results=num_results
            )

            if results is None: # Should not happen with .text() normally, it returns list
                 print(f"WebSearchSkill: No results returned by library for '{query}'.")
                 return []

            # Transform and filter results to ensure they have the keys we expect
            formatted_results = []
            for r in results:
                title = r.get('title')
                snippet = r.get('body') # 'body' is the key for snippet in DDGS().text()
                url = r.get('href')

                if title and snippet and url:
                    formatted_results.append({
                        "title": title,
                        "snippet": snippet,
                        "url": url
                    })

            print(f"WebSearchSkill: Found {len(formatted_results)} formatted results for '{query}'.")
            return formatted_results

        except DuckDuckGoSearchException as e: # Specific to the library
            print(f"WebSearchSkill: DuckDuckGoSearchException during search for '{query}': {e}")
            return None
        except requests.exceptions.RequestException as e: # If DDGS uses requests and it fails at network level
             print(f"WebSearchSkill: Network error (requests.exceptions.RequestException) during search for '{query}': {e}")
             return None
        except Exception as e: # Catch-all for other unexpected errors
            print(f"WebSearchSkill: An unexpected error occurred during search for '{query}': {e}")
            return None

if __name__ == '__main__':
    print("\n--- Testing WebSearchSkill ---")
    skill = WebSearchSkill()

    print("\n--- Test 1: Search for 'What is the capital of France?' ---")
    results1 = skill.search("What is the capital of France?", num_results=3)
    if results1 is not None:
        if results1:
            for i, res in enumerate(results1):
                print(f"Result {i+1}:")
                print(f"  Title: {res['title']}")
                print(f"  Snippet: {res['snippet'][:100]}...") # Print first 100 chars of snippet
                print(f"  URL: {res['url']}")
        else:
            print("No results found for 'What is the capital of France?'.")
    else:
        print("Search failed for 'What is the capital of France?'.")

    print("\n--- Test 2: Search for 'Python programming language benefits' ---")
    results2 = skill.search("Python programming language benefits", num_results=2)
    if results2 is not None:
        if results2:
            for i, res in enumerate(results2):
                print(f"Result {i+1}:")
                print(f"  Title: {res['title']}")
                print(f"  Snippet: {res['snippet'][:100]}...")
                print(f"  URL: {res['url']}")
        else:
            print("No results found for 'Python programming language benefits'.")
    else:
        print("Search failed for 'Python programming language benefits'.")

    print("\n--- Test 3: Search for a query likely to yield few/no specific results ---")
    # Using a very specific, possibly nonsensical query to test empty or near-empty results
    results3 = skill.search("asdfqwerzxcvasdfqwerzxcv unique query string", num_results=3)
    if results3 is not None:
        if results3:
            print(f"Found {len(results3)} results (unexpected for unique string):")
            for i, res in enumerate(results3):
                print(f"Result {i+1}:")
                print(f"  Title: {res['title']}")
                print(f"  Snippet: {res['snippet'][:100]}...")
                print(f"  URL: {res['url']}")
        else:
            print("Correctly found no results for the very unique query string.")
    else:
        print("Search failed for the unique query string (this might indicate an error, not just no results).")

    print("\n--- Test 4: Search with empty query ---")
    results4 = skill.search("") # Should be handled by the skill
    if results4 == []:
        print("Correctly returned empty list for empty query.")
    elif results4 is None:
        print("Search returned None for empty query (might be error).")
    else:
        print(f"Unexpected result for empty query: {results4}")


    print("\nWebSearchSkill testing complete.")
```

One minor correction in the plan: `DDGS().text()` uses `requests` internally, so I've added a `requests.exceptions.RequestException` to the error handling in the code above, just in case it bubbles up, though `DuckDuckGoSearchException` should ideally catch most library-specific network issues. The provided example for `DDGS().text()` returns `None` on error, but the `ddgs_search` library also defines exceptions like `RatelimitException` or `TimeoutException` which are subclasses of `DuckDuckGoSearchException`. Catching `DuckDuckGoSearchException` should cover these. I'll stick to the planned `Exception` for now and specific `DuckDuckGoSearchException`.

The `duckduckgo_search` library might need to be installed. I'll add it to `requirements.txt` in a subsequent step if this subtask focuses only on creating the skill file. For now, the problem statement implies the library is available.
I'll add `requests` to the imports as it's good practice if I'm catching its exceptions, even if `duckduckgo-search` is the primary user. However, on second thought, `duckduckgo-search` should abstract away `requests` errors into its own exception types or return `None`. So, I'll remove the explicit `requests.exceptions.RequestException` catch unless testing shows it's necessary. The `DuckDuckGoSearchException` should be sufficient.
It is also important to note that the `DDGS()` client can be initialized in `__init__` to allow for global settings like proxies or headers, if needed in the future. I've added `self.ddgs_client = DDGS()` in `__init__` and use `self.ddgs_client.text()` in the search method.
