from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import tempfile
import io
import time
import logging
from logging.handlers import RotatingFileHandler
import traceback
import json
import threading
import uuid
import math
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import your existing functions
from transcriber import remove_silence, preprocess_audio, transcribe_audio
from manage_audio import summarize_text, question
import db_manager as db

app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for all routes

# Configure max content length (1GB)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB in bytes

# Configure upload folder
UPLOAD_FOLDER = 'temp_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Set up logging
if not os.path.exists('logs'):
    os.makedirs('logs')

file_handler = RotatingFileHandler('logs/app.log', maxBytes=10485760, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Application startup')

# Dictionary to track background jobs
# In a production environment, this should be stored in a database
background_jobs = {}

# Initialize database
db.init_db()

@app.errorhandler(413)
def request_entity_too_large(error):
    app.logger.error('File too large: %s', request.url)
    return jsonify(error="The file is too large to upload. Maximum allowed size is 1GB."), 413

def trim_audio_if_needed(file_path, max_seconds=1800):
    """
    Trim audio file to specified length if needed.
    
    Args:
        file_path (str): Path to the input audio file
        max_seconds (int): Maximum duration in seconds
        
    Returns:
        str: Path to the trimmed file, or original file if trimming not needed
    """
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(file_path)
        
        # Calculate duration in seconds
        duration_seconds = len(audio) / 1000
        app.logger.info(f"Audio duration: {duration_seconds:.2f} seconds")
        
        # If duration exceeds max_seconds, trim it
        if duration_seconds > max_seconds:
            app.logger.info(f"Trimming audio to {max_seconds} seconds")
            trimmed_audio = audio[:max_seconds * 1000]
            
            # Generate trimmed filename
            trimmed_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"trimmed_{os.path.basename(file_path)}")
            
            # Export trimmed audio
            trimmed_audio.export(trimmed_filepath, format="mp3")
            
            return trimmed_filepath
        else:
            app.logger.info("Audio duration is within limits, no trimming needed")
            return file_path
    except Exception as e:
        app.logger.error(f"Error trimming audio: {str(e)}")
        app.logger.error(traceback.format_exc())
        return file_path  # Return original path if trimming fails

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transcribe', methods=['POST'])
def transcribe_audio_route():
    start_time = time.time()
    
    # Add request size logging
    content_length = request.content_length
    app.logger.info(f"Received request with content length: {content_length} bytes")
    
    if 'file' not in request.files:
        app.logger.warning("No file part in request")
        db.log_api_request('/api/transcribe', 'POST', 400, 'No file part', 0, 0)
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        app.logger.warning("No selected file")
        db.log_api_request('/api/transcribe', 'POST', 400, 'No selected file', 0, 0)
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        # Save the uploaded file temporarily
        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(temp_filepath)
        file_size = os.path.getsize(temp_filepath)
        file_size_mb = file_size / (1024 * 1024)
        
        # Log the file size for debugging
        app.logger.info(f"Processing file: {file.filename}, Size: {file_size_mb:.2f} MB")
        
        # Check if we should trim the audio
        trim_duration = request.form.get('trim_duration')
        if trim_duration:
            try:
                trim_seconds = int(trim_duration)
                app.logger.info(f"Trim duration specified: {trim_seconds} seconds")
                temp_filepath = trim_audio_if_needed(temp_filepath, trim_seconds)
            except Exception as e:
                app.logger.error(f"Error processing trim request: {str(e)}")
        
        try:
            # For large files (>20MB), skip preprocessing to avoid memory issues
            if file_size_mb > 20:
                app.logger.info(f"Large file detected ({file_size_mb:.2f} MB), skipping preprocessing")
                # Just transcribe directly without preprocessing
                with open(temp_filepath, 'rb') as audio_file:
                    transcript = transcribe_audio(audio_file)
            else:
                # Normal processing for smaller files
                app.logger.info("Standard file size, using normal processing")
                processed_audio = remove_silence(temp_filepath)
                processed_audio = preprocess_audio(processed_audio, speed=1.5)
                
                # Create a temporary file for the processed audio
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_processed:
                    temp_processed.write(processed_audio.getvalue())
                    processed_filepath = temp_processed.name
                
                # Transcribe the processed audio
                with open(processed_filepath, 'rb') as audio_file:
                    transcript = transcribe_audio(audio_file)
                
                # Clean up processed audio file
                os.remove(processed_filepath)
            
            # Clean up temporary file
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            
            # Save transcription to database
            transcription_id = db.save_transcription(
                filename=secure_filename(file.filename),
                file_size=file_size,
                transcript=transcript
            )
            
            # Calculate processing time
            processing_time = time.time() - start_time
            app.logger.info(f"Transcription completed in {processing_time:.2f} seconds")
            
            # Prepare response data
            app.logger.info(f"Sending response with transcript length: {len(transcript)}")
            response_data = {'transcript': transcript, 'transcription_id': transcription_id}
            
            # Test JSON serialization to catch issues early
            try:
                json.dumps(response_data)
                
                # Log API request
                db.log_api_request(
                    '/api/transcribe',
                    'POST',
                    200,
                    {'filename': file.filename, 'file_size': file_size},
                    len(transcript),
                    processing_time
                )
                
                return jsonify(response_data), 200
            except Exception as json_error:
                app.logger.error(f"JSON serialization error: {str(json_error)}")
                # Return a simplified response instead
                return jsonify({
                    'transcript': "Transcription successful but too large to return via API. Please check the database.",
                    'transcription_id': transcription_id,
                    'error': "The transcript was too large to serialize to JSON."
                }), 200
            
        except Exception as e:
            # Detailed error logging
            app.logger.error(f"Error processing file {file.filename}: {str(e)}")
            app.logger.error(traceback.format_exc())
            
            # Clean up temporary file if it exists
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            
            # Log error
            processing_time = time.time() - start_time
            error_type = type(e).__name__
            error_message = str(e)
            
            db.log_api_request(
                '/api/transcribe',
                'POST',
                500,
                {'filename': file.filename, 'error': error_message, 'error_type': error_type},
                0,
                processing_time
            )
            
            return jsonify({'error': error_message, 'error_type': error_type}), 500

def process_large_file_in_background(file_path, job_id, filename):
    """Process a large file in the background and save result to database"""
    try:
        app.logger.info(f"Starting background processing of {filename} with job_id {job_id}")
        background_jobs[job_id]['status'] = 'processing'
        
        # First, check if file is very large and needs trimming
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size_mb > 100:  # For extremely large files
            app.logger.info(f"Extremely large file ({file_size_mb:.2f} MB), trimming to 30 minutes")
            file_path = trim_audio_if_needed(file_path, 1800)  # 30 minutes
        
        # Process the file directly (no preprocessing for large files)
        with open(file_path, 'rb') as audio_file:
            transcript = transcribe_audio(audio_file)
        
        # Save to database
        file_size = os.path.getsize(file_path)
        transcription_id = db.save_transcription(
            filename=secure_filename(filename),
            file_size=file_size,
            transcript=transcript
        )
        
        # Update job status
        background_jobs[job_id]['status'] = 'completed'
        background_jobs[job_id]['transcription_id'] = transcription_id
        background_jobs[job_id]['transcript'] = transcript
        background_jobs[job_id]['completed_at'] = time.time()
        
        app.logger.info(f"Background processing complete for job {job_id}, transcript ID: {transcription_id}")
    except Exception as e:
        app.logger.error(f"Error in background processing for job {job_id}: {str(e)}")
        app.logger.error(traceback.format_exc())
        
        # Update job status with error
        background_jobs[job_id]['status'] = 'failed'
        background_jobs[job_id]['error'] = str(e)
        background_jobs[job_id]['error_type'] = type(e).__name__
    finally:
        # Clean up the temporary file
        if os.path.exists(file_path):
            os.remove(file_path)

@app.route('/api/transcribe-large', methods=['POST'])
def transcribe_large_audio_route():
    """Special route for handling very large audio files with background processing"""
    start_time = time.time()
    
    app.logger.info("Large file transcription request received")
    
    if 'file' not in request.files:
        app.logger.warning("No file part in request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        app.logger.warning("No selected file")
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        # Save the uploaded file temporarily
        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(temp_filepath)
        file_size = os.path.getsize(temp_filepath)
        file_size_mb = file_size / (1024 * 1024)
        
        app.logger.info(f"Large file saved: {file.filename}, Size: {file_size_mb:.2f} MB")
        
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Initialize job tracking
        background_jobs[job_id] = {
            'filename': file.filename,
            'file_size': file_size,
            'status': 'queued',
            'created_at': time.time()
        }
        
        # Start a background thread to process the file
        thread = threading.Thread(
            target=process_large_file_in_background,
            args=(temp_filepath, job_id, file.filename)
        )
        thread.daemon = True
        thread.start()
        
        # Log API request
        processing_time = time.time() - start_time
        db.log_api_request(
            '/api/transcribe-large',
            'POST',
            202,
            {'filename': file.filename, 'file_size': file_size, 'job_id': job_id},
            0,
            processing_time
        )
        
        return jsonify({
            'status': 'processing',
            'job_id': job_id,
            'message': 'Your file is being processed. Please check status using the /api/job-status/{job_id} endpoint.'
        }), 202  # 202 Accepted

@app.route('/api/job-status/<job_id>', methods=['GET'])
def check_job_status(job_id):
    """Check the status of a background processing job"""
    if job_id not in background_jobs:
        return jsonify({
            'error': 'Job not found',
            'job_id': job_id
        }), 404
    
    job = background_jobs[job_id]
    
    if job['status'] == 'completed':
        # If job is complete, return the transcript data
        return jsonify({
            'job_id': job_id,
            'status': 'completed',
            'transcription_id': job['transcription_id'],
            'transcript': job['transcript'],
            'message': 'Transcription complete'
        }), 200
    elif job['status'] == 'failed':
        # If job failed, return the error information
        return jsonify({
            'job_id': job_id,
            'status': 'failed',
            'error': job.get('error', 'Unknown error'),
            'error_type': job.get('error_type', 'Unknown'),
            'message': 'Transcription failed'
        }), 500
    else:
        # Job is still processing
        elapsed_time = time.time() - job['created_at']
        
        return jsonify({
            'job_id': job_id,
            'status': job['status'],
            'filename': job['filename'],
            'file_size': job['file_size'],
            'elapsed_time': elapsed_time,
            'message': 'Your file is still being processed. Please check back later.'
        }), 200

@app.route('/api/summarize', methods=['POST'])
def summarize_transcript():
    start_time = time.time()
    
    data = request.json
    if not data or 'transcript' not in data:
        db.log_api_request('/api/summarize', 'POST', 400, 'No transcript provided', 0, 0)
        return jsonify({'error': 'No transcript provided'}), 400
    
    transcript = data['transcript']
    transcription_id = data.get('transcription_id')
    
    # Set default values for word_count and style
    word_count = data.get('wordCount', 100)
    style = data.get('style', 'overview')
    
    try:
        summary = summarize_text(transcript, word_count, style)
        
        # Save summary to database if we have a transcription_id
        if transcription_id:
            db.save_summary(transcription_id, summary, word_count, style)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Log API request
        response_data = {'summary': summary}
        db.log_api_request(
            '/api/summarize',
            'POST',
            200,
            {'transcription_id': transcription_id, 'word_count': word_count, 'style': style},
            len(summary),
            processing_time
        )
        
        return jsonify(response_data), 200
        
    except Exception as e:
        # Log error details
        app.logger.error(f"Error in summarize_transcript: {str(e)}")
        app.logger.error(traceback.format_exc())
        
        # Log error
        processing_time = time.time() - start_time
        db.log_api_request(
            '/api/summarize',
            'POST',
            500,
            {'transcription_id': transcription_id, 'error': str(e)},
            0,
            processing_time
        )
        
        return jsonify({'error': str(e)}), 500

@app.route('/api/customize-summary', methods=['POST'])
def customize_summary():
    start_time = time.time()
    
    data = request.json
    if not data or 'transcript' not in data:
        db.log_api_request('/api/customize-summary', 'POST', 400, 'No transcript provided', 0, 0)
        return jsonify({'error': 'No transcript provided'}), 400
    
    # Extract parameters
    transcript = data['transcript']
    transcription_id = data.get('transcription_id')
    word_count = data.get('wordCount', 100)
    style = data.get('style', 'overview')
    
    try:
        # For now, use the same summarize_text function with custom parameters
        custom_summary = summarize_text(transcript, word_count, style)
        
        # Save to database if we have a transcription_id
        if transcription_id:
            db.save_summary(transcription_id, custom_summary, word_count, style)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Log API request
        response_data = {'summary': custom_summary}
        db.log_api_request(
            '/api/customize-summary',
            'POST',
            200,
            {'transcription_id': transcription_id, 'word_count': word_count, 'style': style},
            len(custom_summary),
            processing_time
        )
        
        return jsonify(response_data), 200
        
    except Exception as e:
        # Log error details
        app.logger.error(f"Error in customize_summary: {str(e)}")
        app.logger.error(traceback.format_exc())
        
        # Log error
        processing_time = time.time() - start_time
        db.log_api_request(
            '/api/customize-summary',
            'POST',
            500,
            {'transcription_id': transcription_id, 'error': str(e)},
            0,
            processing_time
        )
        
        return jsonify({'error': str(e)}), 500

@app.route('/api/ask', methods=['POST'])
def ask_question():
    start_time = time.time()
    
    data = request.json
    if not data or 'transcript' not in data or 'question' not in data:
        db.log_api_request('/api/ask', 'POST', 400, 'Transcript or question missing', 0, 0)
        return jsonify({'error': 'Transcript or question missing'}), 400
    
    transcript = data['transcript']
    user_question = data['question']
    transcription_id = data.get('transcription_id')
    
    try:
        answer = question(transcript, user_question)
        
        # Save to database if we have a transcription_id
        if transcription_id:
            db.save_question(transcription_id, user_question, answer)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Log API request
        response_data = {'answer': answer}
        db.log_api_request(
            '/api/ask',
            'POST',
            200,
            {'transcription_id': transcription_id, 'question': user_question},
            len(answer),
            processing_time
        )
        
        return jsonify(response_data), 200
        
    except Exception as e:
        # Log error details
        app.logger.error(f"Error in ask_question: {str(e)}")
        app.logger.error(traceback.format_exc())
        
        # Log error
        processing_time = time.time() - start_time
        db.log_api_request(
            '/api/ask',
            'POST',
            500,
            {'transcription_id': transcription_id, 'question': user_question, 'error': str(e)},
            0,
            processing_time
        )
        
        return jsonify({'error': str(e)}), 500

# Admin routes to view data
@app.route('/admin/transcriptions', methods=['GET'])
def view_transcriptions():
    try:
        limit = request.args.get('limit', 10, type=int)
        transcriptions = db.get_recent_transcriptions(limit)
        return jsonify({'transcriptions': transcriptions}), 200
    except Exception as e:
        app.logger.error(f"Error in view_transcriptions: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/transcription/<int:transcription_id>', methods=['GET'])
def view_transcription_details(transcription_id):
    try:
        transcription = db.get_transcription_by_id(transcription_id)
        summaries = db.get_summaries_for_transcription(transcription_id)
        questions = db.get_questions_for_transcription(transcription_id)
        
        return jsonify({
            'transcription': transcription,
            'summaries': summaries,
            'questions': questions
        }), 200
    except Exception as e:
        app.logger.error(f"Error in view_transcription_details: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/jobs', methods=['GET'])
def view_active_jobs():
    """View all active background jobs"""
    try:
        # Convert to serializable format
        serializable_jobs = {}
        for job_id, job_data in background_jobs.items():
            job_copy = job_data.copy()
            # Remove transcript which might be too large to display
            if 'transcript' in job_copy:
                job_copy['transcript'] = f"[Transcript available, length: {len(job_copy['transcript'])} chars]"
            serializable_jobs[job_id] = job_copy
            
        return jsonify({'jobs': serializable_jobs}), 200
    except Exception as e:
        app.logger.error(f"Error in view_active_jobs: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Use PORT environment variable if available (for deployment)
    port = int(os.environ.get("PORT", 5000))
    # Run with threaded=True to handle concurrent requests better
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)