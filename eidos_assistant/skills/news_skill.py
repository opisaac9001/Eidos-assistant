import feedparser
from datetime import datetime, timezone
import time
import re # For basic HTML stripping

class NewsSkill:
    def __init__(self):
        """
        Initializes the News Skill with default RSS feed URLs.
        """
        self.default_feed_urls = {
            "World News": "http://feeds.bbci.co.uk/news/world/rss.xml",
            "Tech News": "https://techcrunch.com/feed/",
            "Science News": "http://www.sciencedaily.com/rss/top.xml", # Corrected from https to http if needed, or use https if valid
            "Ars Technica": "http://feeds.arstechnica.com/arstechnica/index/"
        }
        print("NewsSkill initialized with default feeds.")

    def _clean_html(self, raw_html: str) -> str:
        """
        A simple HTML tag stripper.
        """
        if not raw_html:
            return ""
        cleanr = re.compile('<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});')
        cleantext = re.sub(cleanr, '', raw_html)
        return cleantext.strip()

    def _format_date(self, time_struct_or_str) -> str:
        """
        Formats a time_struct or an already formatted string into an ISO 8601 string.
        If input is already a string, returns it as is.
        """
        if isinstance(time_struct_or_str, str):
            return time_struct_or_str # Assume already formatted if string
        if not time_struct_or_str:
            return "Date not available"
        try:
            # Convert time_struct to timestamp, then to datetime object with UTC timezone
            dt_object = datetime.fromtimestamp(time.mktime(time_struct_or_str), tz=timezone.utc)
            return dt_object.isoformat()
        except Exception:
            # Fallback if time_struct is malformed or causes issues
            return "Date formatting error"

    def fetch_news(self, category: str = None, num_headlines: int = 5) -> list[dict] | None:
        """
        Fetches news headlines from RSS feeds.

        Args:
            category (str, optional): The category of news to fetch.
                                      If None or "all", fetches from all default feeds.
            num_headlines (int, optional): The total number of headlines desired. Defaults to 5.

        Returns:
            list[dict] | None: A list of headline dictionaries, or None if a major error occurs.
                                Returns an empty list if no headlines are found.
        """
        all_headlines = []
        feeds_to_fetch = {}

        if category and category in self.default_feed_urls:
            feeds_to_fetch[category] = self.default_feed_urls[category]
            headlines_per_feed = num_headlines # Get all requested headlines from this one feed
        elif not category or category.lower() == "all":
            feeds_to_fetch = self.default_feed_urls
            if not self.default_feed_urls: # Should not happen with current init
                print("NewsSkill Error: No default feed URLs configured.")
                return []
            # Distribute num_headlines among feeds, ensuring at least 1 if possible
            headlines_per_feed = max(1, num_headlines // len(self.default_feed_urls))
        else:
            print(f"NewsSkill Info: Category '{category}' not found. Defaulting to all categories.")
            feeds_to_fetch = self.default_feed_urls
            headlines_per_feed = max(1, num_headlines // len(self.default_feed_urls))
            category = "All Feeds" # For source_feed field

        print(f"NewsSkill: Fetching news for '{category if category else 'All Feeds'}' (target: {num_headlines} headlines, {headlines_per_feed} per feed)...")

        for feed_title, url in feeds_to_fetch.items():
            try:
                print(f"NewsSkill: Parsing feed '{feed_title}' from {url}...")
                parsed_feed = feedparser.parse(url)

                if parsed_feed.bozo: # Check for non-well-formed feed
                    bozo_exception_detail = parsed_feed.bozo_exception
                    print(f"NewsSkill Warning: Feed '{feed_title}' from {url} may be ill-formed. Details: {bozo_exception_detail}")
                    # Continue processing entries if any, as some might still be usable.

                if not parsed_feed.entries:
                    print(f"NewsSkill Info: No entries found in feed '{feed_title}' from {url}.")
                    continue

                for entry in parsed_feed.entries[:headlines_per_feed]: # Limit per feed before sorting
                    title = entry.get("title", "No title available")
                    link = entry.get("link", "#")

                    # Try 'published_parsed' first, then 'updated_parsed'
                    published_struct = entry.get("published_parsed", entry.get("updated_parsed"))
                    published_date_str = self._format_date(published_struct)

                    # Get summary, try 'summary' then 'description', clean HTML
                    summary_raw = entry.get("summary", entry.get("description", "No summary available."))
                    summary_clean = self._clean_html(summary_raw)

                    all_headlines.append({
                        "title": title,
                        "link": link,
                        "published_iso": published_date_str, # Store as ISO string for easier sorting/parsing later
                        "published_struct": published_struct, # Keep original for sorting if needed directly
                        "summary": summary_clean,
                        "source_feed": feed_title
                    })
            except Exception as e:
                print(f"NewsSkill Error: Failed to fetch or parse feed '{feed_title}' from {url}. Error: {e}")

        if not all_headlines:
            print("NewsSkill: No headlines collected from any feed.")
            return []

        # Sort all collected headlines by publication date (descending)
        # Use the time_struct for more reliable sorting if available
        all_headlines.sort(
            key=lambda x: time.mktime(x["published_struct"]) if x["published_struct"] else 0,
            reverse=True
        )

        # Remove the temporary struct used for sorting
        for headline in all_headlines:
            del headline["published_struct"]
            headline["published"] = headline.pop("published_iso") # Rename for final output

        return all_headlines[:num_headlines]


if __name__ == '__main__':
    print("\n--- Testing NewsSkill ---")
    skill = NewsSkill()

    print("\n--- Test 1: Fetch general news (default categories, default headlines) ---")
    general_news = skill.fetch_news(num_headlines=5)
    if general_news:
        print(f"Fetched {len(general_news)} general news headlines:")
        for i, item in enumerate(general_news):
            print(f"{i+1}. {item['title']} ({item['source_feed']}) - {item['published']}")
            print(f"   Link: {item['link']}")
            print(f"   Summary: {item['summary'][:100]}...\n")
    else:
        print("No general news fetched or an error occurred.")

    print("\n--- Test 2: Fetch 'Tech News' (3 headlines) ---")
    tech_news = skill.fetch_news(category="Tech News", num_headlines=3)
    if tech_news:
        print(f"Fetched {len(tech_news)} Tech News headlines:")
        for i, item in enumerate(tech_news):
            print(f"{i+1}. {item['title']} ({item['source_feed']}) - {item['published']}")
            print(f"   Link: {item['link']}")
            print(f"   Summary: {item['summary'][:100]}...\n")
    else:
        print("No Tech News fetched or an error occurred.")

    print("\n--- Test 3: Fetch news from a non-existent category ---")
    # This should default to fetching from all categories as per the logic
    non_existent_category_news = skill.fetch_news(category="NonExistentCategory", num_headlines=2)
    if non_existent_category_news:
        print(f"Fetched {len(non_existent_category_news)} headlines (should be from 'All Feeds' due to fallback):")
        for i, item in enumerate(non_existent_category_news):
            print(f"{i+1}. {item['title']} ({item['source_feed']}) - {item['published']}")
            print(f"   Link: {item['link']}\n")
    else:
        print("No news fetched for non-existent category or an error occurred (expected fallback to all).")

    print("\n--- Test 4: Fetch 'Science News' (1 headline) ---")
    science_news = skill.fetch_news(category="Science News", num_headlines=1)
    if science_news:
        print(f"Fetched {len(science_news)} Science News headlines:")
        for i, item in enumerate(science_news):
            print(f"{i+1}. {item['title']} ({item['source_feed']}) - {item['published']}")
            print(f"   Link: {item['link']}")
            print(f"   Summary: {item['summary'][:100]}...\n")
    else:
        print("No Science News fetched or an error occurred.")

    print("\nNewsSkill testing complete.")
