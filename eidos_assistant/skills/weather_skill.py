import os
import requests
from dotenv import load_dotenv

class WeatherSkill:
    def __init__(self):
        """
        Initializes the Weather Skill.
        Loads configuration from environment variables.
        """
        # Determine path to .env file (assuming it's in the project root: eidos_assistant/)
        # __file__ is eidos_assistant/skills/weather_skill.py
        # os.path.dirname(__file__) is eidos_assistant/skills/
        # os.path.dirname(os.path.dirname(__file__)) is eidos_assistant/
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')

        if not load_dotenv(dotenv_path=dotenv_path):
            print(f"WeatherSkill Warning: Could not load .env file from {dotenv_path}. Relying on system environment variables.")
        else:
            # This print is useful for confirming .env loading during standalone testing
            # print(f"WeatherSkill Debug: Attempted to load .env file from {dotenv_path}")
            pass

        self.api_key = os.getenv("OPENWEATHERMAP_API_KEY")
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

        if not self.api_key or self.api_key == "YOUR_OPENWEATHERMAP_API_KEY_HERE":
            print("WeatherSkill Warning: OPENWEATHERMAP_API_KEY is not set or is a placeholder.")
            print("Weather functionality will be disabled.")
        else:
            print("WeatherSkill Initialized. API Key loaded.")

    def get_current_weather(self, city: str, units: str = "metric") -> dict | None:
        """
        Retrieves the current weather for a specific city.

        Args:
            city (str): The name of the city.
            units (str, optional): Units for temperature and speed ('metric' or 'imperial').
                                   Defaults to "metric".

        Returns:
            dict | None: A dictionary containing weather information, or None on error.
        """
        if not self.api_key or self.api_key == "YOUR_OPENWEATHERMAP_API_KEY_HERE":
            print("WeatherSkill Error: API key not configured. Cannot fetch weather.")
            return None

        if units not in ["metric", "imperial"]:
            print(f"WeatherSkill Info: Invalid units '{units}' specified. Defaulting to 'metric'.")
            units = "metric"

        params = {
            "q": city,
            "appid": self.api_key,
            "units": units
        }

        try:
            print(f"WeatherSkill: Fetching weather for '{city}' with units '{units}'...")
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()  # Raises an HTTPError for bad responses (401, 404, 5xx)

            data = response.json()

            # Double-check the response structure, though raise_for_status should catch API errors
            if 'weather' not in data or not data['weather'] or 'main' not in data or 'wind' not in data or 'sys' not in data:
                print(f"WeatherSkill Error: Received unexpected data structure from API for city '{city}'. Data: {data}")
                return None

            description = data['weather'][0]['description']
            temp = data['main']['temp']
            feels_like = data['main']['feels_like']
            humidity = data['main']['humidity']
            wind_speed = data['wind']['speed']
            city_name = data.get('name', city) # Use API's city name if available
            country = data['sys'].get('country', 'N/A')

            weather_info = {
                "city": city_name,
                "country": country,
                "description": description,
                "temperature": temp,
                "feels_like": feels_like,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "units": units
            }
            print(f"WeatherSkill: Successfully retrieved weather for {city_name}, {country}.")
            return weather_info

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print(f"WeatherSkill Error: Unauthorized - Invalid API key. Please check your OPENWEATHERMAP_API_KEY.")
            elif e.response.status_code == 404:
                print(f"WeatherSkill Error: City '{city}' not found by OpenWeatherMap API.")
            else:
                print(f"WeatherSkill Error: HTTP error fetching weather for '{city}': {e}")
        except requests.exceptions.Timeout:
            print(f"WeatherSkill Error: Timeout fetching weather for '{city}'.")
        except requests.exceptions.RequestException as e:
            print(f"WeatherSkill Error: Network error fetching weather for '{city}': {e}")
        except (KeyError, TypeError, ValueError) as e: # ValueError for json decoding issues
            print(f"WeatherSkill Error: Error parsing weather data for '{city}': {e}")
        except Exception as e: # Catch-all for other unexpected errors
            print(f"WeatherSkill Error: An unexpected error occurred while fetching weather for '{city}': {e}")

        return None

if __name__ == '__main__':
    print("\n--- Testing WeatherSkill ---")

    # The __init__ method already attempts to load .env
    skill = WeatherSkill()

    if not skill.api_key or skill.api_key == "YOUR_OPENWEATHERMAP_API_KEY_HERE":
        print("\nWeatherSkill Test Error: OPENWEATHERMAP_API_KEY is not set in your .env file or is a placeholder.")
        print("Please obtain a key from https://openweathermap.org/appid and add it to .env to run these tests.")
        print("Example: OPENWEATHERMAP_API_KEY=\"your_actual_api_key\"")
    else:
        print(f"\nTesting with API Key: {skill.api_key[:4]}...{skill.api_key[-4:]}") # Show partial key for confirmation

        print("\n--- Test 1: Get weather for London (metric) ---")
        london_weather = skill.get_current_weather("London")
        if london_weather:
            print(f"London Weather (Metric):")
            for key, value in london_weather.items():
                print(f"  {key.replace('_', ' ').capitalize()}: {value}")
        else:
            print("Failed to get weather for London.")

        print("\n--- Test 2: Get weather for Paris (imperial) ---")
        paris_weather = skill.get_current_weather("Paris", units="imperial")
        if paris_weather:
            print(f"Paris Weather (Imperial):")
            temp_unit = "°F" if paris_weather['units'] == "imperial" else "°C"
            wind_unit = "mph" if paris_weather['units'] == "imperial" else "m/s"
            print(f"  City: {paris_weather['city']}, {paris_weather['country']}")
            print(f"  Description: {paris_weather['description']}")
            print(f"  Temperature: {paris_weather['temperature']}{temp_unit}")
            print(f"  Feels like: {paris_weather['feels_like']}{temp_unit}")
            print(f"  Humidity: {paris_weather['humidity']}%")
            print(f"  Wind speed: {paris_weather['wind_speed']} {wind_unit}")
        else:
            print("Failed to get weather for Paris.")

        print("\n--- Test 3: Get weather for an invalid city ---")
        invalid_city_weather = skill.get_current_weather("InvalidCityName123abc")
        if invalid_city_weather is None:
            print("Correctly failed to get weather for 'InvalidCityName123abc' (expected behavior).")
        else:
            print(f"Unexpectedly got weather for invalid city: {invalid_city_weather}")

        print("\n--- Test 4: Get weather with invalid units ---")
        # The skill should default to metric and give a notice.
        berlin_weather = skill.get_current_weather("Berlin", units="celsius_bad_unit")
        if berlin_weather:
            print(f"Berlin Weather (should be Metric):")
            for key, value in berlin_weather.items():
                print(f"  {key.replace('_', ' ').capitalize()}: {value}")
            assert berlin_weather['units'] == 'metric', "Unit did not default to metric correctly"
        else:
            print("Failed to get weather for Berlin even with unit defaulting.")

    print("\nWeatherSkill testing complete.")
