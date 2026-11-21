# JARVIS - Local AI Voice Assistant

A voice assistant that runs on my own laptop. If one AI provider goes down, it automatically switches to another, so it keeps working.

## What it can do
- **Wake word:** say "Hey Jarvis" to activate (openWakeWord)
- **Speech-to-text:** Whisper
- **Smart AI router:** tries Groq first, falls back to local Ollama if it fails
- **PC automation:** create, rename and delete files and folders, with a safety confirmation before risky actions
- **Location aware:** uses GPS/IP location for local answers
- **Three modes:** text, continuous voice, wake-word
- **Visual feedback:** glowing orb overlay built with PyQt6
- **Memory:** remembers your preferences and past conversation

## How it works
Microphone -> Wake word -> Whisper (speech to text) -> AI Router (Groq, else Ollama) -> Automation / Reply -> Voice output

## Run it yourself
1. Clone the repo and create a virtual environment
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file and add your key: `GROQ_API_KEY=your_key_here`
4. (Optional) Install Ollama for the local fallback
5. Run: `python main.py`

Built for macOS (uses the system `say` voice).

## Tech stack
Python, Whisper, Groq API, Ollama, openWakeWord, PyQt6

## Why I built it
I wanted a personal assistant that I fully control, that works even when one service is down, and that I can keep extending with new skills.