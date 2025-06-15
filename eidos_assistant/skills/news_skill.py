import feedparser
import datetime
from typing import List, Dict, Any, Optional, Union # Added Union for type hints

# Assuming BaseSkill, ToolSignature, ToolParameter are in a discoverable path
# For this project structure, it would be:
from eidos_assistant.skills.base_skill import BaseSkill, ToolSignature, ToolParameter

class NewsSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="NewsSkill", version="0.1.0")
        # Define some default RSS feeds with categories
        self.rss_feeds = {
            "general": "http://feeds.bbci.co.uk/news/rss.xml", # BBC News (General)
            "technology": "http://feeds.bbci.co.uk/news/technology/rss.xml", # BBC News (Technology)
            "sports": "http://feeds.bbci.co.uk/news/sport/rss.xml", # BBC News (Sport)
            "world": "http://feeds.bbci.co.uk/news/world/rss.xml", # BBC News (World)
            # Add more feeds or make this configurable
            "science": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        }
        self.default_category = "general"
        self.default_max_headlines = 5
        print("NewsSkill initialized.")

    def get_tool_signature(self) -> ToolSignature:
        return {
            "tool_name": "get_news_headlines",
            "description": "Fetches recent news headlines, optionally filtered by category. Available categories: general, technology, sports, world, science.",
            "parameters": [
                {
                    "name": "category",
                    "type": "string",
                    "description": "The category of news to fetch (e.g., 'general', 'technology', 'sports', 'world', 'science'). If not provided, fetches general news.",
                    "required": False,
                },
                {
                    "name": "num_headlines",
                    "type": "integer",
                    "description": "The maximum number of headlines to return (default is 5).",
                    "required": False,
                }
            ]
        }

    def execute(self, action: Optional[str] = None, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if args is None:
            args = {}

        category_arg = args.get("category", self.default_category).lower()
        num_headlines = args.get("num_headlines", self.default_max_headlines)

        if not isinstance(num_headlines, int) or num_headlines <= 0:
            num_headlines = self.default_max_headlines

        # If a specific category is requested, use its feed. Otherwise, use the default.
        if category_arg in self.rss_feeds:
            feed_url = self.rss_feeds[category_arg]
            category_used = category_arg
        else:
            # Fallback to default if category is unknown or not specified properly
            # Or, could return an error if category_arg was provided but not found.
            # For now, let's default to general news if category is invalid.
            if category_arg != self.default_category and "category" in args: # User specified an invalid category
                 print(f"NewsSkill Warning: Category '{category_arg}' not found. Falling back to '{self.default_category}'.")
            feed_url = self.rss_feeds[self.default_category]
            category_used = self.default_category
            # Consider returning an error if the user *explicitly* asked for a non-existent category.
            # For now, this behavior defaults to 'general' news.

        print(f"NewsSkill: Fetching {num_headlines} headlines for category '{category_used}' from {feed_url}")

        headlines = []
        try:
            feed = feedparser.parse(feed_url)

            if feed.bozo: # Check for malformed feed
                bozo_exception = feed.get("bozo_exception", "Unknown parsing error")
                print(f"NewsSkill Error: Feed at {feed_url} may be malformed. Exception: {bozo_exception}")
                # Depending on severity, you might want to return an error here.
                # For now, try to process entries anyway if any exist.
                if not feed.entries: # If truly no entries due to error
                     return {"error": f"Failed to parse RSS feed from {feed_url}. Malformed feed. Details: {bozo_exception}"}


            for entry in feed.entries[:num_headlines]:
                title = entry.get("title", "N/A")
                link = entry.get("link", "#")
                source_name = feed.feed.get("title", "N/A") if hasattr(feed, 'feed') else 'N/A'

                published_time = "N/A"
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        # Format datetime object into a more readable string
                        dt_obj = datetime.datetime(*entry.published_parsed[:6])
                        published_time = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        published_time = entry.get("published", "N/A") # Fallback to raw string
                elif hasattr(entry, 'published'):
                     published_time = entry.published


                headlines.append({
                    "title": title,
                    "link": link,
                    "source": source_name,
                    "published": published_time
                })

            if not headlines and feed.entries:
                # This case implies we processed entries but couldn't extract any valid headlines
                print(f"NewsSkill Warning: No headlines extracted from {len(feed.entries)} entries. Check entry structure.")
            elif not headlines:
                 print(f"NewsSkill Info: No news entries found in the feed for category '{category_used}'.")


            return {"headlines": headlines, "category_used": category_used, "feed_url_used": feed_url}

        except Exception as e:
            print(f"NewsSkill Error: Exception while fetching or parsing news from {feed_url}: {e}")
            import traceback
            traceback.print_exc()
            return {"error": f"Failed to fetch or parse news from {feed_url}. Exception: {str(e)}"}

if __name__ == '__main__':
    # Basic test for the NewsSkill
    print("Testing NewsSkill...")
    skill = NewsSkill()

    print("\n--- Tool Signature ---")
    signature = skill.get_tool_signature()
    print(signature)

    print("\n--- Fetching General News (Default) ---")
    general_news_args = {}
    result_general = skill.execute(args=general_news_args)
    if "error" in result_general:
        print(f"Error: {result_general['error']}")
    else:
        print(f"Category: {result_general.get('category_used')}")
        for i, headline in enumerate(result_general.get("headlines", [])):
            print(f"  {i+1}. {headline['title']}")
            print(f"     Link: {headline['link']}")
            print(f"     Source: {headline['source']}, Published: {headline['published']}")

    print("\n--- Fetching Technology News (3 headlines) ---")
    tech_news_args = {"category": "technology", "num_headlines": 3}
    result_tech = skill.execute(args=tech_news_args)
    if "error" in result_tech:
        print(f"Error: {result_tech['error']}")
    else:
        print(f"Category: {result_tech.get('category_used')}")
        for i, headline in enumerate(result_tech.get("headlines", [])):
            print(f"  {i+1}. {headline['title']}")
            print(f"     Link: {headline['link']}")
            print(f"     Source: {headline['source']}, Published: {headline['published']}")

    print("\n--- Fetching News for non-existent category ---")
    invalid_cat_args = {"category": "nonexistent"}
    result_invalid = skill.execute(args=invalid_cat_args)
    if "error" in result_invalid: # Should not be an error, but default to general
        print(f"Error: {result_invalid['error']}")
    else:
        print(f"Category (should be default): {result_invalid.get('category_used')}")
        for i, headline in enumerate(result_invalid.get("headlines", [])):
            print(f"  {i+1}. {headline['title']}")
            # print(f"     Link: {headline['link']}")
            # print(f"     Source: {headline['source']}, Published: {headline['published']}")


    print("\nNewsSkill test complete.")
