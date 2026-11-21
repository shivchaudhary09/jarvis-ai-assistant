"""
JARVIS Voice Module
High-Definition Neural TTS (Edge-TTS) + Dynamic Voice Activity Detection (Silero VAD)
"""

import asyncio
import concurrent.futures
import os
import re
import subprocess
import tempfile
import time
from typing import Optional

import numpy as np
import pyaudio
import torch
import whisper

# Load Whisper base model from local cache
print("[JARVIS: Loading voice engine...]")
whisper_model = whisper.load_model("base")

# Load Silero VAD for real-time speech detection
try:
    import silero_vad
    vad_model = silero_vad.load_silero_vad()
    print("[JARVIS: Silero VAD engine active]")
except Exception as vad_err:
    vad_model = None
    print(f"[JARVIS: Silero VAD failed to initialize ({vad_err}); volume fallback active]")

SAMPLE_RATE = 16000
CHUNK_SIZE = 512  # 32ms at 16000Hz (optimal chunk size for Silero VAD)


def clean_text_for_speech(text: str) -> str:
    """Sanitize markdown symbols, code blocks, and URLs for natural speech delivery."""
    if not text:
        return ""
    # Replace code blocks with a brief spoken cue
    cleaned = re.sub(r"```[\s\S]*?```", " Please check the code on screen. ", text)
    # Inline code `...`
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    # Markdown links [text](url) -> text
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    # Raw URLs -> link
    cleaned = re.sub(r"https?://\S+", "link", cleaned)
    # Markdown formatting symbols (*, _, ~, #, >)
    cleaned = re.sub(r"[\*\_~#>]", "", cleaned)
    # Remove extra spaces before punctuation marks
    cleaned = re.sub(r"\s+([.,!?])", r"\1", cleaned)
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def has_devanagari(text: str) -> bool:
    """Detect if the text contains Hindi / Devanagari script."""
    return bool(re.search(r"[\u0900-\u097F]", text))


def _run_async_safely(coroutine, timeout: float = 15.0):
    """Safely execute an async coroutine from a synchronous thread context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coroutine).result(timeout=timeout)
    else:
        return asyncio.run(asyncio.wait_for(coroutine, timeout=timeout))


def _speak_neural(text: str) -> bool:
    """Generate high-fidelity neural audio via Edge-TTS and play using macOS afplay."""
    import edge_tts

    configured_voice = os.getenv("JARVIS_VOICE")
    if has_devanagari(text):
        voice = "hi-IN-MadhurNeural"
    elif configured_voice:
        voice = configured_voice
    else:
        # Iconic British JARVIS voice
        voice = "en-GB-RyanNeural"

    rate = os.getenv("JARVIS_VOICE_RATE", "+8%")

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        async def _generate():
            communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
            await communicate.save(tmp_path)

        _run_async_safely(_generate(), timeout=12.0)

        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
            subprocess.run(["afplay", tmp_path], check=True)
            return True
        return False
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _speak_macos_fallback(text: str):
    """macOS native say command fallback when offline or neural TTS is unavailable."""
    voice = "Lekha" if has_devanagari(text) else "Daniel"
    rate = os.getenv("MACOS_VOICE_RATE", "180")
    subprocess.run(["say", "-v", voice, "-r", rate, str(text)], check=False)


def speak(text: str):
    """
    Deliver spoken output:
    1. Attempts high-definition Edge Neural TTS first (British RyanNeural or Hindi MadhurNeural).
    2. Seamlessly falls back to native macOS 'say' (Daniel/Lekha) if offline.
    """
    speech_text = clean_text_for_speech(str(text))
    if not speech_text:
        return

    try:
        if _speak_neural(speech_text):
            return
    except Exception:
        pass

    _speak_macos_fallback(speech_text)


def listen(duration: int = 10, max_duration: int = 20, min_silence_duration_ms: int = 750, initial_timeout: float = 3.5) -> str:
    """
    Capture speech from microphone using real-time Silero VAD and in-memory Whisper:
    - Buffers audio dynamically once user starts speaking.
    - Concludes immediately after ~750ms of silence.
    - Times out quickly (3.5s) if no speech is detected.
    - Transcribes directly from memory without writing WAV to disk.
    """
    print("[Listening...]")

    microphone = os.getenv("MIC_DEVICE")
    device_index = int(microphone) if microphone and microphone.isdigit() else None

    audio = pyaudio.PyAudio()
    try:
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK_SIZE,
        )
    except (IOError, OSError) as error:
        print("[Microphone unavailable. Please grant Microphone access in macOS Privacy settings.]")
        print(f"[Audio error: {error}]")
        audio.terminate()
        return ""

    recorded_chunks = []
    is_speaking = False
    speech_frames = 0
    silence_frames = 0
    silence_threshold_frames = int((min_silence_duration_ms / 1000.0) / (CHUNK_SIZE / SAMPLE_RATE))
    initial_timeout_frames = int(initial_timeout / (CHUNK_SIZE / SAMPLE_RATE))
    max_frames = int(max_duration / (CHUNK_SIZE / SAMPLE_RATE))

    total_frames = 0

    try:
        while total_frames < max_frames:
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except (IOError, OSError):
                break

            total_frames += 1

            # Convert int16 PCM bytes to float32 normalized array
            chunk_np = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            peak_volume = float(np.max(np.abs(chunk_np)))

            # Speech presence check via Silero VAD + energy
            is_chunk_speech = False
            if vad_model is not None:
                try:
                    tensor_chunk = torch.from_numpy(chunk_np)
                    speech_prob = vad_model(tensor_chunk, SAMPLE_RATE).item()
                    is_chunk_speech = speech_prob > 0.45 or (speech_prob > 0.30 and peak_volume > 0.025)
                except Exception:
                    is_chunk_speech = peak_volume > 0.025
            else:
                is_chunk_speech = peak_volume > 0.025

            if is_chunk_speech:
                speech_frames += 1
                silence_frames = 0
                if speech_frames >= 2 and not is_speaking:
                    is_speaking = True
            else:
                if is_speaking:
                    silence_frames += 1

            if is_speaking:
                recorded_chunks.append(chunk_np)
                if silence_frames >= silence_threshold_frames:
                    # User stopped talking and silence threshold reached
                    break
            else:
                # Rolling 4-frame (~128ms) buffer so initial syllable is preserved
                recorded_chunks.append(chunk_np)
                if len(recorded_chunks) > 4:
                    recorded_chunks.pop(0)

                # Early exit if no voice detected within initial timeout
                if total_frames >= initial_timeout_frames:
                    break

    finally:
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        audio.terminate()

    if not is_speaking or not recorded_chunks:
        return ""

    # Combine recorded audio chunks
    audio_data = np.concatenate(recorded_chunks)
    duration_recorded = len(audio_data) / SAMPLE_RATE

    # Filter out accidental clicks/taps (< 0.4s)
    if duration_recorded < 0.4:
        return ""

    # Direct in-memory Whisper transcription
    try:
        lang_setting = os.getenv("VOICE_LANGUAGE")
        transcribe_args = {
            "fp16": False,
            "initial_prompt": "JARVIS personal AI assistant for Shiv Chaudhary. Natural Hinglish and English conversation.",
        }
        if lang_setting and lang_setting.lower() != "auto":
            transcribe_args["language"] = lang_setting

        result = whisper_model.transcribe(audio_data, **transcribe_args)
        text = result.get("text", "").strip()
    except Exception as trans_err:
        print(f"[Whisper transcription error: {trans_err}]")
        return ""

    if text:
        print(f"[Heard: {text}]")
    return text
