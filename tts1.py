import os
import logging
import uuid
import traceback
import re
from dotenv import load_dotenv
from typing import Union

# Load environment variables
load_dotenv()

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="🎤 [TTS] %(asctime)s - %(levelname)s - %(message)s")

# Attempt Smallest.ai SDK import
try:
    from smallestai.waves import WavesClient
except ImportError:
    raise ImportError("❌ Smallest.ai SDK not found. Install via: pip install smallestai")

# Load API Key
SMALLEST_API_KEY = os.getenv("SMALLEST_API_KEY")
if not SMALLEST_API_KEY:
    raise EnvironmentError("❌ SMALLEST_API_KEY not found in environment variables.")

# Output directory for TTS files
TTS_OUTPUT_DIR = "tts_output"
os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)


def clean_text_for_tts(text: str) -> str:
    """Cleans LLM-style markdown and formatting artifacts from text before TTS."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # Bold
    text = re.sub(r"\*(.*?)\*", r"\1", text)      # Italic
    text = re.sub(r"`(.*?)`", r"\1", text)        # Inline code
    text = re.sub(r"#+\s*", "", text)             # Headers
    return text.strip()


def generate_speech(
    text: str,
    save_as: Union[str, None] = None,
    *,
    model: str = "lightning",
    voice_id: str = "emily",
    sample_rate: int = 24000,
    speed: float = 1.0,
    consistency: float = 0.5,
    similarity: float = 0.0,
    enhancement: bool = False,
    return_metadata: bool = False,
    playback: bool = False
) -> Union[str, dict, None]:
    """
    Generate speech from input text using Smallest.ai's WavesClient.

    Args:
        text (str): Input text for synthesis.
        save_as (str, optional): Output filename. Defaults to UUID.
        model (str): TTS model ('lightning' or 'lightning-large').
        voice_id (str): Speaker voice ID.
        sample_rate (int): Audio sample rate in Hz.
        speed (float): Speech speed multiplier.
        consistency (float): Applies only to 'lightning-large'.
        similarity (float): Applies only to 'lightning-large'.
        enhancement (bool): Applies only to 'lightning-large'.
        return_metadata (bool): Return metadata dictionary.
        playback (bool): Placeholder for future playback implementation.

    Returns:
        Union[str, dict, None]: Path to saved audio or metadata dict, or None on failure.
    """
    if not text.strip():
        logger.warning("⚠️ Skipped TTS due to empty input.")
        return None

    clean_text = clean_text_for_tts(text)

    try:
        client = WavesClient(api_key=SMALLEST_API_KEY)
    except Exception as e:
        logger.error(f"❌ Failed to initialize WavesClient: {e}")
        logger.debug(traceback.format_exc())
        return None

    filename = save_as if save_as else f"{uuid.uuid4().hex}.wav"
    output_path = os.path.join(TTS_OUTPUT_DIR, filename)

    synth_kwargs = {
        "text": clean_text,
        "save_as": output_path,
        "sample_rate": sample_rate,
        "speed": speed,
        "voice_id": voice_id,
        "model": model
    }

    if model == "lightning-large":
        synth_kwargs.update({
            "consistency": consistency,
            "similarity": similarity,
            "enhancement": enhancement,
        })

    logger.info(f"🧠 Generating TTS → {filename} | model={model}, voice={voice_id}")

    try:
        client.synthesize(**synth_kwargs)

        if not os.path.isfile(output_path):
            logger.error(f"❌ Synth failed: Output file not found at {output_path}")
            return None

        logger.info(f"✅ TTS saved: {output_path}")

        if playback:
            logger.warning("🔊 Playback is enabled but not implemented yet.")

        if return_metadata:
            return {
                "output_path": output_path,
                "model": model,
                "voice_id": voice_id,
                "sample_rate": sample_rate,
                "speed": speed,
                "enhancement": enhancement if model == "lightning-large" else None,
            }

        return output_path

    except Exception as e:
        logger.error(f"❌ Error during TTS synthesis: {e}")
        logger.debug(traceback.format_exc())
        return None


# Alias for common interface
speak_text = generate_speech


def stop_playback():
    """
    Placeholder for stopping audio playback if implemented later.
    """
    logger.info("🔇 stop_playback() not implemented.")

"""
import os
import logging
import uuid
import traceback
import re
from dotenv import load_dotenv
from typing import Union

# Load environment variables
load_dotenv()

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="🎤 [TTS] %(asctime)s - %(levelname)s - %(message)s")

# Try importing Smallest.ai SDK
try:
    from smallestai.waves import WavesClient
except ImportError:
    raise ImportError("❌ smallestai SDK not found. Install it with: pip install smallestai")

# Read API key from .env
SMALLEST_API_KEY = os.getenv("SMALLEST_API_KEY")
if not SMALLEST_API_KEY:
    raise EnvironmentError("SMALLEST_API_KEY not found in environment.")

# Output directory
TTS_OUTPUT_DIR = "tts_output"
os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)


def clean_text_for_tts(text: str) -> str:
    
    #Strip markdown and formatting artifacts from LLM responses for clean speech.
    
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # Bold
    text = re.sub(r"\*(.*?)\*", r"\1", text)      # Italic
    text = re.sub(r"`(.*?)`", r"\1", text)        # Inline code
    text = re.sub(r"#+\s*", "", text)             # Headers
    return text.strip()


def generate_speech(
    text: str,
    save_as: Union[str, None] = None,
    *,
    model: str = "lightning",
    voice_id: str = "emily",
    sample_rate: int = 24000,
    speed: float = 1.0,
    consistency: float = 0.5,
    similarity: float = 0.0,
    enhancement: bool = False,
    return_metadata: bool = False,
    playback: bool = False  # Optional playback flag
) -> Union[str, dict, None]:
    ""
    Generate speech from text using Smallest.ai's TTS (WavesClient).

    Args:
        text (str): Input text.
        save_as (str | None): Optional output filename.
        model (str): "lightning" or "lightning-large".
        voice_id (str): Voice name like "emily", "raj", etc.
        sample_rate (int): Audio quality.
        speed (float): Speed multiplier.
        consistency (float): Only for lightning-large.
        similarity (float): Only for lightning-large.
        enhancement (bool): Only for lightning-large.
        return_metadata (bool): Return metadata if True.
        playback (bool): If True, auto-play audio (future use).

    Returns:
        str | dict | None: File path or metadata, or None on error.
    ""
    if not text.strip():
        logger.warning("⚠️ Empty input text for TTS.")
        return None

    clean_text = clean_text_for_tts(text)

    try:
        client = WavesClient(api_key=SMALLEST_API_KEY)
    except Exception as e:
        logger.error(f"❌ Failed to initialize Smallest.ai client: {e}")
        logger.debug(traceback.format_exc())
        return None

    filename = save_as if save_as else f"{uuid.uuid4().hex}.wav"
    output_path = os.path.join(TTS_OUTPUT_DIR, filename)

    synth_kwargs = {
        "text": clean_text,
        "save_as": output_path,
        "sample_rate": sample_rate,
        "speed": speed,
        "voice_id": voice_id,
        "model": model
    }

    if model == "lightning-large":
        synth_kwargs.update({
            "consistency": consistency,
            "similarity": similarity,
            "enhancement": enhancement,
        })

    logger.info(f"🧠 Synthesizing speech → {filename} | voice={voice_id}, model={model}")

    try:
        client.synthesize(**synth_kwargs)

        if not os.path.isfile(output_path):
            logger.error(f"❌ Synthesis failed: Output file not found at {output_path}")
            return None

        logger.info(f"✅ TTS saved: {output_path}")

        # Optional: Audio playback can be added here
        if playback:
            logger.warning("🔊 Playback is enabled but not yet implemented.")

        if return_metadata:
            return {
                "output_path": output_path,
                "model": model,
                "voice_id": voice_id,
                "sample_rate": sample_rate,
                "speed": speed,
                "enhancement": enhancement if model == "lightning-large" else None,
            }

        return output_path

    except Exception as e:
        logger.error(f"❌ Error during TTS synthesis: {e}")
        logger.debug(traceback.format_exc())
        return None
speak_text = generate_speech

def stop_playback():
    logger.info("🔇 stop_playback() is not implemented yet.")
"""