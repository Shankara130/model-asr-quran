const socket = io();

const testerInput = document.getElementById("tester");
const testMode = document.getElementById("testMode");
const modeDescription = document.getElementById("modeDescription");
const verseSelection = document.getElementById("verseSelection");
const surahInput = document.getElementById("surah");
const ayahInput = document.getElementById("ayah");

const startButton = document.getElementById("startButton");
const stopButton = document.getElementById("stopButton");
const statusText = document.getElementById("status");

const verseTargetCard = document.getElementById("verseTargetCard");
const targetText = document.getElementById("targetText");
const targetPhoneme = document.getElementById("targetPhoneme");
const audioReference = document.getElementById("audioReference");
const referenceAudio = document.getElementById("referenceAudio");

const letterTargetCard = document.getElementById("letterTargetCard");
const letterProgress = document.getElementById("letterProgress");
const letterDisplay = document.getElementById("letterDisplay");
const letterName = document.getElementById("letterName");
const latinHint = document.getElementById("latinHint");
const letterWarning = document.getElementById("letterWarning");
const previousLetter = document.getElementById("previousLetter");
const resetLetter = document.getElementById("resetLetter");
const nextLetter = document.getElementById("nextLetter");

const livePhoneme = document.getElementById("livePhoneme");
const resultCard = document.getElementById("resultCard");
const similarityValue = document.getElementById("similarityValue");
const cerValue = document.getElementById("cerValue");
const matchValue = document.getElementById("matchValue");
const resultTarget = document.getElementById("resultTarget");
const finalPhoneme = document.getElementById("finalPhoneme");
const differenceList = document.getElementById("differenceList");

const feedbackCorrect = document.getElementById("feedbackCorrect");
const feedbackIncorrect = document.getElementById("feedbackIncorrect");
const feedbackOptions = document.getElementById("feedbackOptions");
const submitFeedback = document.getElementById("submitFeedback");
const manualFeedback = document.getElementById("manualFeedback");
const feedbackStatus = document.getElementById("feedbackStatus");

let audioContext;
let microphone;
let processor;
let mediaStream;

let currentTestMode = "random";
let currentLetterIndex = 0;
let currentLetterTest = null;

function downsampleBuffer(buffer, inputRate, outputRate) {
    if (inputRate === outputRate) {
        return new Float32Array(buffer);
    }

    const ratio = inputRate / outputRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);
    let resultIndex = 0;
    let inputIndex = 0;

    while (resultIndex < result.length) {
        const nextInputIndex = Math.round((resultIndex + 1) * ratio);
        let sum = 0;
        let count = 0;

        for (
            let index = inputIndex;
            index < nextInputIndex && index < buffer.length;
            index++
        ) {
            sum += buffer[index];
            count++;
        }

        result[resultIndex] = count > 0 ? sum / count : 0;
        resultIndex++;
        inputIndex = nextInputIndex;
    }

    return result;
}

async function startMicrophone() {
    mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
            channelCount: 1,
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
        },
    });

    audioContext = new AudioContext();
    microphone = audioContext.createMediaStreamSource(mediaStream);
    processor = audioContext.createScriptProcessor(4096, 1, 1);

    processor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0);
        const audio16k = downsampleBuffer(
            input,
            audioContext.sampleRate,
            16000
        );
        socket.emit("audio_chunk", audio16k.buffer);
    };

    microphone.connect(processor);
    processor.connect(audioContext.destination);
}

function stopMicrophone() {
    if (processor) {
        processor.disconnect();
        processor.onaudioprocess = null;
    }
    if (microphone) microphone.disconnect();
    if (mediaStream) mediaStream.getTracks().forEach((track) => track.stop());
    if (audioContext) audioContext.close();

    processor = null;
    microphone = null;
    mediaStream = null;
    audioContext = null;
}

function readablePhoneme(text) {
    return (text || "")
        .replace(/ۦ{2,}/g, "ي")
        .replace(/ۥ{2,}/g, "و")
        .replaceAll("للَاهِ", "اللَّهِ")
        .replaceAll("ررَ", "الرَّ")
        .replaceAll("ررِ", "الرِّ")
        .replaceAll("ررُ", "الرُّ");
}

function updateReferenceAudio(surah, ayah) {
    referenceAudio.pause();
    referenceAudio.currentTime = 0;
    referenceAudio.src = `/audio-reference/${surah}/${ayah}`;
    referenceAudio.load();
}

function resetFeedbackForm() {
    feedbackOptions.hidden = true;
    feedbackStatus.textContent = "";
    manualFeedback.value = "";
    document
        .querySelectorAll('input[name="feedbackIssue"]')
        .forEach((checkbox) => {
            checkbox.checked = false;
        });
}

function clearResult() {
    resultCard.hidden = true;
    differenceList.innerHTML = "";
    resultTarget.textContent = "-";
    finalPhoneme.textContent = "-";
    livePhoneme.textContent = "-";
    resetFeedbackForm();
}

function applyVerse(verse) {
    surahInput.value = verse.surah;
    ayahInput.value = verse.ayah;
    targetText.textContent = verse.target_text;
    targetPhoneme.textContent = readablePhoneme(verse.target_phoneme);
    updateReferenceAudio(verse.surah, verse.ayah);
    clearResult();
    statusText.textContent = "Ayat siap. Dengarkan contoh atau mulai rekam.";
}

function applyLetterTest(data) {
    currentLetterTest = data;
    currentLetterIndex = data.index;

    letterProgress.textContent = `Bunyi ${data.index + 1} dari ${data.total}`;
    letterDisplay.textContent = data.display;
    letterName.textContent = `${data.letter_name} — ${data.harakat}`;
    latinHint.textContent = `Petunjuk bunyi: ${data.latin_hint}`;
    letterWarning.textContent = data.warning;

    previousLetter.disabled = data.is_first;
    nextLetter.disabled = data.is_last;
    clearResult();
    statusText.textContent = "Baca satu bunyi dengan jelas, lalu hentikan rekaman.";
}

function requestLetterTest(index) {
    statusText.textContent = "Menyiapkan target huruf...";
    socket.emit("get_letter_test", { index });
}

function updateModeUI() {
    currentTestMode = testMode.value;
    const isRandom = currentTestMode === "random";
    const isSelectedVerse = currentTestMode === "ayat_pilihan";
    const isLetterTest = currentTestMode === "uji_huruf";

    verseSelection.hidden = isLetterTest;
    verseTargetCard.hidden = isLetterTest;
    letterTargetCard.hidden = !isLetterTest;
    audioReference.hidden = isLetterTest;

    surahInput.disabled = isRandom;
    ayahInput.disabled = isRandom;

    clearResult();

    if (isRandom) {
        modeDescription.textContent = "Sistem memilih ayat secara otomatis.";
        statusText.textContent = "Memilih ayat secara acak...";
        socket.emit("get_random_verse");
    } else if (isSelectedVerse) {
        modeDescription.textContent = "Masukkan nomor surah dan ayat yang ingin diuji.";
        statusText.textContent = "Silakan pilih surah dan ayat.";
    } else {
        modeDescription.textContent = "Baca a-i-u, ba-bi-bu, dan seterusnya. Hasil tiap bunyi disimpan untuk mengukur akurasi model.";
        requestLetterTest(currentLetterIndex);
    }
}

function readableDifferenceTitle(type) {
    if (type === "delete") {
        return "Bunyi target tidak terdeteksi";
    }

    if (type === "replace") {
        return "Bunyi terbaca berbeda";
    }

    if (type === "insert") {
        return "Ada bunyi tambahan";
    }

    return "Perbedaan fonem";
}

function readableDifferenceContent(difference) {
    if (difference.type === "replace") {
        return (
            `${readablePhoneme(difference.target)} → ` +
            `${readablePhoneme(difference.detected)}`
        );
    }

    if (difference.type === "delete") {
        return readablePhoneme(difference.target) || "-";
    }

    if (difference.type === "insert") {
        return readablePhoneme(difference.detected) || "-";
    }

    return "-";
}

function renderWordResults(
    wordResults,
    fallbackDifferences,
    targetText
) {
    differenceList.innerHTML = "";

    if (!Array.isArray(wordResults) || wordResults.length === 0) {
        renderDifferences(fallbackDifferences);
        return;
    }

    const arabicWords = String(targetText || "")
        .trim()
        .split(/\s+/);

    const problematicWords = wordResults.filter(
        (word) => !word.exact_match
    );

    if (problematicWords.length === 0) {
        differenceList.innerHTML = `
            <div class="difference-item"
                 style="border-color:#15803d;background:#f0fdf4;">
                <strong>Bacaan sesuai</strong>
                <div style="margin-top:4px;">
                    Tidak ada perbedaan bunyi yang terdeteksi.
                </div>
            </div>
        `;
        return;
    }

    problematicWords.forEach((word) => {
        const item = document.createElement("div");
        item.className = "word-result-item";

        const arabicWord =
            arabicWords[word.word_index] ||
            `Bagian ${word.word_index + 1}`;

        const feedbackItems =
            Array.isArray(word.tajwid_feedback) &&
                word.tajwid_feedback.length > 0
                ? word.tajwid_feedback
                : (word.differences || []).map((difference) => ({
                    message: readableDifferenceContent(difference),
                }));

        const issues = feedbackItems
            .map((feedback) => `
                <div class="word-issue">
                    <span class="issue-icon">!</span>
                    <span>
                        ${feedback.message || "Bunyi perlu diperiksa."}
                    </span>
                </div>
            `)
            .join("");

        item.innerHTML = `
            <div class="word-result-header">
                <div>
                    <div class="word-label">Kata yang perlu diperiksa</div>
                    <div class="arabic word-arabic">
                        ${arabicWord}
                    </div>
                </div>

                <div class="word-score">
                    ${Number(word.similarity).toFixed(0)}%
                </div>
            </div>

            <div class="word-comparison">
                <div>
                    <small>Seharusnya</small>
                    <div class="phoneme">
                        ${readablePhoneme(word.target)}
                    </div>
                </div>

                <div class="comparison-arrow">→</div>

                <div>
                    <small>Terdeteksi</small>
                    <div class="phoneme">
                        ${readablePhoneme(word.detected) || "-"}
                    </div>
                </div>
            </div>

            <div class="word-issues">
                ${issues}
            </div>
        `;

        differenceList.appendChild(item);
    });
}

function renderDifferences(differences) {
    differenceList.innerHTML = "";

    if (!differences || differences.length === 0) {
        differenceList.innerHTML = `
            <div class="difference-item" style="border-color:#15803d;background:#f0fdf4;">
                Tidak ada perbedaan fonem yang terdeteksi.
            </div>
        `;
        return;
    }

    differences.forEach((difference) => {
        const item = document.createElement("div");
        item.classList.add("difference-item", `difference-${difference.type}`);

        let title = "Perbedaan fonem";
        let content = "";

        if (difference.type === "delete") {
            title = "Bunyi target tidak terdeteksi";
            content = readablePhoneme(difference.target);
        } else if (difference.type === "replace") {
            title = "Bunyi terbaca berbeda";
            content = `${readablePhoneme(difference.target)} → ${readablePhoneme(difference.detected)}`;
        } else if (difference.type === "insert") {
            title = "Ada bunyi tambahan";
            content = readablePhoneme(difference.detected);
        }

        item.innerHTML = `
            <div class="diff-label">${title}</div>
            <div class="diff-text">${content || "-"}</div>
        `;
        differenceList.appendChild(item);
    });
}

testMode.addEventListener("change", updateModeUI);
previousLetter.addEventListener("click", () => requestLetterTest(currentLetterIndex - 1));
nextLetter.addEventListener("click", () => requestLetterTest(currentLetterIndex + 1));
resetLetter.addEventListener("click", () => requestLetterTest(0));

startButton.addEventListener("click", () => {
    clearResult();
    statusText.textContent = "Menyiapkan sesi rekaman...";

    const payload = {
        tester: testerInput.value,
        test_mode: currentTestMode,
    };

    if (currentTestMode === "uji_huruf") {
        if (!currentLetterTest) {
            statusText.textContent = "Target huruf belum tersedia.";
            return;
        }
        payload.letter_index = currentLetterIndex;
    } else {
        payload.surah = Number(surahInput.value);
        payload.ayah = Number(ayahInput.value);
    }

    socket.emit("start_recording", payload);
});

stopButton.addEventListener("click", () => {
    stopMicrophone();
    statusText.textContent = "Menyelesaikan hasil...";
    stopButton.disabled = true;
    socket.emit("recording_stopped");
});

socket.on("session_started", async (data) => {
    if (data.test_mode === "uji_huruf") {
        letterDisplay.textContent = data.target_text;
        letterWarning.textContent = data.warning;
    } else {
        targetText.textContent = data.target_text;
        targetPhoneme.textContent = readablePhoneme(data.target_phoneme);
        updateReferenceAudio(data.surah, data.ayah);
    }

    try {
        await startMicrophone();
        startButton.disabled = true;
        stopButton.disabled = false;
        statusText.textContent = data.test_mode === "uji_huruf"
            ? "Mikrofon aktif. Baca bunyi satu kali dengan jelas."
            : "Mikrofon aktif. Silakan membaca ayat.";
    } catch (error) {
        console.error(error);
        statusText.textContent = "Mikrofon gagal diakses.";
        startButton.disabled = false;
    }
});

socket.on("phoneme_result", (data) => {
    livePhoneme.textContent = readablePhoneme(data.text) || "-";
});

socket.on("phoneme_final", (data) => {
    statusText.textContent = "Pengujian selesai dan hasil sudah tersimpan.";
    resultCard.hidden = false;
    similarityValue.textContent = `${data.similarity.toFixed(2)}%`;
    cerValue.textContent = `${(data.cer * 100).toFixed(2)}%`;

    if (data.exact_match) {
        matchValue.textContent = "Sesuai";
        matchValue.className = "score-value good";
    } else {
        matchValue.textContent = "Perlu dicek";
        matchValue.className = "score-value bad";
    }

    resultTarget.textContent = readablePhoneme(data.target_phoneme) || "-";
    finalPhoneme.textContent =
        readablePhoneme(data.prediction_clean || data.prediction) ||
        "(tidak ada bunyi terdeteksi)";

    renderWordResults(
        data.word_results,
        data.differences,
        data.target_text
    );

    startButton.disabled = false;
    stopButton.disabled = true;
});

socket.on("session_error", (data) => {
    stopMicrophone();
    statusText.textContent = data.message || "Terjadi kesalahan.";
    startButton.disabled = false;
    stopButton.disabled = true;
});

feedbackCorrect.addEventListener("click", () => {
    feedbackCorrect.disabled = true;
    feedbackIncorrect.disabled = true;
    feedbackStatus.textContent = "Mengirim feedback...";
    socket.emit("submit_feedback", {
        status: "sesuai",
        issues: [],
        note: "",
    });
});

feedbackIncorrect.addEventListener("click", () => {
    feedbackOptions.hidden = false;
    feedbackStatus.textContent = "Pilih masalah yang ditemukan.";
});

submitFeedback.addEventListener("click", () => {
    const selectedIssues = Array.from(
        document.querySelectorAll('input[name="feedbackIssue"]:checked')
    ).map((checkbox) => checkbox.value);

    if (selectedIssues.length === 0 && !manualFeedback.value.trim()) {
        feedbackStatus.textContent = "Pilih minimal satu masalah atau isi catatan.";
        return;
    }

    submitFeedback.disabled = true;
    feedbackStatus.textContent = "Mengirim feedback...";
    socket.emit("submit_feedback", {
        status: "tidak_sesuai",
        issues: selectedIssues,
        note: manualFeedback.value.trim(),
    });
});

socket.on("feedback_saved", (data) => {
    feedbackCorrect.disabled = false;
    feedbackIncorrect.disabled = false;
    submitFeedback.disabled = false;

    if (data.retry_letter_test) {
        applyLetterTest(data.retry_letter_test);
        statusText.textContent = "Feedback tersimpan. Silakan ulangi bunyi yang sama.";
        return;
    }

    if (data.next_letter_test) {
        applyLetterTest(data.next_letter_test);
        statusText.textContent = "Feedback tersimpan. Lanjut ke bunyi berikutnya.";
        return;
    }

    if (data.letter_test_complete) {
        resultCard.hidden = true;
        statusText.textContent = "Seluruh rangkaian uji huruf selesai. Data sudah tersimpan.";
        return;
    }

    if (data.retry_verse) {
        applyVerse(data.retry_verse);
        statusText.textContent = "Feedback tersimpan. Silakan ulangi ayat yang sama.";
        return;
    }

    if (data.next_verse) {
        applyVerse(data.next_verse);
        return;
    }

    feedbackStatus.textContent = data.message || "Feedback berhasil disimpan.";
});

socket.on("feedback_error", (data) => {
    feedbackStatus.textContent = data.message || "Feedback gagal disimpan.";
    feedbackCorrect.disabled = false;
    feedbackIncorrect.disabled = false;
    submitFeedback.disabled = false;
});

socket.on("random_verse", applyVerse);
socket.on("letter_test", applyLetterTest);
socket.on("letter_test_error", (data) => {
    statusText.textContent = data.message || "Target huruf gagal dimuat.";
});

socket.on("connect", updateModeUI);
