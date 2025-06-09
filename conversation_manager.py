import threading
import time
import tempfile
import os
import logging
import collections

from audio_listener import AudioListener
from stt1 import transcribe_audio
from llm import query_llm
from tts1 import speak_text, stop_playback

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ConversationManager:
    def __init__(self):
        # session_id -> dict with keys: history, listener, stop_tts_flag, lock
        self.sessions = {}

    def get_session(self, session_id):
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "history": [],
                "listener": AudioListener(),
                "stop_tts_flag": threading.Event(),
                "lock": threading.Lock(),
                "sliding_window": collections.deque(maxlen=10),
                "silence_start": None,
                "playback_thread": None,
            }
        return self.sessions[session_id]

    def reset_history(self, session_id):
        session = self.get_session(session_id)
        with session["lock"]:
            session["history"] = []

    def _is_followup(self, new_input: str, last_input: str) -> bool:
        if not last_input:
            return False
        keywords = ["also", "and", "by the way", "what about", "continue"]
        return any(kw in new_input.lower() for kw in keywords)

    def _save_audio_buffer_to_file(self, audio_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
            tmpfile.write(audio_bytes)
            return tmpfile.name

    def _monitor_barge_in(self, session_id):
        session = self.get_session(session_id)
        flag = session["stop_tts_flag"]
        listener = session["listener"]

        while not flag.is_set():
            if listener.barge_in_detected():
                logger.info(f"🔇 [{session_id}] Barge-in detected: interrupting TTS...")
                stop_playback()
                flag.set()
                break
            time.sleep(0.05)

    def _play_response_async(self, session_id, text: str):
        """Play TTS response asynchronously with barge-in monitoring."""

        def playback():
            session = self.get_session(session_id)
            session["stop_tts_flag"].clear()
            monitor_thread = threading.Thread(target=self._monitor_barge_in, args=(session_id,), daemon=True)
            monitor_thread.start()

            try:
                speak_text(text)  # Blocking call to play TTS
            except Exception as e:
                logger.error(f"❌ [{session_id}] Error during TTS playback: {e}")
            finally:
                session["stop_tts_flag"].set()

        session = self.get_session(session_id)
        # If previous playback thread is still alive, wait or stop it
        if session["playback_thread"] and session["playback_thread"].is_alive():
            logger.info(f"⚠️ [{session_id}] Waiting for previous playback to finish...")
            session["stop_tts_flag"].set()
            session["playback_thread"].join()

        playback_thread = threading.Thread(target=playback, daemon=True)
        session["playback_thread"] = playback_thread
        playback_thread.start()

    def process_turn(self, session_id, audio_bytes: bytes):
        session = self.get_session(session_id)
        with session["lock"]:
            logger.info(f"📥 [{session_id}] Processing new audio turn...")
            wav_path = self._save_audio_buffer_to_file(audio_bytes)

            try:
                transcription = transcribe_audio(wav_path)
                logger.info(f"📝 [{session_id}] Transcription: {transcription}")

                # Check if follow-up continuation
                if session["history"] and session["history"][-1]["role"] == "user":
                    prev = session["history"][-1]["content"]
                    if self._is_followup(transcription, prev):
                        transcription = prev + " " + transcription
                        session["history"].pop()

                session["history"].append({"role": "user", "content": transcription})
                response = query_llm(transcription)
                logger.info(f"🤖 [{session_id}] LLM Response: {response}")
                session["history"].append({"role": "assistant", "content": response})

            finally:
                try:
                    os.remove(wav_path)
                except Exception as e:
                    logger.warning(f"⚠️ [{session_id}] Could not delete temp wav file: {e}")

        # Play TTS outside the lock
        self._play_response_async(session_id, response)

    def run_loop(self, session_id):
        """
        Starts the continuous listening loop for a session.
        This method blocks; run in a dedicated thread per session.
        """

        session = self.get_session(session_id)
        listener = session["listener"]
        sliding_window = session["sliding_window"]
        frame_duration_sec = listener.frame_duration / 1000.0

        logger.info(f"🚀 [{session_id}] Starting conversational loop...")
        listener.start_listening()
        buffer = bytearray()
        silence_start = None

        try:
            while listener.listening:
                try:
                    audio_chunk = listener.audio_queue.get(timeout=1)
                    buffer.extend(audio_chunk)
                except Exception:
                    continue  # Timeout or empty queue

                is_speech = listener.barge_in_detected()
                sliding_window.append(is_speech)

                if any(sliding_window):
                    silence_start = None  # speech ongoing
                else:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start >= 0.8:
                        # End of utterance detected by silence
                        listener.reset_buffer()
                        sliding_window.clear()
                        audio_data = bytes(buffer)
                        buffer.clear()

                        logger.info(f"🛑 [{session_id}] Silence detected, processing turn...")
                        self.process_turn(session_id, audio_data)
                        silence_start = None

                time.sleep(frame_duration_sec)

        except KeyboardInterrupt:
            logger.info(f"🛑 [{session_id}] Conversation loop interrupted by user.")

        finally:
            listener.stop_listening()
            logger.info(f"🛑 [{session_id}] Listener stopped.")

    def stop_session(self, session_id):
        """Gracefully stop the listener and playback for a session."""
        session = self.sessions.get(session_id)
        if not session:
            return

        session["listener"].stop_listening()
        if session["playback_thread"] and session["playback_thread"].is_alive():
            session["stop_tts_flag"].set()
            session["playback_thread"].join()
        logger.info(f"🛑 [{session_id}] Session stopped.")


if __name__ == "__main__":
    # Example of running a single session for local testing
    conv_mgr = ConversationManager()
    test_session = "localtest"

    # Run listening loop in a thread so main thread isn't blocked
    thread = threading.Thread(target=conv_mgr.run_loop, args=(test_session,), daemon=True)
    thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        conv_mgr.stop_session(test_session)
        logger.info("Exiting main.")

"""
import threading
import time
import tempfile
import os
import logging

from audio_listener import AudioListener
from stt1 import transcribe_audio
from llm import query_llm
from tts1 import speak_text, stop_playback

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ConversationManager:
    def __init__(self):
        self.listener = AudioListener()
        self.playback_thread = None
        self.stop_tts_flag = threading.Event()
        self.history = []

    def _monitor_barge_in(self):
        #""Monitor if user starts speaking during TTS to interrupt playback.""
        while not self.stop_tts_flag.is_set():
            if self.listener.barge_in_detected():
                logger.info("🔇 Barge-in detected: interrupting TTS...")
                stop_playback()
                self.stop_tts_flag.set()
                break
            time.sleep(0.1)

    def _play_response(self, text: str):
        #""Play the TTS response while listening for barge-in.""
        self.stop_tts_flag.clear()
        monitor_thread = threading.Thread(target=self._monitor_barge_in, daemon=True)
        monitor_thread.start()
        speak_text(text)  # Blocking call
        self.stop_tts_flag.set()

    def _save_audio_buffer_to_file(self, audio_bytes: bytes) -> str:
        #""Save the audio buffer to a temporary WAV file.""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
            tmpfile.write(audio_bytes)
            return tmpfile.name

    def _is_followup(self, new_input: str, last_input: str) -> bool:
        #""Decide if new input is a continuation of last input.""
        if not last_input:
            return False
        keywords = ["also", "and", "by the way", "what about", "continue"]
        return any(kw in new_input.lower() for kw in keywords)

    def reset_history(self):
        self.history = []

    def run_once(self):
        #""Listen → transcribe → respond (interruption-aware).""
        logger.info("🎙️ Listening for user input...")
        audio = self.listener.listen_until_silence()

        logger.info("📥 Capturing complete. Processing...")
        wav_path = self._save_audio_buffer_to_file(audio)

        try:
            transcription = transcribe_audio(wav_path)
            logger.info(f"📝 Transcription: {transcription}")

            # 🧠 Merge if continuation
            if self.history and self.history[-1]["role"] == "user":
                prev = self.history[-1]["content"]
                if self._is_followup(transcription, prev):
                    transcription = prev + " " + transcription
                    self.history.pop()

            self.history.append({"role": "user", "content": transcription})
            response = query_llm(transcription)
            logger.info(f"🤖 LLM Response: {response}")
            self.history.append({"role": "assistant", "content": response})

            self._play_response(response)

        finally:
            os.remove(wav_path)

    def run_loop(self):
        #""Continuously listen/respond until manually stopped.""
        logger.info("🚀 Entering full-duplex conversational loop...")
        try:
            while True:
                self.run_once()
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("🛑 Exiting conversation loop by KeyboardInterrupt")"""


