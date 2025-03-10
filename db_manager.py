import sqlite3
import os
from datetime import datetime

# Database file path
DB_PATH = 'transcription_data.db'

def init_db():
    """Initialize the database with required tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create transcriptions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transcriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        transcript TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL
    )
    ''')
    
    # Create summaries table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transcription_id INTEGER NOT NULL,
        summary TEXT NOT NULL,
        word_count INTEGER NOT NULL,
        style TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        FOREIGN KEY (transcription_id) REFERENCES transcriptions (id)
    )
    ''')
    
    # Create questions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transcription_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        FOREIGN KEY (transcription_id) REFERENCES transcriptions (id)
    )
    ''')
    
    # Create api_requests table to log all API usage
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS api_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        endpoint TEXT NOT NULL,
        method TEXT NOT NULL,
        status_code INTEGER NOT NULL,
        request_data TEXT,
        response_size INTEGER,
        processing_time REAL,
        created_at TIMESTAMP NOT NULL
    )
    ''')
    
    conn.commit()
    conn.close()
    
    print("Database initialized successfully.")

def save_transcription(filename, file_size, transcript):
    """Save a transcription to the database and return its ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO transcriptions (filename, file_size, transcript, created_at) VALUES (?, ?, ?, ?)",
        (filename, file_size, transcript, datetime.now())
    )
    
    # Get the ID of the inserted row
    transcription_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return transcription_id

def save_summary(transcription_id, summary, word_count, style):
    """Save a summary to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO summaries (transcription_id, summary, word_count, style, created_at) VALUES (?, ?, ?, ?, ?)",
        (transcription_id, summary, word_count, style, datetime.now())
    )
    
    conn.commit()
    conn.close()

def save_question(transcription_id, question, answer):
    """Save a question and its answer to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO questions (transcription_id, question, answer, created_at) VALUES (?, ?, ?, ?)",
        (transcription_id, question, answer, datetime.now())
    )
    
    conn.commit()
    conn.close()

def log_api_request(endpoint, method, status_code, request_data=None, response_size=None, processing_time=None):
    """Log details about API requests for tracking usage."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Convert request_data to string if it's not None
    if request_data is not None and not isinstance(request_data, str):
        import json
        request_data = json.dumps(request_data)
    
    cursor.execute(
        "INSERT INTO api_requests (endpoint, method, status_code, request_data, response_size, processing_time, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (endpoint, method, status_code, request_data, response_size, processing_time, datetime.now())
    )
    
    conn.commit()
    conn.close()

def get_recent_transcriptions(limit=10):
    """Get the most recent transcriptions."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id, filename, file_size, substr(transcript, 1, 100) || '...', created_at FROM transcriptions ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    
    results = cursor.fetchall()
    conn.close()
    
    return results

def get_transcription_by_id(transcription_id):
    """Get a specific transcription by ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM transcriptions WHERE id = ?", (transcription_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result

def get_summaries_for_transcription(transcription_id):
    """Get all summaries for a specific transcription."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM summaries WHERE transcription_id = ? ORDER BY created_at DESC", (transcription_id,))
    results = cursor.fetchall()
    
    conn.close()
    return results

def get_questions_for_transcription(transcription_id):
    """Get all questions for a specific transcription."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM questions WHERE transcription_id = ? ORDER BY created_at DESC", (transcription_id,))
    results = cursor.fetchall()
    
    conn.close()
    return results

# Initialize the database when this module is imported
if __name__ == "__main__":
    init_db()