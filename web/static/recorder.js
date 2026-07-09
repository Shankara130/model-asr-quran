const socket = io();

const startButton = document.getElementById("startButton");
const stopButton = document.getElementById("stopButton");
const statusText = document.getElementById("status");

let audioContext;
let microphone;
let processor;
let mediaStream;

startButton.addEventListener("click", async () => {
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: true
        });

        audioContext = new AudioContext();

        microphone = audioContext.createMediaStreamSource(mediaStream);

        processor = audioContext.createScriptProcessor(
            4096,
            1,
            1
        );

        processor.onaudioprocess = (event) => {
            const samples = event.inputBuffer.getChannelData(0);

            const audioChunk = new Float32Array(samples);

            socket.emit("audio_chunk", audioChunk.buffer);
        };

        microphone.connect(processor);
        processor.connect(audioContext.destination);

        startButton.disabled = true;
        stopButton.disabled = false;

        statusText.textContent = "Mikrofon aktif. Silakan membaca.";
    } catch (error) {
        console.error(error);
        statusText.textContent = "Mikrofon gagal diakses.";
    }
});

stopButton.addEventListener("click", () => {
    if (processor) {
        processor.disconnect();
    }

    if (microphone) {
        microphone.disconnect();
    }

    if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop());
    }

    if (audioContext) {
        audioContext.close();
    }

    socket.emit("recording_stopped");

    startButton.disabled = false;
    stopButton.disabled = true;

    statusText.textContent = "Rekaman dihentikan.";
});