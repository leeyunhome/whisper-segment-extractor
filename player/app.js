document.addEventListener('DOMContentLoaded', () => {
    const audio = document.getElementById('audio-player');
    const container = document.getElementById('script-container');
    const loadBtn = document.getElementById('load-btn');
    const fileInput = document.getElementById('file-input');
    const fileTitle = document.getElementById('file-title');

    let scriptData = [];
    let currentLineIndex = -1;

    loadBtn.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        if (files.length === 0) return;

        let jsonData = null;
        let audioFile = null;

        // To handle cases where both files are selected simultaneously
        let jsonProcessed = false;
        let audioProcessed = false;

        const checkAndLoad = () => {
            if (jsonProcessed && audioProcessed) {
                if (jsonData) loadPlayer(jsonData, audioFile);
            } else if (jsonProcessed && !audioFile && jsonData) {
                // JSON is loaded, but no audio file was selected
                loadPlayer(jsonData, null);
            } else if (audioProcessed && !jsonData && audioFile) {
                // Audio is loaded, but no JSON file was selected
                // This case might need a different handling, e.g., prompt user for JSON
                console.warn("MP3 file loaded, but no JSON script provided.");
            }
        };

        files.forEach(file => {
            if (file.name.endsWith('.json')) {
                const reader = new FileReader();
                reader.onload = (event) => {
                    try {
                        jsonData = JSON.parse(event.target.result);
                        fileTitle.textContent = file.name; // Display JSON file name
                        jsonProcessed = true;
                        checkAndLoad();
                    } catch (err) {
                        alert('JSON 파일 형식이 올바르지 않습니다.');
                        jsonProcessed = true; // Mark as processed even if error
                        checkAndLoad();
                    }
                };
                reader.readAsText(file);
            } else if (file.name.endsWith('.mp3')) {
                audioFile = file;
                audioProcessed = true;
                checkAndLoad();
            } else {
                console.warn(`Unsupported file type: ${file.name}`);
                // If we have other files, we still need to mark them as processed
                // to ensure checkAndLoad is eventually called for the relevant files.
                // For simplicity, we'll just count them as processed for now.
                if (!file.name.endsWith('.json') && !file.name.endsWith('.mp3')) {
                    // This is a simple way to ensure checkAndLoad runs if only one type of file is present
                    // and other files are ignored. A more robust solution might track specific file types.
                    if (!jsonProcessed && !audioProcessed) { // If neither JSON nor audio is found yet
                        // This branch might need refinement based on exact requirements for mixed inputs
                    }
                }
            }
        });

        // If only one type of file was selected (e.g., only JSON or only MP3)
        // and the other type is not expected, ensure checkAndLoad is called.
        // This is a fallback for cases where only one file type is present.
        if (files.length === 1) {
            if (files[0].name.endsWith('.json')) {
                audioProcessed = true; // No audio file, so mark audio as "processed" (not found)
            } else if (files[0].name.endsWith('.mp3')) {
                jsonProcessed = true; // No JSON file, so mark JSON as "processed" (not found)
            }
            checkAndLoad();
        }
    });

    function loadPlayer(data, audioFile) {
        if (data.script) {
            scriptData = data.script;
            renderScript();
        }

        if (audioFile) {
            const url = URL.createObjectURL(audioFile);
            audio.src = url;
            console.log("Audio loaded from file:", audioFile.name);
        } else if (data.audio) {
            // JSON은 있는데 오디오 파일이 아직 선택 안 된 경우 알림
            console.log("Audio recommended:", data.audio);
            if (!audio.src || audio.src === '') {
                // scriptContainer에 안내 메시지 추가 가능
            }
        }
    }

    function renderScript() {
        container.innerHTML = '';
        scriptData.forEach((line, index) => {
            const div = document.createElement('div');
            div.className = 'script-line';
            div.innerHTML = `<span>${line.text}</span>`;
            div.dataset.index = index;
            div.dataset.start = line.start;

            div.addEventListener('click', () => {
                audio.currentTime = line.start;
                audio.play();
            });

            container.appendChild(div);
        });
    }

    audio.addEventListener('timeupdate', () => {
        const time = audio.currentTime;
        const activeIndex = scriptData.findIndex(line => time >= line.start && time < line.end);

        if (activeIndex !== -1 && activeIndex !== currentLineIndex) {
            // 이전 활성 라인 해제
            const prevLine = container.querySelector(`[data-index="${currentLineIndex}"]`);
            if (prevLine) prevLine.classList.remove('active');

            // 현재 활성 라인 설정
            const currentLine = container.querySelector(`[data-index="${activeIndex}"]`);
            if (currentLine) {
                currentLine.classList.add('active');
                currentLine.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }

            currentLineIndex = activeIndex;
        }
    });
});
