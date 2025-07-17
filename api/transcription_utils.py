import whisper
import json

model = whisper.load_model("base")

def transcribe_audio(audio_path):
    try:
        result = model.transcribe(audio_path)
        transcription = result.get("text", "").strip()
        return transcription
    except Exception as e:
        raise RuntimeError(f"Error transcribing audio: {str(e)}")

        
