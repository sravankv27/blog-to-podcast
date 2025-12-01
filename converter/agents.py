import threading
from .models import ConversionTask
from .utils import fetch_blog_content, generate_podcast_script

class BaseAgent:
    def __init__(self, task_id):
        self.task_id = task_id
        self.task = ConversionTask.objects.get(id=task_id)

    def update_progress(self, progress, step):
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {step}\n"
        
        self.task.progress = progress
        self.task.current_step = step
        self.task.logs += log_entry
        self.task.save()

class ContentExtractionAgent(BaseAgent):
    def run(self):
        self.update_progress(10, "Extracting content from blog...")
        content = fetch_blog_content(self.task.url)
        if not content:
            raise Exception("Failed to fetch content")
        return content

class ScriptGenerationAgent(BaseAgent):
    def run(self, content):
        self.update_progress(40, "Generating podcast script with Gemini...")
        script = generate_podcast_script(content)
        if not script:
            raise Exception("Failed to generate script")
        self.task.script = script
        self.task.save()
        return script

import asyncio
import edge_tts
import os
from django.conf import settings

class AudioGenerationAgent(BaseAgent):
    def run(self, script):
        self.update_progress(80, "Generating multi-speaker audio...")
        
        # Parse script into segments
        segments = []
        lines = script.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith("Host A:") or line.startswith("Host A ("):
                text = line.split(":", 1)[1].strip()
                segments.append({"voice": "en-IN-RehaanNeural", "text": text})
            elif line.startswith("Host B:") or line.startswith("Host B ("):
                text = line.split(":", 1)[1].strip()
                segments.append({"voice": "en-IN-KavyaNeural", "text": text})
            else:
                # Default to Host A if no label found (or narration)
                segments.append({"voice": "en-IN-RehaanNeural", "text": line})

        # Generate audio for each segment
        output_file = f"podcast_{self.task_id}.mp3"
        output_path = os.path.join(settings.MEDIA_ROOT, output_file)
        
        # Ensure media directory exists
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

        async def generate_audio():
            from asgiref.sync import sync_to_async
            
            temp_files = []
            timing_data = []
            current_time = 0.0
            
            # Need to import AudioFileClip here or at top level
            try:
                from moviepy import AudioFileClip
            except ImportError:
                from moviepy.editor import AudioFileClip

            for i, seg in enumerate(segments):
                if not seg['text']: 
                    print(f"Skipping empty segment {i}")
                    continue
                
                print(f"Generating segment {i}: {seg['voice']} - '{seg['text'][:50]}...'")
                temp_file = os.path.join(settings.MEDIA_ROOT, f"temp_{self.task_id}_{i}.mp3")
                
                try:
                    communicate = edge_tts.Communicate(seg['text'], seg['voice'])
                    await communicate.save(temp_file)
                    temp_files.append(temp_file)
                    
                    # Get duration
                    try:
                        clip = AudioFileClip(temp_file)
                        duration = clip.duration
                        clip.close()
                        
                        timing_data.append({
                            'start': current_time,
                            'end': current_time + duration,
                            'text': seg['text'],
                            'speaker': "Host A" if seg['voice'] == "en-IN-RehaanNeural" else "Host B"
                        })
                        current_time += duration
                    except Exception as e:
                        print(f"Error getting duration for segment {i}: {e}")
                        
                except Exception as e:
                    print(f"Error generating segment {i}: {e}")
                    # Continue to next segment instead of failing everything
                    continue
            
            if not temp_files:
                raise Exception("No audio segments were successfully generated.")

            # Save timing map using sync_to_async
            @sync_to_async
            def save_timing_map():
                self.task.timing_map = timing_data
                self.task.save()
            
            await save_timing_map()

            # Concatenate files
            with open(output_path, 'wb') as outfile:
                for temp_file in temp_files:
                    try:
                        with open(temp_file, 'rb') as infile:
                            outfile.write(infile.read())
                        os.remove(temp_file) # Clean up temp file
                    except Exception as e:
                        print(f"Error merging file {temp_file}: {e}")

        try:
            asyncio.run(generate_audio())
        except Exception as e:
            raise Exception(f"Failed to generate audio: {str(e)}")

        self.task.audio_file = output_file
        self.task.save()
        return output_file

class VideoGenerationAgent(BaseAgent):
    def run(self, audio_file):
        self.update_progress(90, "Generating video with captions...")
        
        try:
            from moviepy import AudioFileClip, ColorClip, CompositeVideoClip, TextClip
        except ImportError:
            # Fallback to old import style
            from moviepy.editor import AudioFileClip, ColorClip, CompositeVideoClip, TextClip
        
        audio_path = os.path.join(settings.MEDIA_ROOT, audio_file)
        output_file = f"podcast_{self.task_id}.mp4"
        output_path = os.path.join(settings.MEDIA_ROOT, output_file)
        
        try:
            # Load audio
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration
            
            # Parse script for subtitles
            # Use timing map if available, otherwise fallback to estimation (or just empty)
            subtitle_segments = self.task.timing_map
            
            if not subtitle_segments and self.task.script:
                # Fallback to old estimation logic if timing_map is empty for some reason
                script = self.task.script
                current_time = 0
                lines = script.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Estimate duration based on text length (roughly 150 words per minute)
                    words = len(line.split())
                    segment_duration = max(2, words / 2.5)  # At least 2 seconds per line
                    
                    speaker = "Host A"
                    text = line
                    
                    if line.startswith("Host A:"):
                        speaker = "Host A"
                        text = line.split(":", 1)[1].strip()
                    elif line.startswith("Host B:"):
                        speaker = "Host B"
                        text = line.split(":", 1)[1].strip()
                    
                    if current_time + segment_duration <= duration:
                        subtitle_segments.append({
                            'start': current_time,
                            'end': current_time + segment_duration,
                            'speaker': speaker,
                            'text': text
                        })
                        current_time += segment_duration
            
            # Create animated gradient background with particles
            def make_frame(t):
                import numpy as np
                import math
                # Create a gradient that shifts over time
                w, h = 1920, 1080
                frame = np.zeros((h, w, 3), dtype=np.uint8)
                
                # Animated gradient from dark blue to purple
                for y in range(h):
                    progress = (y / h + t / 10) % 1.0
                    r = int(15 + progress * 100)
                    g = int(23 + progress * 50)
                    b = int(42 + progress * 180)
                    frame[y, :] = [r, g, b]
                
                # Add pulsing circles
                pulse = abs(math.sin(t * 2))
                circle_radius = int(200 + pulse * 100)
                
                # Draw multiple pulsing circles
                for cx, cy in [(480, 270), (1440, 270), (960, 810)]:
                    for radius in range(circle_radius, circle_radius + 50, 10):
                        alpha = 1 - (radius - circle_radius) / 50
                        for angle in range(0, 360, 5):
                            x = int(cx + radius * math.cos(math.radians(angle)))
                            y = int(cy + radius * math.sin(math.radians(angle)))
                            if 0 <= x < w and 0 <= y < h:
                                frame[y, x] = [
                                    min(255, int(frame[y, x, 0] + 60 * alpha)),
                                    min(255, int(frame[y, x, 1] + 100 * alpha)),
                                    min(255, int(frame[y, x, 2] + 200 * alpha))
                                ]
                
                # Add floating particles
                num_particles = 30
                for i in range(num_particles):
                    particle_t = (t + i * 2) % 20
                    px = int((w / num_particles * i + particle_t * 50) % w)
                    py = int((h / 2 + math.sin(t + i) * 300))
                    if 0 <= px < w and 0 <= py < h:
                        for dx in range(-3, 4):
                            for dy in range(-3, 4):
                                if 0 <= px + dx < w and 0 <= py + dy < h:
                                    if dx*dx + dy*dy <= 9:
                                        frame[py + dy, px + dx] = [200, 200, 255]
                
                return frame
            
            from moviepy import VideoClip
            background = VideoClip(make_frame, duration=duration)
            
            # Create video with text burned into frames
            intro_duration = 2  # 2 seconds blank intro
            outro_duration = 2  # 2 seconds blank outro
            content_duration = duration - intro_duration - outro_duration
            
            def make_video_frame(t):
                import numpy as np
                import math
                from PIL import Image, ImageDraw, ImageFont
                
                w, h = 1920, 1080
                
                # Show blank screen during intro and outro
                if t < intro_duration or t >= (intro_duration + content_duration):
                    # Black screen
                    frame = np.zeros((h, w, 3), dtype=np.uint8)
                    return frame
                
                # Adjust time for content (subtract intro duration)
                content_t = t - intro_duration
                
                # Create a gradient that shifts over time
                frame = np.zeros((h, w, 3), dtype=np.uint8)
                
                # Animated gradient from dark blue to purple
                for y in range(h):
                    progress = (y / h + content_t / 10) % 1.0
                    r = int(15 + progress * 100)
                    g = int(23 + progress * 50)
                    b = int(42 + progress * 180)
                    frame[y, :] = [r, g, b]
                
                # Add pulsing circles
                pulse = abs(math.sin(content_t * 2))
                circle_radius = int(200 + pulse * 100)
                
                # Draw multiple pulsing circles
                for cx, cy in [(480, 270), (1440, 270), (960, 810)]:
                    for radius in range(circle_radius, circle_radius + 50, 10):
                        alpha = 1 - (radius - circle_radius) / 50
                        for angle in range(0, 360, 5):
                            x = int(cx + radius * math.cos(math.radians(angle)))
                            y = int(cy + radius * math.sin(math.radians(angle)))
                            if 0 <= x < w and 0 <= y < h:
                                frame[y, x] = [
                                    min(255, int(frame[y, x, 0] + 60 * alpha)),
                                    min(255, int(frame[y, x, 1] + 100 * alpha)),
                                    min(255, int(frame[y, x, 2] + 200 * alpha))
                                ]
                
                # Add floating particles
                num_particles = 30
                for i in range(num_particles):
                    particle_t = (content_t + i * 2) % 20
                    px = int((w / num_particles * i + particle_t * 50) % w)
                    py = int((h / 2 + math.sin(content_t + i) * 300))
                    if 0 <= px < w and 0 <= py < h:
                        for dx in range(-3, 4):
                            for dy in range(-3, 4):
                                if 0 <= px + dx < w and 0 <= py + dy < h:
                                    if dx*dx + dy*dy <= 9:
                                        frame[py + dy, px + dx] = [200, 200, 255]
                
                # Convert to PIL Image for text rendering
                img = Image.fromarray(frame)
                draw = ImageDraw.Draw(img)
                
                try:
                    # Try to use a nice font
                    title_font = ImageFont.truetype("arial.ttf", 50)
                    live_font = ImageFont.truetype("arialbd.ttf", 35)
                    bullet_font = ImageFont.truetype("arialbd.ttf", 45)
                    speaker_font = ImageFont.truetype("arialbd.ttf", 38)
                except:
                    # Fallback to default font
                    title_font = ImageFont.load_default()
                    live_font = ImageFont.load_default()
                    bullet_font = ImageFont.load_default()
                    speaker_font = ImageFont.load_default()
                
                # Draw title with background
                title_text = "Graffiti - AI Podcast"
                title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
                title_width = title_bbox[2] - title_bbox[0]
                title_x = (w - title_width) // 2
                # Background rectangle
                draw.rectangle([title_x - 20, 20, title_x + title_width + 20, 100], fill=(0, 0, 0, 180))
                draw.text((title_x, 30), title_text, fill=(255, 255, 255), font=title_font)
                
                # Draw LIVE indicator
                draw.rectangle([20, 20, 180, 80], fill=(0, 0, 0, 200))
                draw.text((30, 30), "● LIVE", fill=(239, 68, 68), font=live_font)
                
                # Find and draw current subtitle (adjust timing for intro)
                for segment in subtitle_segments:
                    # Adjust segment times to account for intro
                    adjusted_start = segment['start'] + intro_duration
                    adjusted_end = segment['end'] + intro_duration
                    
                    if adjusted_start <= t < adjusted_end:
                        # Speaker color
                        if segment['speaker'] == 'Host A':
                            color = (96, 165, 250)  # Light blue
                            icon = "🎙️"
                        else:
                            color = (192, 132, 252)  # Light purple
                            icon = "🎤"
                        
                        # Draw speaker label background
                        speaker_text = f"{icon} {segment['speaker']}"
                        draw.rectangle([80, 680, 400, 740], fill=(0, 0, 0, 230))
                        draw.text((100, 690), speaker_text, fill=(255, 255, 255), font=speaker_font)
                        
                        # Draw bullet point background
                        bullet_text = f"• {segment['text']}"
                        # Word wrap
                        if len(bullet_text) > 70:
                            words = bullet_text.split()
                            lines = []
                            current_line = "• "
                            for word in words[1:]:
                                if len(current_line + word) > 70:
                                    lines.append(current_line.strip())
                                    current_line = "  " + word + " "
                                else:
                                    current_line += word + " "
                            if current_line.strip():
                                lines.append(current_line.strip())
                            bullet_text = '\n'.join(lines[:2])  # Max 2 lines
                        
                        # Background for bullet
                        draw.rectangle([80, 760, w - 80, 950], fill=(15, 23, 42, 240))
                        
                        # Draw bullet text
                        y_offset = 780
                        for line in bullet_text.split('\n'):
                            draw.text((100, y_offset), line, fill=color, font=bullet_font)
                            y_offset += 60
                        
                        break
                
                return np.array(img)
            
            from moviepy import VideoClip
            video = VideoClip(make_video_frame, duration=duration)
            
            # Add audio (offset by intro duration)
            audio_with_silence = audio_clip.with_start(intro_duration)
            video = video.with_audio(audio_with_silence)
            
            # Write video file
            video.write_videofile(output_path, fps=30, codec='libx264', 
                                 audio_codec='aac', bitrate='5000k',
                                 temp_audiofile=os.path.join(settings.MEDIA_ROOT, f'temp_audio_{self.task_id}.m4a'),
                                 remove_temp=True, logger=None)
            
            # Close clips
            audio_clip.close()
            video.close()
            
        except Exception as e:
            raise Exception(f"Failed to generate video: {str(e)}")
        
        self.task.video_file = output_file
        self.task.save()
        return output_file


class Orchestrator:
    def __init__(self, task_id):
        self.task_id = task_id

    def start(self):
        thread = threading.Thread(target=self._process)
        thread.start()

    def _process(self):
        try:
            task = ConversionTask.objects.get(id=self.task_id)
            task.status = 'PROCESSING'
            task.save()

            # Agent 1: Extract
            extractor = ContentExtractionAgent(self.task_id)
            content = extractor.run()

            # Agent 2: Script
            writer = ScriptGenerationAgent(self.task_id)
            script = writer.run(content)

            # Agent 3: Audio
            audio_gen = AudioGenerationAgent(self.task_id)
            audio_file = audio_gen.run(script)

            # Agent 4: Video
            video_gen = VideoGenerationAgent(self.task_id)
            video_gen.run(audio_file)

            # Complete
            # Refetch task to ensure we don't overwrite fields saved by agents
            task = ConversionTask.objects.get(id=self.task_id)
            task.progress = 100
            task.current_step = "Completed"
            task.status = 'COMPLETED'
            task.save()

        except Exception as e:
            import traceback
            task = ConversionTask.objects.get(id=self.task_id)
            task.status = 'FAILED'
            task.error_message = f"{str(e)}\n{traceback.format_exc()}"
            task.save()
