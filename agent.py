import re
import asyncio
from dotenv import load_dotenv
import os

from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, room_io, function_tool
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# load the env file
load_dotenv(".env.local")

WEATHERAPI_KEY = os.getenv("WEATHERAPI_KEY")

@function_tool
async def getweather(location: str) -> str:
    """
    Return current weather from WeatherAPI for a city.
    Uses: http://api.weatherapi.com/v1/current.json?key=KEY&q=LOCATION
    """
    import requests, os
    key = os.getenv("WEATHERAPI_KEY")
    if not key:
        return "WeatherAPI key is missing"

    url = "http://api.weatherapi.com/v1/current.json"
    params = {"key": key, "q": location}
    try:
        res = requests.get(url, params=params, timeout=10)
        print("getweather request url:", res.url)
        res.raise_for_status()
        data = res.json()

        loc_name = data.get("location", {}).get("name", location)
        region = data.get("location", {}).get("region", "")
        temp_c = data["current"]["temp_c"]
        cond = data["current"]["condition"]["text"]
        humidity = data["current"].get("humidity")
        wind_kph = data["current"].get("wind_kph")

        region_text = f", {region}" if region else ""
        return (
            f"The weather in {loc_name}{region_text} is {cond} with a temperature of {temp_c}°C. "
            f"Humidity {humidity}%. Wind {wind_kph} kph."
        )
    except Exception as e:
        print("getweather error:", e, getattr(e, "response", None))
        return f"Sorry, I couldn't get the weather for {location}."

@function_tool
async def getForecast(location: str, day: int) -> str:
    """
    Check if it will rain in the given location in `day` days using WeatherAPI forecast.
    day=0 -> today, day=1 -> tomorrow.
    Uses: http://api.weatherapi.com/v1/forecast.json?key=KEY&q=LOCATION&days=N
    """
    import requests, os
    key = os.getenv("WEATHERAPI_KEY")
    if not key:
        return "WeatherAPI key is missing"

    # WeatherAPI to get forecast for upcoming days
    days_required = max(1, day + 1)
    url = "http://api.weatherapi.com/v1/forecast.json"
    params = {"key": key, "q": location, "days": days_required}

    try:
        res = requests.get(url, params=params, timeout=10)
        print("getForecast request url:", res.url)
        res.raise_for_status()
        data = res.json()

        forecast_days = data.get("forecast", {}).get("forecastday", [])
        if not forecast_days or day >= len(forecast_days):
            return f"Sorry, I don't have forecast data that far ahead for {location}."

        target = forecast_days[day]["day"]
        # - "daily_will_it_rain": 0 or 1
        # - "daily_chance_of_rain": "0"-"100" (string) in some responses
        will_it_rain_flag = target.get("daily_will_it_rain")
        chance_str = target.get("daily_chance_of_rain")
        chance = None
        if chance_str is not None:
            try:
                chance = int(chance_str)
            except Exception:
                try:
                    chance = int(float(chance_str))
                except Exception:
                    chance = None

        condition = target.get("condition", {}).get("text", "no data")
        day_label = "today" if day == 0 else ("tomorrow" if day == 1 else f"in {day} days")

        # decide final answer
        if will_it_rain_flag == 1 or (chance is not None and chance >= 30):
            chance_text = f" Chance of rain: {chance}%." if chance is not None else ""
            return f"Yes, it looks like it will rain in {location} {day_label}. Forecast: {condition}.{chance_text}"
        else:
            chance_text = f" Chance of rain: {chance}%." if chance is not None else ""
            return f"No, it doesn't look like it will rain in {location} {day_label}. Forecast: {condition}.{chance_text}"

    except requests.exceptions.HTTPError as http_err:
        print("getForecast HTTP error:", http_err, res.text if 'res' in locals() else None)
        if 'res' in locals() and res.status_code == 400:
            return f"Bad request for location {location}."
        if 'res' in locals() and res.status_code == 401:
            return "Unauthorized: check your WeatherAPI key."
        return f"Sorry, I couldn't get the forecast for {location}."
    except Exception as e:
        print("getForecast error:", e)
        return f"Sorry, I could not retrieve the rain forecast for {location}."

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a helpful voice AI assistant.
            You eagerly assist users with their questions by providing information from your extensive knowledge.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You are curious, friendly, and have a sense of humor.""",
            tools=[getweather, getForecast],
        )

server = AgentServer()

@server.rtc_session()
async def my_agent(ctx: agents.JobContext):
    session = AgentSession(
        stt="assemblyai/universal-streaming:en",
        llm="google/gemini-2.5-flash",
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony()
                if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                else noise_cancellation.BVC(),
            ),
        ),
    )

    # --- Simple regex extractor for location and forecast info (weather / rain / tomorrow) ---
    def extract_location_from_text(text: str) -> str | None:
        patterns = [
            r'weather\s+(?:in|for|at)\s+([A-Za-z\s,]+)',
            r'what(?:\'s| is) the weather in\s+([A-Za-z\s,]+)',
            r'will it rain (?:in|at)\s+([A-Za-z\s,]+)',
            r'rain in\s+([A-Za-z\s,]+)',
            r'in\s+([A-Za-z\s,]+)\s+(?:tomorrow|today|on)',
        ]
        for p in patterns:
            m = re.search(p, text, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip().strip('.,?!')
        m = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
        if m:
            return m[-1]
        return None

    # --- Extraction of day (today ,tomorrow etc.) or weekdays ---
    def extract_day_offset(text: str) -> int:
        text_l = text.lower()
        if "today" in text_l:
            return 0
        if "tomorrow" in text_l:
            return 1
        weekdays = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
        for i, wd in enumerate(weekdays):
            if wd in text_l:
                from datetime import datetime, timedelta
                today_idx = datetime.utcnow().weekday()
                target_idx = i
                delta = (target_idx - today_idx) % 7
                if delta == 0:
                    delta = 7
                return delta
        return 1

    # Callback that runs whenever a transcript (speech-to-text result) arrives

    async def on_transcript_event(transcript):

        # Safely extract text from different possible transcript formats
        text = getattr(transcript, "text", None) or getattr(transcript, "transcript", None) or transcript
        if not text:
            return
        text_l = text.lower()

        # RAIN FORECAST INTENT HANDLING
        if "rain" in text_l:
            location = extract_location_from_text(text) or "your location"
            day = extract_day_offset(text)
            reply = await getForecast(location, day)
            try:
                await session.send_assistant_message(reply)
            except Exception:
                try:
                    await session.generate_reply(instructions=reply)
                except Exception:
                    print("Failed to send getForecast reply:", reply)
            return

        # WEATHER INTENT HANDLING
        if "weather" in text_l:

            # Extract location from the spoken text
            location = extract_location_from_text(text) or "your location"
            reply = await getweather(location)

            # Try sending the assistant response
            try:
                await session.send_assistant_message(reply)
            except Exception:
                try:
                    await session.generate_reply(instructions=reply)
                except Exception:
                    print("Failed to send getweather reply:", reply)
            return

    # Attaching transcript listeners
    attached = False

    # method 1: using session.on()
    try:
        session.on("transcript", on_transcript_event)
        attached = True
    except Exception:
        pass
    
    # method 2: using add_transcript_listener()
    if not attached:
        try:
            session.add_transcript_listener(on_transcript_event)
            attached = True
        except Exception:
            pass

    # method 3: manually polling
    if not attached:
        async def poller():
            while True:
                try:
                    evt = await session.receive()
                except Exception:
                    await asyncio.sleep(0.2)
                    continue
                text = None

                 # Extract text from event
                if isinstance(evt, dict):
                    text = evt.get("text") or evt.get("transcript")
                else:
                    text = getattr(evt, "text", None) or getattr(evt, "transcript", None)

                # If transcript contains weather related words, handle it
                if text:
                    if "weather" in text.lower() or "rain" in text.lower():
                        await on_transcript_event(text)
                
        # Run poller in background
        asyncio.create_task(poller())

    # initial greeting
    await session.generate_reply(instructions="Greet the user and offer your assistance.")

    # keep alive while room is open
    try:
        await ctx.wait_until_closed()
    except Exception:
        while not getattr(ctx.room, "is_closed", lambda: False)():
            await asyncio.sleep(1)

if __name__ == "__main__":
    # print("WEATHERAPI_KEY :", os.getenv("WEATHERAPI_KEY") is not None)
    agents.cli.run_app(server)
