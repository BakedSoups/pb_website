from openai import OpenAI
from transcriber import process_audio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment variable
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("No OpenAI API key found. Please set the OPENAI_API_KEY environment variable.")

client = OpenAI(api_key=api_key)
def summarize_text(text,word_count,style):
    response = client.chat.completions.create(
        model="gpt-4-turbo",  # Use "gpt-3.5-turbo" for a cheaper option
        messages=[
            {"role": "system", "content": f"You shorten text and give a {style}summary. Just talk about the content; don't add anything like 'for today'."},
            {"role": "user", "content": f"Summarize this:\n\n{text} in exactly {word_count} words"}
        ],
        temperature=0.4,
        max_tokens=800
    )

    return response.choices[0].message.content.strip()

def question(text, question):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # Use "gpt-3.5-turbo" for a cheaper option
        messages=[
            {"role": "system", "content": "You answer questions about the provided text accurately and concisely."},
            {"role": "user", "content": f"With this text:\n\n{text}\n\nAnswer this question: {question}"}
        ],
        temperature=0.5,
        max_tokens=200
    )

    return response.choices[0].message.content.strip()

if __name__ == "__main__":
    transcript = process_audio()
    summary = summarize_text(transcript)
    print(summary)