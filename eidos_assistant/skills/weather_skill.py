import os
import requests
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional # Ensure Any, List, Optional are imported for type hints

# Assuming base_skill.py is in the same directory or accessible via PYTHONPATH
try:
    from .base_skill import BaseSkill, ToolSignature, ToolParameter
except ImportError:
    # Fallback for environments where relative import fails (e.g. direct script execution)
    # This might happen if 'skills' is not treated as a package by the execution context.
    # For LLMEngine, skills_dir_path is added to sys.path, so direct `from base_skill import ...` should work there.
    # However, for `if __name__ == '__main__'` in this file, this fallback might be needed.
    print("WeatherSkill: Could not perform relative import of BaseSkill. Attempting direct import.")
    from base_skill import BaseSkill, ToolSignature, ToolParameter # type: ignore

class WeatherSkill(BaseSkill):
    def __init__(self):
        """
        Initializes the Weather Skill.
        Loads configuration from environment variables.
        """
        super().__init__() # Call BaseSkill's __init__

        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')

        if not load_dotenv(dotenv_path=dotenv_path):
            print(f"WeatherSkill Warning: Could not load .env file from {dotenv_path}. Relying on system environment variables.")

        self.api_key = os.getenv("OPENWEATHERMAP_API_KEY")
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

        if not self.api_key or self.api_key == "YOUR_OPENWEATHERMAP_API_KEY_HERE":
            print("WeatherSkill Warning: OPENWEATHERMAP_API_KEY is not set or is a placeholder. Weather functionality will be disabled.")
        else:
            print("WeatherSkill Initialized. API Key loaded.") # This is also printed by LLMEngine, consider removing one.

    def get_tool_signature(self) -> ToolSignature: # type: ignore # If ToolSignature is fallback Dict
        """
        Returns the tool signature for the WeatherSkill.
        """
        return {
            "tool_name": "get_weather", # Changed from weather_tool for simplicity
            "description": "Fetches the current weather for a specified city using OpenWeatherMap.",
            "parameters": [
                {
                    "name": "city",
                    "type": "string",
                    "description": "The name of the city for which to get the weather (e.g., 'London', 'New York').",
                    "required": True
                },
                {
                    "name": "units",
                    "type": "string",
                    "description": "Units for temperature and speed. 'metric' (Celsius, m/s) or 'imperial' (Fahrenheit, mph).",
                    "required": False # Defaults to 'metric' in the execute method
                }
            ]
        }

    def execute(self, action: Optional[str] = None, args: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Executes the weather fetching functionality.
        The 'action' parameter is ignored as this skill has one primary function.

        Args:
            action (Optional[str]): Ignored for this skill.
            args (Dict[str, Any]): A dictionary containing:
                'city' (str): The name of the city.
                'units' (str, optional): 'metric' or 'imperial'. Defaults to 'metric'.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing weather information, or None on error.
        """
        if args is None:
            args = {}

        city = args.get("city")
        units = args.get("units", "metric")

        if not city:
            print("WeatherSkill Error: 'city' argument is required.")
            # Returning a dict with error might be better for LLM to understand failure reason
            return {"error": "City not provided.", "message": "Please specify a city to get the weather."}


        if not self.api_key or self.api_key == "YOUR_OPENWEATHERMAP_API_KEY_HERE":
            print("WeatherSkill Error: API key not configured. Cannot fetch weather.")
            return {"error": "API key not configured.", "message": "The weather skill is not configured with an API key."}


        if units not in ["metric", "imperial"]:
            print(f"WeatherSkill Info: Invalid units '{units}' specified. Defaulting to 'metric'.")
            units = "metric"

        params = {
            "q": city,
            "appid": self.api_key,
            "units": units
        }

        try:
            print(f"WeatherSkill: Fetching weather for '{city}' with units '{units}' using execute method...")
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'weather' not in data or not data['weather'] or 'main' not in data or 'wind' not in data or 'sys' not in data:
                print(f"WeatherSkill Error: Received unexpected data structure from API for city '{city}'. Data: {data}")
                return {"error": "Unexpected API response structure.", "city": city}


            description = data['weather'][0]['description']
            temp = data['main']['temp']
            feels_like = data['main']['feels_like']
            humidity = data['main']['humidity']
            wind_speed = data['wind']['speed']
            city_name_from_api = data.get('name', city)
            country = data['sys'].get('country', 'N/A')

            weather_info = {
                "city": city_name_from_api,
                "country": country,
                "description": description,
                "temperature": temp,
                "feels_like": feels_like,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "units": units
            }
            print(f"WeatherSkill: Successfully retrieved weather for {city_name_from_api}, {country}.")
            return weather_info

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print("WeatherSkill Error: Unauthorized - Invalid API key.")
                return {"error": "Invalid API key.", "city": city}
            elif e.response.status_code == 404:
                print(f"WeatherSkill Error: City '{city}' not found.")
                return {"error": "City not found.", "city": city}
            else:
                print(f"WeatherSkill Error: HTTP error for '{city}': {e}")
                return {"error": f"HTTP error: {e.response.status_code}", "city": city}
        except requests.exceptions.Timeout:
            print(f"WeatherSkill Error: Timeout fetching weather for '{city}'.")
            return {"error": "Request timed out.", "city": city}
        except requests.exceptions.RequestException as e:
            print(f"WeatherSkill Error: Network error for '{city}': {e}")
            return {"error": f"Network error: {e}", "city": city}
        except (KeyError, TypeError, ValueError) as e:
            print(f"WeatherSkill Error: Error parsing data for '{city}': {e}")
            return {"error": "Error parsing weather data.", "city": city}
        except Exception as e:
            print(f"WeatherSkill Error: Unexpected error for '{city}': {e}")
            return {"error": f"An unexpected error occurred: {e}", "city": city}

if __name__ == '__main__':
    print("\n--- Testing WeatherSkill (Refactored) ---")
    skill = WeatherSkill()

    # Test get_tool_signature
    print("\n--- Tool Signature ---")
    signature = skill.get_tool_signature()
    import json
    print(json.dumps(signature, indent=2))

    if not skill.api_key or skill.api_key == "YOUR_OPENWEATHERMAP_API_KEY_HERE":
        print("\nWeatherSkill Test Warning: OPENWEATHERMAP_API_KEY is not set or is a placeholder.")
        print("Live API calls in tests will fail. Please configure .env for full testing.")
    else:
        print(f"\nAPI Key found: {skill.api_key[:4]}...{skill.api_key[-4:]}")

    def print_weather_result(data, city_name_for_title):
        print(f"\n--- Weather for {city_name_for_title} ---")
        if data and "error" not in data:
            temp_unit = "°C" if data.get('units') == "metric" else "°F"
            wind_unit = "m/s" if data.get('units') == "metric" else "mph"
            print(f"  City: {data.get('city', 'N/A')}, {data.get('country', 'N/A')}")
            print(f"  Description: {data.get('description', 'N/A')}")
            print(f"  Temperature: {data.get('temperature', 'N/A')}{temp_unit}")
            print(f"  Feels like: {data.get('feels_like', 'N/A')}{temp_unit}")
            print(f"  Humidity: {data.get('humidity', 'N/A')}%")
            print(f"  Wind speed: {data.get('wind_speed', 'N/A')} {wind_unit}")
        elif data and "error" in data:
            print(f"  Error: {data['error']}")
            if "message" in data: print(f"  Message: {data['message']}")
        else:
            print("  Failed to get weather or no data returned.")

    # Test execute method
    print("\n--- Test 1: London (metric) ---")
    args_london = {"city": "London", "units": "metric"}
    london_weather = skill.execute(args=args_london)
    print_weather_result(london_weather, "London")

    print("\n--- Test 2: Paris (imperial) ---")
    args_paris = {"city": "Paris", "units": "imperial"}
    paris_weather = skill.execute(args=args_paris)
    print_weather_result(paris_weather, "Paris")

    print("\n--- Test 3: Invalid City ---")
    args_invalid = {"city": "InvalidCityName123abc"} # Default units metric
    invalid_city_weather = skill.execute(args=args_invalid)
    print_weather_result(invalid_city_weather, "InvalidCityName123abc")
    if invalid_city_weather and invalid_city_weather.get("error") == "City not found.":
         print("  (Correctly handled invalid city)")


    print("\n--- Test 4: Missing city argument ---")
    args_missing_city = {"units": "metric"}
    missing_city_result = skill.execute(args=args_missing_city)
    print_weather_result(missing_city_result, "Missing City")
    if missing_city_result and missing_city_result.get("error") == "City not provided.":
        print("  (Correctly handled missing city argument)")

    print("\n--- Test 5: Invalid units (should default to metric) ---")
    args_invalid_units = {"city": "Berlin", "units": "kelvin_is_not_supported"}
    invalid_units_weather = skill.execute(args=args_invalid_units)
    print_weather_result(invalid_units_weather, "Berlin with invalid units")
    if invalid_units_weather and invalid_units_weather.get("units") == "metric":
        print("  (Correctly defaulted to metric units)")


    print("\nWeatherSkill refactored testing complete.")
