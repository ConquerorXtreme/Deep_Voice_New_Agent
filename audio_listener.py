import threading
import queue
import sounddevice as sd
import numpy as np
import time
import logging

from vad_utils import VADAudio

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class AudioListener:
    def __init__(self, sample_rate=16000, frame_duration=30):
        self.sample_rate = sample_rate
        self.frame_duration = frame_duration  # ms
        self.bytes_per_sample = 2  # int16
        self.frame_size = int(self.sample_rate * self.frame_duration / 1000) * self.bytes_per_sample

        self.vad = VADAudio(sample_rate=self.sample_rate, frame_duration=self.frame_duration)
        self.audio_queue = queue.Queue()
        self.listening = False
        self.buffer = bytearray()
        self.thread = None
        self.speech_detected = threading.Event()

        self.MAX_BUFFER_LEN = self.frame_size * 100  # limit to ~3 seconds

    def _callback(self, indata, frames, time_info, status):
        if status:
            logger.warning(f"[SoundDevice] Status: {status}")

        audio_bytes = indata.tobytes()
        self.audio_queue.put(audio_bytes)

        # Append to buffer and limit growth
        self.buffer.extend(audio_bytes)
        if len(self.buffer) > self.MAX_BUFFER_LEN:
            self.buffer = self.buffer[-self.MAX_BUFFER_LEN:]

        # Set barge-in detection flag
        if len(audio_bytes) >= self.frame_size:
            chunk = audio_bytes[-self.frame_size:]
            if self.vad.is_speech(chunk):
                self.speech_detected.set()
            else:
                self.speech_detected.clear()

    def start_listening(self):
        if self.listening:
            logger.warning("⚠️ Already listening.")
            return

        self.buffer = bytearray()
        self.listening = True
        self.speech_detected.clear()
        logger.info("🎧 Audio listener started.")

        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def _listen_loop(self):
        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=0,
                dtype='int16',
                channels=1,
                callback=self._callback
            ):
                while self.listening:
                    time.sleep(0.01)
        except Exception as e:
            logger.error(f"❌ Audio input error: {e}")
            self.listening = False

    def stop_listening(self):
        if not self.listening:
            return
        logger.info("🛑 Stopping audio listener.")
        self.listening = False
        if self.thread and self.thread.is_alive():
            self.thread.join()

        # Clear queue and buffer
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()
        self.buffer = bytearray()

    def reset_buffer(self):
        self.buffer = bytearray()

    def get_audio_buffer(self) -> bytes:
        return bytes(self.buffer)

    def barge_in_detected(self) -> bool:
        return self.speech_detected.is_set()

    def listen_until_silence(self, silence_timeout=1.0, max_duration=10.0) -> bytes:
        """
        Uses VADAudio.vad_collector to stream and return a full speech segment.
        Ends on either max_duration or prolonged silence.
        """
        self.reset_buffer()
        self.start_listening()
        logger.info("🕒 Listening for speech segment using VAD collector...")

        collected_audio = bytearray()
        start_time = time.time()
        silence_start = None

        try:
            while time.time() - start_time < max_duration:
                try:
                    audio_chunk = self.audio_queue.get(timeout=0.1)
                    self.buffer.extend(audio_chunk)
                except queue.Empty:
                    continue

                if len(self.buffer) >= self.frame_size * 10:
                    frames = list(self.vad.frame_generator(bytes(self.buffer)))
                    for speech_bytes in self.vad.vad_collector(frames):
                        logger.info("✅ Speech segment collected.")
                        collected_audio.extend(speech_bytes)
                        self.buffer = bytearray()
                        silence_start = time.time()

                if silence_start and (time.time() - silence_start) >= silence_timeout:
                    logger.info("🛑 Silence timeout reached.")
                    break

        except Exception as e:
            logger.error(f"💥 Error during listen: {e}")

        self.stop_listening()
        return bytes(collected_audio)


if __name__ == "__main__":
    listener = AudioListener()
    print("Say something...")
    audio = listener.listen_until_silence()
    print(f"Captured {len(audio)} bytes of audio.")

"""
import threading
import queue
import sounddevice as sd
import numpy as np
import time
import logging

from vad_utils import VADAudio

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class AudioListener:
    def __init__(self, sample_rate=16000, frame_duration=30):
        self.sample_rate = sample_rate
        self.frame_duration = frame_duration  # ms
        self.bytes_per_sample = 2  # int16
        self.frame_size = int(self.sample_rate * self.frame_duration / 1000) * self.bytes_per_sample

        self.vad = VADAudio(sample_rate=self.sample_rate, frame_duration=self.frame_duration)
        self.audio_queue = queue.Queue()
        self.listening = False
        self.buffer = bytearray()
        self.thread = None
        self.speech_detected = threading.Event()

    def _callback(self, indata, frames, time_info, status):
        if status:
            logger.warning(f"[SoundDevice] Status: {status}")

        audio_bytes = indata.tobytes()
        self.audio_queue.put(audio_bytes)

        if len(audio_bytes) >= self.frame_size:
            chunk = audio_bytes[-self.frame_size:]
            if self.vad.is_speech(chunk):
                self.speech_detected.set()
            else:
                self.speech_detected.clear()

    def start_listening(self):
        if self.listening:
            logger.warning("⚠️ Already listening.")
            return

        self.buffer = bytearray()
        self.listening = True
        self.speech_detected.clear()
        logger.info("🎧 Audio listener started.")

        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def _listen_loop(self):
        try:
            with sd.RawInputStream(samplerate=self.sample_rate,
                                   blocksize=0,
                                   dtype='int16',
                                   channels=1,
                                   callback=self._callback):
                while self.listening:
                    time.sleep(0.01)
        except Exception as e:
            logger.error(f"❌ Audio input error: {e}")
            self.listening = False

    def stop_listening(self):
        if not self.listening:
            return
        logger.info("🛑 Stopping audio listener.")
        self.listening = False
        if self.thread and self.thread.is_alive():
            self.thread.join()

    def reset_buffer(self):
        self.buffer = bytearray()

    def get_audio_buffer(self) -> bytes:
        return bytes(self.buffer)

    def barge_in_detected(self) -> bool:
        return self.speech_detected.is_set()

    def listen_until_silence(self, silence_timeout=1.0, max_duration=10.0) -> bytes:
        ""
        Uses VADAudio.vad_collector to stream and return a full speech segment.
        ""
        self.reset_buffer()
        self.start_listening()
        logger.info("🕒 Listening for speech segment using VAD collector...")

        collected_audio = bytearray()
        start_time = time.time()

        try:
            # Aggregate raw audio bytes from queue
            while time.time() - start_time < max_duration:
                try:
                    audio_chunk = self.audio_queue.get(timeout=0.1)
                    self.buffer.extend(audio_chunk)
                except queue.Empty:
                    continue

                # Once we have enough for VAD frames, process
                if len(self.buffer) >= self.frame_size * 10:
                    frames = list(self.vad.frame_generator(bytes(self.buffer)))
                    for speech_bytes in self.vad.vad_collector(frames):
                        logger.info("✅ Speech segment collected.")
                        collected_audio.extend(speech_bytes)
                        self.buffer = bytearray()  # Reset after yielding segment
                        self.stop_listening()
                        return bytes(collected_audio)

        except Exception as e:
            logger.error(f"💥 Error during listen: {e}")

        self.stop_listening()
        return bytes(collected_audio)"""

"""
import threading
import queue
import sounddevice as sd
import numpy as np
import time
import logging

from vad_utils import VADAudio

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class AudioListener:
    def __init__(self, sample_rate=16000, frame_duration=30):
        self.sample_rate = sample_rate
        self.frame_duration = frame_duration  # ms
        self.bytes_per_sample = 2  # int16
        self.frame_size = int(self.sample_rate * self.frame_duration / 1000) * self.bytes_per_sample

        self.vad = VADAudio(sample_rate=self.sample_rate, frame_duration=self.frame_duration)
        self.audio_queue = queue.Queue()
        self.listening = False
        self.speaking_event = threading.Event()
        self.buffer = bytearray()
        self.stream = None

    def _callback(self, indata, frames, time_info, status):
        if status:
            logger.warning(f"[SoundDevice] Status: {status}")

        audio_bytes = indata.tobytes()
        self.buffer.extend(audio_bytes)

        # VAD on the last frame-sized chunk only
        if len(audio_bytes) >= self.frame_size:
            chunk = audio_bytes[-self.frame_size:]
            if self.vad.is_speech(chunk):
                self.speaking_event.set()
            else:
                self.speaking_event.clear()

        self.audio_queue.put(audio_bytes)

    def start_listening(self):
        if self.listening:
            logger.warning("Already listening.")
            return

        self.buffer = bytearray()
        self.listening = True
        logger.info("🎧 Starting audio listener...")

        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def _listen_loop(self):
        try:
            with sd.RawInputStream(samplerate=self.sample_rate,
                                   blocksize=0,
                                   dtype='int16',
                                   channels=1,
                                   callback=self._callback):
                while self.listening:
                    time.sleep(0.05)
        except Exception as e:
            logger.error(f"❌ Audio input stream error: {e}")
            self.listening = False

    def stop_listening(self):
        logger.info("🛑 Stopping audio listener...")
        self.listening = False
        if hasattr(self, 'thread') and self.thread.is_alive():
            self.thread.join()

    def reset_buffer(self):
        self.buffer = bytearray()

    def get_audio_buffer(self) -> bytes:
        return bytes(self.buffer)

    def barge_in_detected(self) -> bool:
        return self.speaking_event.is_set()

    def listen_until_silence(self, silence_timeout=1.0, max_duration=10.0) -> bytes:
        self.reset_buffer()
        self.start_listening()
        logger.info("🕒 Listening for speech...")

        silence_start = None
        start_time = time.time()

        while True:
            if self.barge_in_detected():
                silence_start = None
            else:
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start >= silence_timeout:
                    break

            if time.time() - start_time > max_duration:
                logger.warning("⌛ Max listen duration reached.")
                break

            time.sleep(0.05)

        self.stop_listening()
        return self.get_audio_buffer()
"""