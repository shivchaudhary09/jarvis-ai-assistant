import pyaudio
import numpy as np
import time
from openwakeword.model import Model

# Model load karo (sirf "hey jarvis" wala)
try:
    oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    wake_word_error = None
except Exception as error:
    oww_model = None
    wake_word_error = error
    print(f"[Wake word unavailable: {error}]")

CHUNK = 1280  # openWakeWord ko 80ms chunks chahiye (16000Hz * 0.08s)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CONFIDENCE_THRESHOLD = 0.65  # zyada strict — echo/noise se false triggers kam

def listen_for_wake_word():
    """Continuously sunta hai jab tak 'Hey Jarvis' detect na ho."""
    if oww_model is None:
        print("[Wake word model unavailable. Model assets install/download karke /wake retry karo.]")
        return False

    audio = pyaudio.PyAudio()
    try:
        stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                            input=True, frames_per_buffer=CHUNK)
    except (OSError, IOError) as error:
        print(f"[Wake word microphone error: {error}]")
        audio.terminate()
        return False

    print("[Wake word ke liye sun raha hu... 'Hey Jarvis' bolo]")

    # Stream open hote hi kuch chunks discard karo — isse pichle
    # speak()/echo ka residual audio detection mein count nahi hota.
    try:
        for _ in range(6):
            stream.read(CHUNK, exception_on_overflow=False)
    except (OSError, IOError):
        pass

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)

            prediction = oww_model.predict(audio_data)

            for wake_word, score in prediction.items():
                if score > CONFIDENCE_THRESHOLD:
                    print(f"[Wake word detected: {wake_word} (confidence: {score:.2f})]")
                    try:
                        oww_model.reset()
                    except AttributeError:
                        pass
                    time.sleep(0.8)
                    return True

    except (KeyboardInterrupt, OSError, IOError) as error:
        if not isinstance(error, KeyboardInterrupt):
            print(f"[Wake word microphone error: {error}]")
        return False
    finally:
        try:
            stream.stop_stream()
            stream.close()
        finally:
            audio.terminate()