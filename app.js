const socket = io();

const recordBtn = document.getElementById("recordBtn");
const btnIcon = document.getElementById("btnIcon");
const btnLabel = document.getElementById("btnLabel");
const statusEl = document.getElementById("status");
const transcriptionEl = document.getElementById("transcription");
const responseEl = document.getElementById("response");
const audioReplyEl = document.getElementById("audioReply");
const audioSection = document.getElementById("audioSection");
const micVisual = document.getElementById("micVisual");
const loadingSpinner = document.getElementById("loadingSpinner");

let mediaRecorder;
let streaming = false;

recordBtn.addEventListener("click", async () => {
  if (streaming) {
    stopRecording();
  } else {
    await startRecording();
  }
});

async function startRecording() {
  resetUI();

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (e) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64data = reader.result.split(',')[1];
        socket.emit("audio_chunk", { chunk: base64data });
      };
      reader.readAsDataURL(e.data);
    };

    mediaRecorder.onstop = () => {
      toggleRecordingUI(false);
    };

    mediaRecorder.start(1000); // 1 second chunks
    streaming = true;
    toggleRecordingUI(true);
  } catch (err) {
    statusEl.textContent = `❌ Error accessing microphone: ${err.message}`;
  }
}

function stopRecording() {
  mediaRecorder.stop();
  streaming = false;
  recordBtn.disabled = true;
  updateBtn("⏳", "Processing…");
  statusEl.textContent = "Processing audio…";
  loadingSpinner.hidden = false;
  micVisual.style.animationPlayState = "paused";
}

function resetUI() {
  transcriptionEl.textContent = "";
  responseEl.textContent = "";
  audioReplyEl.src = "";
  audioSection.hidden = true;
  loadingSpinner.hidden = true;
}

function toggleRecordingUI(isRecording) {
  recordBtn.disabled = false;
  updateBtn(isRecording ? "⏹️" : "🎙️", isRecording ? "Stop Recording" : "Start Recording");
  micVisual.style.animationPlayState = isRecording ? "running" : "paused";
  statusEl.textContent = isRecording ? "Recording… Click again to stop." : "Click “Start Recording” to speak";
  recordBtn.setAttribute("aria-pressed", isRecording.toString());
}

function updateBtn(icon, label) {
  btnIcon.textContent = icon;
  btnLabel.textContent = label;
}

// Handle server events
socket.on("audio_reply", (data) => {
  loadingSpinner.hidden = true;
  if (data.response) responseEl.textContent = data.response;
  if (data.tts_audio) {
    audioReplyEl.src = `data:audio/wav;base64,${data.tts_audio}`;
    audioSection.hidden = false;
    setTimeout(() => audioReplyEl.play(), 200);
  }
});

socket.on("error", (data) => {
  loadingSpinner.hidden = true;
  toggleRecordingUI(false);
  statusEl.textContent = `❌ Error: ${data.message}`;
});

socket.on("connect", () => {
  console.log("✅ Connected to server");
});

socket.on("disconnect", () => {
  console.log("⚠️ Disconnected from server");
  statusEl.textContent = "⚠️ Disconnected from server";
  if (streaming) {
    mediaRecorder.stop();
    streaming = false;
    toggleRecordingUI(false);
  }
});