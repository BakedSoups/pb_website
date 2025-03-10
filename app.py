from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import tempfile
import io
import time
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from transcriber import remove_silence, preprocess_audio, transcribe_audio
from manage_audio import summarize_text, question
import db_manager as db

app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for all routes

# Configure upload folder
UPLOAD_FOLDER = 'temp_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize database
db.init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transcribe', methods=['POST'])
def transcribe_audio_route():
    start_time = time.time()
    
    if 'file' not in request.files:
        db.log_api_request('/api/transcribe', 'POST', 400, 'No file part', 0, 0)
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        db.log_api_request('/api/transcribe', 'POST', 400, 'No selected file', 0, 0)
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        # Save the uploaded file temporarily
        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(temp_filepath)
        file_size = os.path.getsize(temp_filepath)
        
        try:
            # Process the audio file using your existing functions
            processed_audio = remove_silence(temp_filepath)
            processed_audio = preprocess_audio(processed_audio, speed=1.5)
            
            # Create a temporary file for the processed audio
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_processed:
                temp_processed.write(processed_audio.getvalue())
                processed_filepath = temp_processed.name
            
            # Transcribe the processed audio using OpenAI's Whisper
            with open(processed_filepath, 'rb') as audio_file:
                transcript = transcribe_audio(audio_file)
            
            # Clean up temporary files
            os.remove(temp_filepath)
            os.remove(processed_filepath)
            
            # Save transcription to database
            transcription_id = db.save_transcription(
                filename=secure_filename(file.filename),
                file_size=file_size,
                transcript=transcript
            )
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Log API request
            response_data = {'transcript': transcript, 'transcription_id': transcription_id}
            db.log_api_request(
                '/api/transcribe',
                'POST',
                200,
                {'filename': file.filename, 'file_size': file_size},
                len(str(response_data)),
                processing_time
            )
            
            return jsonify(response_data), 200
            
        except Exception as e:
            # Clean up temporary file if it exists
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            
            # Log error
            processing_time = time.time() - start_time
            db.log_api_request(
                '/api/transcribe',
                'POST',
                500,
                {'filename': file.filename, 'error': str(e)},
                0,
                processing_time
            )
            
            return jsonify({'error': str(e)}), 500

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
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Use PORT environment variable if available (for deployment)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)