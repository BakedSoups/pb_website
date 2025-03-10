from openai import OpenAI
import ffmpeg
import io
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("No OpenAI API key found. Please set the OPENAI_API_KEY environment variable.")

client = OpenAI(api_key=api_key)

def remove_silence(input_path):
    """
    Removes silence from an audio file.
    
    Args:
        input_path (str): Path to the input audio file
        
    Returns:
        io.BytesIO: Memory buffer containing the processed audio
    """
    output_stream = io.BytesIO()

    process = (
        ffmpeg
        .input(input_path)
        .output("pipe:1", format="mp3", acodec="libmp3lame", af="silenceremove=1:0:-50dB")
        .run(capture_stdout=True, capture_stderr=True)
    )

    output_stream.write(process[0])
    output_stream.seek(0)

    return output_stream

def preprocess_audio(input_audio, speed=1.5):
    """
    Preprocesses audio by adjusting speed and converting to mono 16kHz.
    
    Args:
        input_audio (io.BytesIO): Memory buffer containing input audio
        speed (float): Speed factor for the audio (1.0 is normal speed)
        
    Returns:
        io.BytesIO: Memory buffer containing the processed audio
    """
    output_stream = io.BytesIO()

    process = (
        ffmpeg
        .input("pipe:0")
        .output("pipe:1", format="mp3", acodec="libmp3lame", ac=1, ar="16000", af=f"atempo={speed}")
        .run(input=input_audio.read(), capture_stdout=True, capture_stderr=True)
    )

    output_stream.write(process[0])
    output_stream.seek(0)

    return output_stream

def transcribe_audio(audio_file):
    """
    Transcribe audio using OpenAI's Whisper model.
    
    Args:
        audio_file: File-like object or path to audio file
        
    Returns:
        str: Transcribed text
    """
    response = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file
    )
    
    return response.text

def process_audio(file_path=None):
    """
    Process audio file by removing silence and adjusting speed.
    If file_path is provided, process that file.
    Otherwise, process the default test file.
    
    Args:
        file_path (str, optional): Path to input audio file
        
    Returns:
        str: Transcribed text
    """
    if file_path is None:
        # Use default test file if no file path provided
        file_path = "audio/not-today-satan.mp3"
    
    processed_audio = remove_silence(file_path)
    processed_audio = preprocess_audio(processed_audio, speed=1.5)
    
    response = client.audio.transcriptions.create(
        model="whisper-1",
        file=("processed.mp3", processed_audio, "audio/mpeg")
    )

    return response.text

if __name__ == "__main__":
    print(process_audio())