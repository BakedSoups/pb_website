from openai import OpenAI
import ffmpeg
import io
import os
import tempfile
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API key from environment
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("No OpenAI API key found. Please set the OPENAI_API_KEY environment variable.")

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

# OpenAI API file size limit (25MB)
OPENAI_FILE_SIZE_LIMIT = 25 * 1024 * 1024

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

def compress_audio_file(input_path, output_path=None, bitrate="64k"):
    """
    Compress audio file to reduce file size.
    
    Args:
        input_path (str): Path to the input audio file
        output_path (str, optional): Path for the output file. If None, a temp file is created.
        bitrate (str): Target bitrate for compression (lower = smaller file)
        
    Returns:
        str: Path to the compressed audio file
    """
    try:
        from pydub import AudioSegment
        
        # If no output path is provided, create a temporary one
        if output_path is None:
            temp_dir = os.path.dirname(input_path)
            output_path = os.path.join(temp_dir, f"compressed_{os.path.basename(input_path)}")
        
        # Load the audio and convert to mono
        audio = AudioSegment.from_file(input_path)
        audio = audio.set_channels(1)  # Convert to mono
        
        # Export with compression
        audio.export(output_path, format="mp3", bitrate=bitrate)
        
        # Log compression stats
        original_size = os.path.getsize(input_path)
        compressed_size = os.path.getsize(output_path)
        print(f"Compressed audio from {original_size/1024/1024:.2f}MB to {compressed_size/1024/1024:.2f}MB")
        
        return output_path
    except Exception as e:
        print(f"Error compressing audio: {str(e)}")
        # Return original file if compression fails
        return input_path

def transcribe_audio(audio_file):
    """
    Transcribe audio using OpenAI's Whisper model.
    Handles file size limits by compressing if needed.
    
    Args:
        audio_file: File-like object or path to audio file
        
    Returns:
        str: Transcribed text
    """
    temp_file = None
    try:
        # If audio_file is a string (file path)
        if isinstance(audio_file, str):
            file_path = audio_file
            file_size = os.path.getsize(file_path)
            
            # If file is too large, compress it
            if file_size > OPENAI_FILE_SIZE_LIMIT:
                print(f"File size ({file_size/1024/1024:.2f}MB) exceeds OpenAI limit. Compressing...")
                
                try:
                    # Import pydub for audio processing
                    from pydub import AudioSegment
                    
                    # Load audio
                    audio = AudioSegment.from_file(file_path)
                    
                    # Create temp file
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                    temp_path = temp_file.name
                    temp_file.close()
                    
                    # Convert to mono & export at lower bitrate
                    audio = audio.set_channels(1)
                    audio.export(temp_path, format="mp3", bitrate="64k")
                    
                    # Check if compression was enough
                    compressed_size = os.path.getsize(temp_path)
                    if compressed_size <= OPENAI_FILE_SIZE_LIMIT:
                        print(f"Successfully compressed to {compressed_size/1024/1024:.2f}MB")
                        # Use the compressed file
                        with open(temp_path, 'rb') as f:
                            response = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=f
                            )
                        return response.text
                    else:
                        # Try more aggressive compression
                        audio.export(temp_path, format="mp3", bitrate="32k")
                        compressed_size = os.path.getsize(temp_path)
                        
                        if compressed_size <= OPENAI_FILE_SIZE_LIMIT:
                            print(f"Successfully compressed to {compressed_size/1024/1024:.2f}MB with aggressive compression")
                            with open(temp_path, 'rb') as f:
                                response = client.audio.transcriptions.create(
                                    model="whisper-1",
                                    file=f
                                )
                            return response.text
                        else:
                            # If still too large, try processing in chunks
                            try:
                                return transcribe_large_audio(file_path)
                            except Exception as chunk_error:
                                print(f"Error processing in chunks: {str(chunk_error)}")
                                return "Audio file too large. Even after compression, it exceeds the OpenAI API's 25MB limit."
                
                except ImportError:
                    return "Audio file too large and pydub library is not available for compression."
                except Exception as e:
                    print(f"Error compressing audio: {str(e)}")
                    return f"Error compressing audio: {str(e)}"
            
            # If file is within size limit, proceed normally
            with open(file_path, 'rb') as f:
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                )
            return response.text
        
        # If audio_file is a file-like object
        else:
            # For file-like objects, we need to save to temp file to check size
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            temp_path = temp_file.name
            
            # If it's a BytesIO, get the content
            if hasattr(audio_file, 'read'):
                audio_file.seek(0)
                temp_file.write(audio_file.read())
                temp_file.close()
            
            # Check size
            file_size = os.path.getsize(temp_path)
            if file_size > OPENAI_FILE_SIZE_LIMIT:
                # Handle same as above with compression
                try:
                    from pydub import AudioSegment
                    audio = AudioSegment.from_file(temp_path)
                    audio = audio.set_channels(1)
                    audio.export(temp_path, format="mp3", bitrate="64k")
                    
                    if os.path.getsize(temp_path) <= OPENAI_FILE_SIZE_LIMIT:
                        with open(temp_path, 'rb') as f:
                            response = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=f
                            )
                        return response.text
                    else:
                        # Try more aggressive compression
                        audio.export(temp_path, format="mp3", bitrate="32k")
                        if os.path.getsize(temp_path) <= OPENAI_FILE_SIZE_LIMIT:
                            with open(temp_path, 'rb') as f:
                                response = client.audio.transcriptions.create(
                                    model="whisper-1",
                                    file=f
                                )
                            return response.text
                        else:
                            return "Audio file too large even after compression."
                except Exception as e:
                    return f"Error compressing audio: {str(e)}"
            
            # If within size limit
            with open(temp_path, 'rb') as f:
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                )
            return response.text
    
    except Exception as e:
        print(f"Error transcribing audio: {str(e)}")
        return f"Error transcribing audio: {str(e)}"
    
    finally:
        # Clean up temp file
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except:
                pass

def transcribe_large_audio(file_path, chunk_duration_seconds=300):
    """
    Transcribe large audio files by splitting into chunks.
    
    Args:
        file_path (str): Path to the audio file
        chunk_duration_seconds (int): Duration of each chunk in seconds
        
    Returns:
        str: Complete transcription
    """
    try:
        from pydub import AudioSegment
        
        print(f"Processing large audio file: {file_path}")
        
        # Load the audio file
        audio = AudioSegment.from_file(file_path)
        
        # Calculate total duration
        total_duration_ms = len(audio)
        total_duration_sec = total_duration_ms / 1000
        
        print(f"Audio duration: {total_duration_sec:.2f} seconds")
        
        # If file is short enough, process directly
        if total_duration_sec <= chunk_duration_seconds:
            print("Audio is short enough to process directly")
            # But we know it's too large, so compress heavily
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            temp_path = temp_file.name
            temp_file.close()
            
            audio = audio.set_channels(1)
            audio.export(temp_path, format="mp3", bitrate="32k")
            
            if os.path.getsize(temp_path) <= OPENAI_FILE_SIZE_LIMIT:
                with open(temp_path, 'rb') as f:
                    response = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f
                    )
                os.unlink(temp_path)
                return response.text
            else:
                os.unlink(temp_path)
                raise ValueError("File still too large after compression")
        
        # Otherwise, split into chunks
        chunk_ms = chunk_duration_seconds * 1000
        num_chunks = (total_duration_ms + chunk_ms - 1) // chunk_ms  # Ceiling division
        
        print(f"Splitting audio into {num_chunks} chunks of {chunk_duration_seconds} seconds each")
        
        transcriptions = []
        
        for i in range(int(num_chunks)):
            start_ms = i * chunk_ms
            end_ms = min((i + 1) * chunk_ms, total_duration_ms)
            
            print(f"Processing chunk {i+1}/{num_chunks}: {start_ms/1000:.1f}s - {end_ms/1000:.1f}s")
            
            # Extract chunk
            chunk = audio[start_ms:end_ms]
            
            # Save chunk to temporary file
            chunk_path = tempfile.mktemp(suffix='.mp3')
            chunk = chunk.set_channels(1)  # Convert to mono
            chunk.export(chunk_path, format="mp3", bitrate="64k")
            
            # Check size and compress further if needed
            chunk_size = os.path.getsize(chunk_path)
            if chunk_size > OPENAI_FILE_SIZE_LIMIT:
                print(f"Chunk {i+1} too large ({chunk_size/1024/1024:.2f}MB), compressing further")
                chunk.export(chunk_path, format="mp3", bitrate="32k")
                chunk_size = os.path.getsize(chunk_path)
                
                if chunk_size > OPENAI_FILE_SIZE_LIMIT:
                    print(f"Chunk {i+1} still too large ({chunk_size/1024/1024:.2f}MB), trying extreme compression")
                    chunk.export(chunk_path, format="mp3", bitrate="16k")
                    chunk_size = os.path.getsize(chunk_path)
                    
                    if chunk_size > OPENAI_FILE_SIZE_LIMIT:
                        print(f"Chunk {i+1} cannot be compressed enough, skipping")
                        os.remove(chunk_path)
                        transcriptions.append(f"[Audio chunk {i+1} could not be transcribed due to size limitations]")
                        continue
            
            # Transcribe chunk
            try:
                with open(chunk_path, 'rb') as chunk_file:
                    chunk_response = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=chunk_file
                    )
                chunk_transcript = chunk_response.text
                transcriptions.append(chunk_transcript)
                print(f"Chunk {i+1} transcribed successfully")
            except Exception as e:
                print(f"Error transcribing chunk {i+1}: {str(e)}")
                transcriptions.append(f"[Error transcribing chunk {i+1}: {str(e)}]")
            
            # Clean up chunk file
            os.remove(chunk_path)
        
        # Combine all transcriptions
        full_transcript = " ".join(transcriptions)
        print(f"Successfully transcribed {num_chunks} chunks")
        
        return full_transcript
    
    except Exception as e:
        print(f"Error in transcribe_large_audio: {str(e)}")
        raise

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
    
    # Check file size
    file_size = os.path.getsize(file_path)
    if file_size > OPENAI_FILE_SIZE_LIMIT * 2:  # If file is more than twice the API limit
        # For very large files, try chunking directly
        try:
            return transcribe_large_audio(file_path)
        except Exception as e:
            print(f"Error with chunked processing: {str(e)}")
            # Fall back to regular processing
            pass
    
    # For smaller files or if chunking failed, use the regular processing
    processed_audio = remove_silence(file_path)
    processed_audio = preprocess_audio(processed_audio, speed=1.5)
    
    # Check size of processed audio
    processed_size = len(processed_audio.getvalue())
    if processed_size > OPENAI_FILE_SIZE_LIMIT:
        print(f"Processed audio too large ({processed_size/1024/1024:.2f}MB), trying direct transcription")
        return transcribe_audio(file_path)
    
    # Create a temporary file from the processed audio
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_processed:
        temp_processed.write(processed_audio.getvalue())
        processed_filepath = temp_processed.name
    
    # Transcribe the processed audio
    try:
        with open(processed_filepath, 'rb') as audio_file:
            transcript = transcribe_audio(audio_file)
        
        # Clean up temporary file
        os.remove(processed_filepath)
        
        return transcript
    except Exception as e:
        # If transcription fails, clean up and re-raise
        if os.path.exists(processed_filepath):
            os.remove(processed_filepath)
        raise e

if __name__ == "__main__":
    print(process_audio())