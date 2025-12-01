# Sravan's AI Podcast Studio

A multi-agent AI system that converts blog posts into professional video podcasts with synchronized subtitles.

## Features

- **Multi-Speaker Audio**: Indian English voices (Host A: RehaanNeural, Host B: KavyaNeural)
- **Animated Video**: Professional 1080p video with gradient backgrounds, pulsing circles, and particles
- **Synchronized Subtitles**: Bullet-point captions burned directly into video frames
- **Real-Time Progress**: Live updates during conversion
- **Dual Output**: Both MP3 audio and MP4 video files

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your Google API key:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```

5. Run migrations:
   ```bash
   python manage.py migrate
   ```

6. Start the server:
   ```bash
   python manage.py runserver
   ```

7. Open http://localhost:8000 in your browser

## Usage

1. Paste a blog URL into the input field
2. Click "Generate Podcast"
3. Wait for the AI agents to process (2-3 minutes)
4. Download your MP3 audio and MP4 video

## Architecture

The system uses 4 AI agents:
- **Content Extraction Agent**: Scrapes and cleans blog content
- **Script Generation Agent**: Creates dialogue using Google Gemini
- **Audio Generation Agent**: Generates multi-speaker audio with Edge TTS
- **Video Generation Agent**: Creates video with synchronized subtitles

## Technology Stack

- Django 5.x
- Google Gemini 2.0 Flash
- Microsoft Edge TTS
- MoviePy + Pillow
- BeautifulSoup4

## License

MIT
