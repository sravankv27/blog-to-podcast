import os
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import uuid
from django.conf import settings

def fetch_blog_content(url):
    """
    Fetches and extracts text content from a blog URL.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        # Get text
        text = soup.get_text()
        
        # Break into lines and remove leading/trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    except Exception as e:
        print(f"Error fetching blog content: {e}")
        raise e

def generate_podcast_script(text):
    """
    Generates a podcast script from the given text using Google Gemini.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = f"""
    You are an expert podcast script writer. Convert the following blog post content into an engaging, conversational podcast script between two hosts (Host A and Host B).
    
    STRICT FORMATTING RULES:
    1. Every line of dialogue MUST start with exactly "Host A:" or "Host B:".
    2. Do not use "Host A says" or other variations.
    3. Do not include stage directions or sound effects in parentheses unless they are very short and at the end of the line.
    4. Keep it concise (around 2-3 minutes spoken).
    5. Make it sound natural, with some back-and-forth.

    Blog Content:
    {text[:10000]}
    
    Podcast Script:
    """
    
    response = model.generate_content(prompt)
    return response.text
