import os
import logging
import base64
import uuid
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from flask import request as socket_request
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from stt1 import transcribe_audio
from llm import query_llm
from tts1 import generate_speech
from conversation_manager import ConversationManager

# Load environment variables and configure logging
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "secret!")
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["TTS_FOLDER"] = "tts_output"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["TTS_FOLDER"], exist_ok=True)

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
conv_manager = ConversationManager()

ALLOWED_EXTENSIONS = {"wav", "mp3", "m4a"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def session_wav_path() -> str:
    """
    Return a unique file path for the current WebSocket session.
    NOTE: Only valid inside SocketIO event handlers.
    """
    sid = socket_request.sid or uuid.uuid4().hex
    return os.path.join(app.config["UPLOAD_FOLDER"], f"{sid}.wav")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/voice")
def voice_interface():
    """Serve voice interface page (can reuse index.html)."""
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """
    REST endpoint to handle full audio file upload.
    Transcribes audio, queries LLM, generates TTS, returns results.
    """
    if "audio" not in request.files:
        return jsonify({"error": "No audio file uploaded"}), 400

    file = request.files["audio"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Invalid or missing file"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    logging.info(f"📥 File saved: {filepath}")

    transcription = transcribe_audio(filepath)
    logging.info(f"📝 Transcription: {transcription}")

    response_text = query_llm(transcription)
    logging.info(f"🤖 LLM Response: {response_text}")

    tts_path = generate_speech(response_text)
    if not tts_path:
        return jsonify({"error": "TTS generation failed"}), 500

    return jsonify({
        "transcription": transcription,
        "response": response_text,
        "audio_reply_url": f"/audio/{os.path.basename(tts_path)}"
    })


@app.route("/audio/<filename>")
def serve_audio(filename: str):
    """Serve TTS audio files."""
    return send_from_directory(app.config["TTS_FOLDER"], filename)


@app.route("/speak-once", methods=["POST"])
def speak_once():
    """
    REST endpoint to trigger a full-duplex conversation cycle once.
    """
    try:
        conv_manager.run_once()
        return jsonify({"status": "✅ Ran full-duplex conversation once."})
    except Exception as e:
        logging.exception("❌ Error during speak_once")
        return jsonify({"error": str(e)}), 500


@socketio.on("audio_chunk")
def handle_audio_chunk(data):
    """
    Append each base64-encoded audio chunk to a session WAV file.
    """
    chunk_b64 = data.get("chunk")
    if not chunk_b64:
        emit("error", {"message": "Missing audio chunk"})
        return

    try:
        wav_path = session_wav_path()
        audio = base64.b64decode(chunk_b64)
        with open(wav_path, "ab") as f:
            f.write(audio)
    except Exception as e:
        logging.exception(f"[{socket_request.sid}] Failed to save chunk")
        emit("error", {"message": str(e)})

@socketio.on("end_audio")
def handle_end_audio():
    sid = socket_request.sid or "unknown"

    # Check if this sid is already processing
    if processing_flags.get(sid, False):
        logging.info(f"[{sid}] Ignored end_audio event: already processing.")
        return  # Ignore this repeated event

    processing_flags[sid] = True  # Mark as processing

    wav_path = session_wav_path()
    try:
        logging.info(f"[{sid}] Processing complete audio: {wav_path}")
        transcription = transcribe_audio(wav_path)
        logging.info(f"[{sid}] Transcription: {transcription}")

        response = query_llm(transcription)
        logging.info(f"[{sid}] LLM response: {response}")

        tts_path = generate_speech(response)
        if not tts_path:
            emit("error", {"message": "TTS generation failed"})
            return

        with open(tts_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        emit("audio_reply", {
            "transcription": transcription,
            "response": response,
            "tts_audio": audio_b64
        })

    except Exception as e:
        logging.exception(f"[{sid}] Error during end_audio processing")
        emit("error", {"message": str(e)})

    finally:
        processing_flags[sid] = False  # Release the lock

        # Clean up session WAV file for next question
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                logging.warning(f"[{sid}] Could not delete {wav_path}")


@socketio.on("reset_conversation")
def reset_conversation():
    conv_manager.reset_history()
    emit("conversation_reset", {"message": "Conversation history cleared."})


if __name__ == "__main__":
    print("🚀 Starting REST + WebSocket voice agent…")
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
"""
import os
import logging
import base64
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from stt1 import transcribe_audio
from llm import query_llm
from tts1 import generate_speech
from conversation_manager import ConversationManager

# ✅ Load env and configure
load_dotenv()
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "secret!")
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["TTS_FOLDER"] = "tts_output"

UPLOAD_FOLDER = app.config["UPLOAD_FOLDER"]
TTS_FOLDER = app.config["TTS_FOLDER"]
ALLOWED_EXTENSIONS = {"wav", "mp3", "m4a"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TTS_FOLDER, exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")
conv_manager = ConversationManager()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_audio_chunk(data):
    path = os.path.join(UPLOAD_FOLDER, "temp_stream.wav")
    with open(path, "ab") as f:
        f.write(data)
    return path

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/voice")
def voice_interface():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file uploaded"}), 400

    file = request.files["audio"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        logging.info(f"📥 File saved: {filepath}")

        transcription = transcribe_audio(filepath)
        logging.info(f"📝 Transcription: {transcription}")

        response_text = query_llm(transcription)
        logging.info(f"🤖 LLM Response: {response_text}")

        tts_path = generate_speech(response_text)
        if tts_path is None:
            return jsonify({"error": "TTS generation failed"}), 500

        return jsonify({
            "transcription": transcription,
            "response": response_text,
            "audio_reply_url": f"/audio/{os.path.basename(tts_path)}"
        })

    return jsonify({"error": "Unsupported file format"}), 400

@app.route("/speak-once", methods=["POST"])
def speak_once():
    try:
        conv_manager.run_once()
        return jsonify({"status": "✅ Ran full-duplex conversation once."})
    except Exception as e:
        logging.exception("❌ Error during speak_once")
        return jsonify({"error": str(e)}), 500

@app.route("/audio/<filename>")
def serve_audio(filename):
    return send_from_directory(TTS_FOLDER, filename)

# ✅ WebSocket Handler
@socketio.on("audio_chunk")
def handle_audio_chunk(data):
    try:
        chunk = data.get("chunk")
        if not chunk:
            emit("error", {"message": "Missing audio chunk"})
            return

        audio_data = base64.b64decode(chunk)
        wav_path = save_audio_chunk(audio_data)

        transcription = transcribe_audio(wav_path)
        logging.info(f"📝 Transcribed: {transcription}")

        response = query_llm(transcription)
        logging.info(f"🤖 LLM: {response}")

        tts_path = generate_speech(response)
        if not tts_path:
            emit("error", {"message": "TTS generation failed"})
            return

        with open(tts_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        emit("audio_reply", {
            "response": response,
            "tts_audio": audio_b64
        })

        if os.path.exists(wav_path):
            os.remove(wav_path)


    except Exception as e:
        logging.exception("❌ Error processing chunk")
        emit("error", {"message": str(e)})

@socketio.on("reset_conversation")
def reset_conversation():
    conv_manager.reset()
    emit("conversation_reset", {"message": "Conversation reset."})

if __name__ == "__main__":
    print("🚀 Launching hybrid REST + WebSocket voice agent...")
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
"""
"""import os
import logging
from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename

# ✅ Logging setup
logging.basicConfig(level=logging.INFO)

# ✅ Dependency imports
print("✅ Flask imported")

print("✅ stt1.py import starting")
from stt1 import transcribe_audio
print("✅ stt1.py imported")

print("✅ llm.py import starting")
from llm import query_llm
print("✅ llm.py imported")

print("✅ tts1.py import starting")
from tts1 import generate_speech
print("✅ tts1.py imported")

print("✅ conversation_manager.py import starting")
from conversation_manager import ConversationManager
print("✅ conversation_manager.py imported")

# ✅ Config
UPLOAD_FOLDER = "uploads"
TTS_FOLDER = "tts_output"
ALLOWED_EXTENSIONS = {"wav", "mp3", "m4a"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["TTS_FOLDER"] = TTS_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TTS_FOLDER, exist_ok=True)

# ✅ Init Conversation Manager
conv_manager = ConversationManager()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ✅ Routes

@app.route("/")
def index():
    return "🎤 Conversational Voice Agent is running!"

@app.route("/voice")
def voice_interface():
    return render_template("index.html")  # Make sure templates/index.html exists

@app.route("/chat", methods=["POST"])
def chat():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file uploaded"}), 400

    file = request.files["audio"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        logging.info(f"📥 File saved: {filepath}")

        # 1. Transcribe
        transcription = transcribe_audio(filepath)
        logging.info(f"📝 Transcription: {transcription}")

        # 2. Get response from LLM
        response_text = query_llm(transcription)
        logging.info(f"🤖 LLM Response: {response_text}")

        # 3. Generate speech
        tts_path = generate_speech(response_text)
        if tts_path is None:
            return jsonify({"error": "TTS generation failed"}), 500

        return jsonify({
            "transcription": transcription,
            "response": response_text,
            "audio_reply_url": f"/audio/{os.path.basename(tts_path)}"
        })

    return jsonify({"error": "Unsupported file format"}), 400

@app.route("/speak-once", methods=["POST"])
def speak_once():
    ""
    Runs a full conversation cycle: listen → STT → LLM → TTS → playback
    Uses `ConversationManager.run_once()` with barge-in and memory.
    ""
    try:
        conv_manager.run_once()
        return jsonify({"status": "✅ Ran full-duplex conversation once."})
    except Exception as e:
        logging.exception("❌ Error during speak_once")
        return jsonify({"error": str(e)}), 500

@app.route("/audio/<filename>")
def serve_audio(filename):
    return send_from_directory(app.config["TTS_FOLDER"], filename)

# ✅ Entry point
if __name__ == "__main__":
    print("🚀 Launching Flask app...")
    app.run(debug=True, host="0.0.0.0", port=5000)"""

"""import os
from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename
import logging

# ✅ Logging setup
logging.basicConfig(level=logging.INFO)

# ✅ Dependency imports
print("✅ Flask imported")
print("✅ stt.py import starting")
from stt import transcribe_audio
print("✅ stt.py imported")

print("✅ llm.py import starting")
from llm import query_llm
print("✅ llm.py imported")

print("✅ tts.py import starting")
from tts import generate_speech
print("✅ tts.py imported")

# ✅ Config
UPLOAD_FOLDER = "uploads"
TTS_FOLDER = "tts_output"
ALLOWED_EXTENSIONS = {"wav", "mp3", "m4a"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["TTS_FOLDER"] = TTS_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TTS_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ✅ Routes

@app.route("/")
def index():
    return "🎤 Conversational Voice Agent is running!"

@app.route("/voice")
def voice_interface():
    return render_template("index.html")  # Make sure templates/index.html exists

@app.route("/chat", methods=["POST"])
def chat():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file uploaded"}), 400

    file = request.files["audio"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        logging.info(f"📥 File saved: {filepath}")

        # 1. Transcribe
        transcription = transcribe_audio(filepath)
        logging.info(f"📝 Transcription: {transcription}")

        # 2. Get response from LLM
        response_text = query_llm(transcription)
        logging.info(f"🤖 LLM Response: {response_text}")

        # 3. Generate speech
        tts_path = generate_speech(response_text)
        if tts_path is None:
            return jsonify({"error": "TTS generation failed"}), 500


        # ✅ Return everything
        return jsonify({
            "transcription": transcription,
            "response": response_text,
            "audio_reply_url": f"/audio/{os.path.basename(tts_path)}"
        })

    return jsonify({"error": "Unsupported file format"}), 400

@app.route("/audio/<filename>")
def serve_audio(filename):
    return send_from_directory(app.config["TTS_FOLDER"], filename)

# ✅ Entry point
if __name__ == "__main__":
    print("🚀 Launching Flask app...")
    app.run(debug=True, host="0.0.0.0", port=5000)
"""