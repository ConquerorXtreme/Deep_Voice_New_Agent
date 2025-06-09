import os
import logging
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in environment.")

# Initialize OpenAI client
client = openai.OpenAI(api_key=api_key)

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="🎙️ [STT] %(asctime)s - %(levelname)s - %(message)s")

def transcribe_audio(file_path: str) -> str:
    """
    Transcribe an audio file using OpenAI Whisper API.

    Args:
        file_path (str): Path to the WAV audio file.

    Returns:
        str: Transcribed text or fallback message.
    """
    try:
        logger.info(f"📂 Reading audio file: {file_path}")
        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        text = response.text.strip()
        if not text:
            logger.warning("🟡 Transcription returned empty text.")
            return "Sorry, I couldn't hear you clearly."

        logger.info(f"✅ Transcription successful: {text}")
        return text

    except openai.APIError as api_err:
        logger.error(f"❌ OpenAI API Error during transcription: {api_err}")
    except Exception as e:
        logger.error(f"❌ Unexpected transcription error: {e}")

    return "Sorry, I couldn't understand the audio."

"""
import os
import logging
from dotenv import load_dotenv
import openai

# Load environment
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in environment.")

# Setup OpenAI client
client = openai.OpenAI(api_key=api_key)

# Setup logger
logging.basicConfig(level=logging.INFO, format="🔍 [STT] %(asctime)s - %(levelname)s - %(message)s")

def transcribe_audio(file_path: str) -> str:
    ""
    Transcribes a given audio file using OpenAI Whisper API.

    Args:
        file_path (str): Path to the audio file.

    Returns:
        str: Transcribed text or fallback message.
    ""
    try:
        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        text = response.text.strip()
        if not text:
            logging.warning("Transcription returned empty text.")
            return "Sorry, I couldn't hear you clearly."

        logging.info(f"Transcription successful: {text}")
        return text

    except openai.APIError as api_err:
        logging.error(f"OpenAI API Error during transcription: {api_err}")
    except Exception as e:
        logging.error(f"Unexpected transcription error: {e}")

    return "Sorry, I couldn't understand the audio.
"""
