import os
import logging
import asyncio
import re
import threading
from uuid import uuid4
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackContext, CallbackQueryHandler
)
import yt_dlp
from pydub import AudioSegment
import speech_recognition as sr

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize recognizer
recognizer = sr.Recognizer()

# Audio download options
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'wav',
        'preferredquality': '192',
    }],
    'outtmpl': 'audio_%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True
}

class TranscriptionBot:
    def __init__(self):
        self.token = "7567951774:AAEeyDqHnaC7uuPUvw_wAoW6WF9iZ0pO_NE"
        self.application = Application.builder().token(self.token).build()
        
        # Register handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("transcribe", self.transcribe_help))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Track active processes
        self.active_transcriptions = {}
        
        # Supported languages
        self.languages = {
            'en': {'code': 'en-US', 'name': 'English'},
            'ar': {'code': 'ar-SA', 'name': 'العربية'},
            'es': {'code': 'es-ES', 'name': 'Español'},
            'fr': {'code': 'fr-FR', 'name': 'Français'},
            'de': {'code': 'de-DE', 'name': 'Deutsch'}
        }

    async def start(self, update: Update, context: CallbackContext) -> None:
        """Send welcome message with interactive buttons"""
        keyboard = [
            [InlineKeyboardButton("📝 Transcribe Video", callback_data='how_to'),
             InlineKeyboardButton("⚙️ الإعدادات", callback_data='settings')],
            [InlineKeyboardButton("ℹ️ About", callback_data='about'),
             InlineKeyboardButton("🆘 المساعدة", callback_data='help_ar')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🎬 *YouTube Video Transcriber*\n\n"
            "أرسل لي رابط فيديو يوتيوب وسأحوله إلى نص لك!\n\n"
            "✨ *الميزات:*\n"
            "- يدعم أي فيديو على يوتيوب\n"
            "- تحويل سريع للصوت إلى نص\n"
            "- دعم متعدد للغات\n"
            "- تنسيق نظيف\n",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def help(self, update: Update, context: CallbackContext) -> None:
        """Send help information in English"""
        await update.message.reply_text(
            "🆘 *How to use this bot:*\n\n"
            "1. Send a YouTube video URL (e.g., https://www.youtube.com/watch?v=...)\n"
            "2. Wait while I download and process the audio\n"
            "3. Receive your transcription!\n\n"
            "💡 *Tips:*\n"
            "- Videos under 10 minutes work best\n"
            "- Clear audio gives better results\n"
            "- Use /settings to configure language\n",
            parse_mode='Markdown'
        )

    async def help_arabic(self, update: Update, context: CallbackContext) -> None:
        """Send help information in Arabic"""
        await update.message.reply_text(
            "🆘 *كيفية استخدام هذا البوت:*\n\n"
            "1. أرسل رابط فيديو يوتيوب (مثال: https://www.youtube.com/watch?v=...)\n"
            "2. انتظر بينما أقوم بتحميل ومعالجة الصوت\n"
            "3. استلم النص المحول!\n\n"
            "💡 *نصائح:*\n"
            "- الفيديوهات أقل من 10 دقائق تعمل بشكل أفضل\n"
            "- الصوت الواضح يعطي نتائج أفضل\n"
            "- استخدم /settings لضبط اللغة\n",
            parse_mode='Markdown'
        )

    async def transcribe_help(self, update: Update, context: CallbackContext) -> None:
        """Help for transcribe command"""
        await update.message.reply_text(
            "🔍 *Transcription Help*\n\n"
            "Just send me a YouTube link directly or use:\n"
            "/transcribe [YouTube URL]\n\n"
            "مثال:\n"
            "/transcribe https://www.youtube.com/watch?v=...",
            parse_mode='Markdown'
        )

    async def button_handler(self, update: Update, context: CallbackContext) -> None:
        """Handle inline button presses"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'how_to':
            await query.edit_message_text(
                "📋 *How to transcribe videos:*\n\n"
                "1. Copy a YouTube video URL\n"
                "2. Paste it here\n"
                "3. I'll process it and send you the text\n\n"
                "⏳ Processing time depends on video length\n"
                "🔊 Better audio quality = better results",
                parse_mode='Markdown'
            )
        elif query.data == 'help_ar':
            await query.edit_message_text(
                "📋 *كيفية تحويل الفيديوهات:*\n\n"
                "1. انسخ رابط فيديو يوتيوب\n"
                "2. الصقه هنا\n"
                "3. سأقوم بمعالجته وإرسال النص لك\n\n"
                "⏳ وقت المعالجة يعتمد على طول الفيديو\n"
                "🔊 جودة صوت أفضل = نتائج أفضل",
                parse_mode='Markdown'
            )
        elif query.data == 'settings':
            keyboard = [
                [InlineKeyboardButton("English", callback_data='lang_en')],
                [InlineKeyboardButton("العربية", callback_data='lang_ar')],
                [InlineKeyboardButton("Español", callback_data='lang_es')],
                [InlineKeyboardButton("Français", callback_data='lang_fr')],
                [InlineKeyboardButton("Back", callback_data='back')]
            ]
            await query.edit_message_text(
                "⚙️ *Settings*\n\n"
                "اختر لغة التحويل:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        elif query.data.startswith('lang_'):
            lang = query.data.split('_')[1]
            context.user_data['language'] = self.languages[lang]['code']
            await query.edit_message_text(
                f"✅ تم ضبط اللغة على: {self.languages[lang]['name']}",
                parse_mode='Markdown'
            )
        elif query.data == 'about':
            await query.edit_message_text(
                "🤖 *About YouTube Transcriber*\n\n"
                "إصدار: 2.2\n"
                "المطور: @YourUsername\n\n"
                "هذا البوت يستخدم:\n"
                "- Python 3.12\n"
                "- yt-dlp لتحميل الفيديوهات\n"
                "- Google Speech Recognition\n",
                parse_mode='Markdown'
            )
        elif query.data == 'back':
            await self.start(update, context)

    async def handle_message(self, update: Update, context: CallbackContext) -> None:
        """Handle incoming YouTube links"""
        text = update.message.text
        
        # Extract URL from message (could be plain URL or command with URL)
        url = self.extract_youtube_url(text)
        
        if not url:
            await update.message.reply_text(
                "❌ هذا لا يبدو رابط يوتيوب صالح. الرجاء إرسال رابط يوتيوب صحيح.\n"
                "❌ That doesn't look like a valid YouTube URL. Please send a correct YouTube link.",
                parse_mode='Markdown'
            )
            return
        
        # Create unique job ID
        job_id = str(uuid4())
        self.active_transcriptions[job_id] = {
            'chat_id': update.message.chat_id,
            'message_id': update.message.message_id,
            'status': 'starting'
        }
        
        # Send initial response
        status_msg = await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="🔄 *جاري معالجة طلبك...*\n\n"
                 "⏳ الحالة الحالية: جاري تحميل الفيديو\n"
                 "📊 التقدم: 0%",
            parse_mode='Markdown'
        )
        
        # Store status message ID for updates
        self.active_transcriptions[job_id]['status_msg_id'] = status_msg.message_id
        
        # Start processing in a separate thread
        thread = threading.Thread(
            target=self.run_async_process_video,
            args=(update, context, url, job_id))
        thread.start()

    def extract_youtube_url(self, text: str) -> str:
        """Extract YouTube URL from text with proper regex"""
        # Check for command with URL
        if text.startswith('/transcribe'):
            parts = text.split()
            if len(parts) > 1:
                url = parts[1]
                if self.is_valid_youtube_url(url):
                    return url
                return None
        
        # Check if it's a plain URL
        if self.is_valid_youtube_url(text):
            return text
        
        return None

    def is_valid_youtube_url(self, url: str) -> bool:
        """Validate YouTube URL with robust regex"""
        youtube_regex = (
            r'(https?://)?(www\.)?'
            r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
            r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
        
        return re.match(youtube_regex, url) is not None

    def run_async_process_video(self, update: Update, context: CallbackContext, url: str, job_id: str):
        """Wrapper to run async function in a thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.process_video(update, context, url, job_id))
        loop.close()

    async def update_status(self, context: CallbackContext, job_id: str, status: str, progress: int) -> None:
        """Update the status message"""
        if job_id not in self.active_transcriptions:
            return
            
        chat_id = self.active_transcriptions[job_id]['chat_id']
        msg_id = self.active_transcriptions[job_id]['status_msg_id']
        
        status_texts = {
            'downloading': "جاري تحميل الفيديو",
            'converting': "جاري تحويل الصوت",
            'transcribing': "جاري تحويل الصوت إلى نص",
            'formatting': "جاري تنسيق النتائج",
            'complete': "اكتمل!"
        }
        
        # Create progress bar
        progress_bar = "[" + "■" * (progress // 10) + "□" * (10 - progress // 10) + "]"
        
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=f"🔄 *جاري معالجة طلبك...*\n\n"
                     f"⏳ الحالة الحالية: {status_texts.get(status, status)}\n"
                     f"📊 التقدم: {progress}% {progress_bar}",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error updating status: {e}")

    async def download_audio(self, url: str, job_id: str) -> tuple:
        """Download audio using yt-dlp with error handling"""
        try:
            ydl_opts['outtmpl'] = f'audio_{job_id}.%(ext)s'
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                audio_file = f"audio_{job_id}.wav"
                title = info.get('title', 'Unknown Title')
                duration = info.get('duration', 0)
                
            return audio_file, title, duration, None
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None, None, None, str(e)

    async def process_video(self, update: Update, context: CallbackContext, url: str, job_id: str) -> None:
        """Process the YouTube video"""
        try:
            chat_id = self.active_transcriptions[job_id]['chat_id']
            
            # Step 1: Download audio
            await self.update_status(context, job_id, 'downloading', 10)
            audio_file, title, duration, error = await self.download_audio(url, job_id)
            
            if error:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ فشل تحميل الفيديو: {error}\n"
                         f"❌ Failed to download video: {error}"
                )
                del self.active_transcriptions[job_id]
                return
            
            # Step 2: Transcribe
            await self.update_status(context, job_id, 'transcribing', 60)
            try:
                with sr.AudioFile(audio_file) as source:
                    audio_data = recognizer.record(source)
                    language = context.user_data.get('language', 'en-US')
                    transcript = recognizer.recognize_google(audio_data, language=language)
                
                # Clean up audio file
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            except sr.UnknownValueError:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ تعذر فهم الصوت. جودة الصوت قد تكون سيئة.\n"
                         "❌ Could not understand audio. Audio quality might be poor."
                )
                del self.active_transcriptions[job_id]
                return
            except Exception as e:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ فشل التحويل إلى نص: {str(e)}\n"
                         f"❌ Transcription failed: {str(e)}"
                )
                del self.active_transcriptions[job_id]
                return
            
            # Step 3: Format and send results
            await self.update_status(context, job_id, 'formatting', 90)
            
            formatted_transcript = self.format_transcript(transcript, context.user_data.get('language', 'en-US'))
            
            # Send results
            await self.update_status(context, job_id, 'complete', 100)
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=self.active_transcriptions[job_id]['status_msg_id']
            )
            
            # Send transcript with download option
            keyboard = [
                [InlineKeyboardButton("📥 Download as TXT", callback_data=f'download_{job_id}')]
            ]
            
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ *اكتمل التحويل!*\n\n"
                     f"📺 *عنوان الفيديو:* {title}\n"
                     f"⏱ *المدة:* {duration_str}\n\n"
                     f"📝 *النص:*\n\n"
                     f"{formatted_transcript[:3000]}...",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            # Store full transcript for download
            self.active_transcriptions[job_id]['transcript'] = formatted_transcript
            self.active_transcriptions[job_id]['video_title'] = title
            
        except Exception as e:
            logger.error(f"Error in processing thread: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ حدث خطأ غير متوقع: {str(e)}\n"
                     f"❌ An unexpected error occurred: {str(e)}"
            )
            if job_id in self.active_transcriptions:
                del self.active_transcriptions[job_id]

    def format_transcript(self, text: str, lang_code: str) -> str:
        """Format the raw transcript for better readability"""
        if 'ar' in lang_code:
            # Right-to-left formatting for Arabic
            formatted = text.replace(". ", ".\n\n")
            return formatted
        else:
            # Left-to-right formatting for other languages
            formatted = text.replace(". ", ".\n\n")
            return formatted

    def run(self):
        """Run the bot"""
        self.application.run_polling()
        logger.info("Bot is running...")

if __name__ == '__main__':
    # Install required packages if not already installed
    required_packages = ['python-telegram-bot', 'yt-dlp', 'pydub', 'SpeechRecognition', 'ffmpeg-python']
    
    bot = TranscriptionBot()
    bot.run()
