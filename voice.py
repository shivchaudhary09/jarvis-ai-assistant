import whisper
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import tempfile
import os
import subprocess

# Whisper model load karo (ek baar hi load hoga, thoda time lagega pehli baar)
print("[Voice module load ho raha hai...]")
whisper_model = whisper.load_model("base")

def listen(duration=5, samplerate=16000):
    """Microphone se audio record karke text mein convert karta hai."""
    print(f"[Sun raha hu... ({duration} seconds)]")

    # Set MIC_DEVICE in .env only if you want a specific microphone. It can be
    # its sounddevice index (for example: MIC_DEVICE=1) or its device name.
    microphone = os.getenv("MIC_DEVICE")
    if microphone and microphone.isdigit():
        microphone = int(microphone)
    if not microphone:
        microphone = None

    try:
        sd.check_input_settings(device=microphone, channels=1, samplerate=samplerate)
        audio = sd.rec(
            int(duration * samplerate),
            samplerate=samplerate,
            channels=1,
            dtype="float32",
            device=microphone,
        )
        sd.wait()
    except sd.PortAudioError as error:
        print("[Microphone unavailable. macOS Privacy settings mein Terminal/VS Code ko Microphone access do.]")
        print(f"[Audio error: {error}]")
        return ""

    peak_volume = float(np.max(np.abs(audio)))
    if peak_volume < 0.01:
        print("[Mic se audio nahi aa rahi. Sahi input device select karo aur Microphone permission allow karo.]")
        return ""

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        audio_path = tmp_file.name

    try:
        wav.write(audio_path, samplerate, audio)
        # Explicit FP32 removes Whisper's harmless FP16-on-CPU warning.
        result = whisper_model.transcribe(audio_path, language="hi", fp16=False)
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)

    text = result["text"].strip()
    print(f"[Tune bola: {text}]")
    return text

def speak(text):
    """Text ko poora bolke khatam hone ke baad hi return karta hai."""
    # macOS `say` synchronous hai: next listen cycle speech complete hone se
    # pehle start nahi hoga. pyttsx3 macOS par kabhi-kabhi jaldi return karta hai.
    subprocess.run(["say", "-r", "175", str(text)], check=False)
