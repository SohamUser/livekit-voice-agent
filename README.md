🌤️ LiveKit Weather Voice Assistant

A real-time, voice-interactive AI assistant that provides current weather and rain forecasts using WeatherAPI, powered by LiveKit Agents, multilingual VAD, TTS/STT, and a Next.js frontend.

Users speak naturally, and the assistant responds with helpful weather insights — all streamed live over WebRTC.

📑 Table of Contents

1.Overview <br/>
2.Features <br/>
3.Architecture <br/>
4.Tech Stack <br/>
5.Backend Setup (Agent Server) <br/>
6.How It Works <br/>
7.API Tools

🔍 Overview

This project is a voice-operated weather assistant built on LiveKit’s Agents framework.
Users speak commands like:

>“What’s the weather in Pune?” <br/>
>“Will it rain tomorrow in Bangalore?” <br/>
>“Is it going to rain on Friday in Pune?” <br/>

The system extracts locations and dates using simple NLP, calls WeatherAPI, and responds with TTS(Text to speech) in real time.

✨ Features

> Real-time voice communication using LiveKit <br/>
> Weather lookup via WeatherAPI <br/>
> Rain forecasting with smart day-offset handling <br/>
> Location extraction using regex-based NLP <br/>
> Wake-free turn detection (silero VAD + multilingual turn detector) <br/>
> Tools system (@function_tool) for LLM function calling <br/>
> Streaming STT (AssemblyAI) + TTS (Cartesia Sonic-3) <br/>
> Gemini 2.5 Flash LLM for conversational logic <br/>
> Next.js frontend provided by LiveKit starter kit <br/>

🏗 Architecture

Client (Next.js)
→ Connects to LiveKit room
→ Sends microphone audio
→ Plays assistant responses

LiveKit Agent Server
→ Listens to user transcripts
→ Extracts information (weather forecast)
→ Calls WeatherAPI via tools
→ Generates spoken response

WeatherAPI
→ Provides current conditions & forecast


🧰 Tech Stack

Backend (Agent Server):

1.Python <br/>
2.LiveKit Agents SDK <br/>
3.AssemblyAI STT <br/>
4.Cartesia Sonic TTS <br/>
5.Google Gemini 2.5 Flash LLM <br/>
6.WeatherAPI <br/>
7.Silero VAD <br/>
8.LiveKit Turn Detector (MultilingualModel)

Frontend:

1.Next.js (LiveKit starter kit) <br/>
2.Typescript <br/>
3.WebRTC audio through LiveKit Browser SDK

⚙ Backend Setup (Agent Server)

1.Clone this repository

2.Change the directory:
```bash
cd livekit-voice-agent
```

3.Setup Python Virtual Environment:

For mac:
```bash
python3 -m venv .venv
source .venv/bin/activate
```
For Windows:
```bash
python -m venv .venv
.venv\Scripts\activate
```

4.Install Dependencies:
```bash
uv pip install -r pyproject.toml
```
OR
```bash
pip install .
```
5.Set Environment by making .env.local file and paste your environment variables:
```bash
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
OPENWEATHER_API_KEY=
WEATHERAPI_KEY=
```
6.Run assistant:
```bash
python agent.py download-files
python agent.py dev
```

🧠 How It Works
1. STT Transcription
AssemblyAI streams text to the agent in real time.

2. Intent Detection
The agent listens for:
"weather" → calls getweather()
"rain" → calls getForecast()

3. NLP Extraction
Regex-based extractors pull:
Location names
Day offsets (today, tomorrow, weekdays)

4. API Tool Call
WeatherAPI endpoints:
current.json
forecast.json

5. LLM Response
Gemini 2.5 Flash composes a concise natural-language answer.

6. TTS
Cartesia Sonic-3 voice reads the response aloud.

🧩 API Tools

The agent exposes two function tools:

getweather(location: str)

Returns:

Condition,
Temperature,
Humidity,
Wind speed

getForecast(location: str, day: int)

Returns:

Will it rain? ,
Forecast summary ,
Chance of rain ,
Both hit WeatherAPI with proper error handling.