import webrtcvad
import collections
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Frame:
    def __init__(self, bytes_data: bytes, timestamp: float, duration: float):
        self.bytes = bytes_data
        self.timestamp = timestamp
        self.duration = duration


class VADAudio:
    def __init__(self, sample_rate=16000, frame_duration=30, aggressiveness=2):
        """
        Args:
            sample_rate (int): Audio sample rate (typically 16000 Hz).
            frame_duration (int): Frame size in milliseconds (10, 20, or 30 ms).
            aggressiveness (int): VAD aggressiveness (0-3).
        """
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        self.frame_duration = frame_duration
        self.frame_size = int(sample_rate * frame_duration / 1000) * 2  # 16-bit PCM = 2 bytes
        self.padding_ms = 300  # padding for end-of-speech detection
        self.num_padding_frames = int(self.padding_ms / frame_duration)
        self.ring_buffer = collections.deque(maxlen=self.num_padding_frames)

    def is_speech(self, audio_chunk: bytes) -> bool:
        """Check if a chunk of audio is speech."""
        return self.vad.is_speech(audio_chunk, self.sample_rate)

    def frame_generator(self, audio: bytes):
        """Split raw audio into timestamped frames."""
        n = self.frame_size
        offset = 0
        timestamp = 0.0
        duration = float(n) / (2 * self.sample_rate)
        while offset + n <= len(audio):
            yield Frame(audio[offset:offset + n], timestamp, duration)
            timestamp += duration
            offset += n

    def vad_collector(self, frames, ratio=0.9):
        """
        Collect voiced segments from audio frames using VAD.

        Args:
            frames: Iterable of audio frames.
            ratio: Proportion of non-speech frames to detect end of speech.

        Yields:
            Contiguous segments of voiced audio as raw bytes.
        """
        triggered = False
        voiced_frames = []
        num_voiced = int(self.num_padding_frames * ratio)

        for frame in frames:
            is_speech = self.is_speech(frame.bytes)

            if not triggered:
                self.ring_buffer.append((frame, is_speech))
                num_voiced_frames = sum(1 for _, speech in self.ring_buffer if speech)
                if num_voiced_frames > 0.8 * self.ring_buffer.maxlen:
                    triggered = True
                    logger.info("🎙️ Speech started")
                    voiced_frames.extend(f for f, _ in self.ring_buffer)
                    self.ring_buffer.clear()
            else:
                voiced_frames.append(frame)
                self.ring_buffer.append((frame, is_speech))
                num_unvoiced = sum(1 for _, speech in self.ring_buffer if not speech)
                if num_unvoiced > num_voiced:
                    logger.info("🔇 Speech ended")
                    yield b''.join(f.bytes for f in voiced_frames)
                    triggered = False
                    self.ring_buffer.clear()
                    voiced_frames = []

        if voiced_frames:
            yield b''.join(f.bytes for f in voiced_frames)

"""
import webrtcvad
import collections
import numpy as np
import sys
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Frame:
    def __init__(self, bytes_data: bytes, timestamp: float, duration: float):
        self.bytes = bytes_data
        self.timestamp = timestamp
        self.duration = duration


class VADAudio:
    def __init__(self, sample_rate=16000, frame_duration=30, aggressiveness=2):
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        self.frame_duration = frame_duration  # ms
        self.frame_size = int(sample_rate * frame_duration / 1000) * 2  # bytes (16-bit)
        self.padding_ms = 300  # duration to look for stop of speech
        self.num_padding_frames = int(self.padding_ms / frame_duration)
        self.ring_buffer = collections.deque(maxlen=self.num_padding_frames)

    def is_speech(self, audio_chunk: bytes) -> bool:
        return self.vad.is_speech(audio_chunk, self.sample_rate)

    def frame_generator(self, audio: bytes):
        "#"Yields audio frames from raw audio.""
        n = self.frame_size
        offset = 0
        timestamp = 0.0
        duration = float(n) / (2 * self.sample_rate)
        while offset + n <= len(audio):
            yield Frame(audio[offset:offset + n], timestamp, duration)
            timestamp += duration
            offset += n

    def vad_collector(self, frames, ratio=0.9):
        
        #Yields segments of audio containing speech.
        #ratio = 0.9 means 90% of padding frames must be non-speech to trigger stop.
        
        triggered = False
        voiced_frames = []
        num_voiced = int(self.num_padding_frames * ratio)

        for frame in frames:
            is_speech = self.is_speech(frame.bytes)

            if not triggered:
                self.ring_buffer.append((frame, is_speech))
                num_voiced_frames = len([f for f, speech in self.ring_buffer if speech])
                if num_voiced_frames > 0.8 * self.ring_buffer.maxlen:
                    triggered = True
                    logger.info("🎙️ Speech started")
                    for f, _ in self.ring_buffer:
                        voiced_frames.append(f)
                    self.ring_buffer.clear()
            else:
                voiced_frames.append(frame)
                self.ring_buffer.append((frame, is_speech))
                num_unvoiced = len([f for f, speech in self.ring_buffer if not speech])
                if num_unvoiced > num_voiced:
                    logger.info("🔇 Speech ended")
                    yield b''.join([f.bytes for f in voiced_frames])
                    triggered = False
                    self.ring_buffer.clear()
                    voiced_frames = []

        if voiced_frames:
            yield b''.join([f.bytes for f in voiced_frames])
"""