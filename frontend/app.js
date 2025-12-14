function app() {
    return {
        // State
        page: 'home', // home, transcript, dashboard
        showTutorial: false,
        dragover: false,
        uploading: false,

        // Recorder
        mediaRecorder: null,
        audioChunks: [],
        isRecording: false,
        recordingTime: 0,
        timerInterval: null,
        recordedBlob: null,
        recordingName: '',

        // Data
        transcripts: [], // All list
        recentTranscripts: [], // Queue list
        selectedTranscript: null,

        // Q&A
        questionList: [''],
        qaResults: [],
        qaLoading: false,

        init() {
            // Poll for updates
            this.fetchTranscripts();
            setInterval(() => {
                this.fetchTranscripts();
                if (this.selectedTranscript) {
                    this.fetchQA(this.selectedTranscript.id);
                }
            }, 5000); // 5 seconds poll
        },

        navigate(to) {
            this.page = to;
            if (to === 'dashboard') this.fetchTranscripts();
        },

        // --- API Calls ---

        async fetchTranscripts() {
            try {
                const res = await fetch('/api/transcripts');
                const data = await res.json();
                this.transcripts = data;

                // Recent: items that are queued, processing, or PENDING
                this.recentTranscripts = data.filter(t =>
                    t.status === 'pending' || t.status === 'queued' || t.status === 'processing' ||
                    (t.status === 'completed' && (new Date() - new Date(t.process_end)) < 600000) // Show completed for 10 mins
                );

                // Refresh specific view if open
                if (this.selectedTranscript) {
                    const fresh = data.find(t => t.id === this.selectedTranscript.id);
                    if (fresh) {
                        this.selectedTranscript = fresh; // Update text/status
                    }
                }
            } catch (e) {
                console.error("Fetch error", e);
            }
        },

        async startItem(id) {
            await fetch(`/api/transcripts/${id}/start`, { method: 'POST' });
            this.fetchTranscripts();
        },

        async retryItem(id) {
            await fetch(`/api/transcripts/${id}/retry`, { method: 'POST' });
            this.fetchTranscripts();
        },
        async retryItem(id) {
            await fetch(`/api/transcripts/${id}/retry`, { method: 'POST' });
            this.fetchTranscripts();
        },

        async deleteItem(id) {
            if (!confirm("Hapus file dan hasil transkrip ini permanen?")) return;
            try {
                const res = await fetch(`/api/transcripts/${id}`, { method: 'DELETE' });
                if (res.ok) {
                    this.selectedTranscript = null; // Clear view
                    this.fetchTranscripts();
                }
            } catch (e) {
                alert("Gagal menghapus.");
            }
        },

        // --- Upload Logic ---

        handleDrop(e) {
            this.dragover = false;
            const file = e.dataTransfer.files[0];
            if (file) this.handleFile(file);
        },

        async handleFile(file) {
            if (!file) return;
            this.uploading = true;

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });
                if (res.ok) {
                    // Success animation or feedback
                    this.fetchTranscripts();
                    this.navigate('transcript'); // Stay here to see queue
                } else if (res.status === 409) {
                    const err = await res.json();
                    alert(err.detail); // "File already exists"
                } else {
                    throw new Error("Upload failed");
                }
            } catch (e) {
                if (!e.message.includes("File already exists")) {
                    alert("Upload Failed: " + e.message);
                }
            } finally {
                this.uploading = false;
            }
        },

        // --- Recorder Logic ---

        async startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                this.mediaRecorder = new MediaRecorder(stream);
                this.audioChunks = [];

                this.mediaRecorder.ondataavailable = (e) => this.audioChunks.push(e.data);
                this.mediaRecorder.onstop = () => {
                    const blob = new Blob(this.audioChunks, { type: 'audio/wav' });
                    this.recordedBlob = blob;
                    const audioUrl = URL.createObjectURL(blob);
                    this.$refs.audioPreview.src = audioUrl;
                };

                this.mediaRecorder.start();
                this.isRecording = true;
                this.recordingTime = 0;
                this.timerInterval = setInterval(() => this.recordingTime++, 1000);
            } catch (e) {
                alert("Microphone access denied or not available.");
            }
        },

        stopRecording() {
            if (this.mediaRecorder) {
                this.mediaRecorder.stop();
                this.mediaRecorder.stream.getTracks().forEach(track => track.stop()); // Release mic
            }
            this.isRecording = false;
            clearInterval(this.timerInterval);
        },

        resetRecorder() {
            this.recordedBlob = null;
            this.recordingName = '';
            this.$refs.audioPreview.src = '';
        },

        async saveRecording(transcribe) {
            if (!this.recordedBlob) return;

            const name = this.recordingName.trim() || `Recording_${new Date().getTime()}`;
            const formData = new FormData();
            formData.append('file', this.recordedBlob, name + '.wav'); // Force wav ext for blob
            formData.append('filename', name);
            formData.append('transcribe', transcribe);

            try {
                const res = await fetch('/api/record', { method: 'POST', body: formData });
                if (res.ok) {
                    this.resetRecorder();
                    this.fetchTranscripts();
                }
            } catch (e) {
                alert("Save failed");
            }
        },

        formatTimer(seconds) {
            const m = Math.floor(seconds / 60).toString().padStart(2, '0');
            const s = (seconds % 60).toString().padStart(2, '0');
            return `${m}:${s}`;
        },

        // --- Dashboard / QA Logic ---

        selectTranscript(item) {
            this.selectedTranscript = item;
            this.questionList = ['']; // Reset questions
            this.fetchQA(item.id);
        },

        async fetchQA(id) {
            const res = await fetch(`/api/qa/${id}`);
            const data = await res.json();
            this.qaResults = data;
        },

        async submitQuestions() {
            if (!this.selectedTranscript) return;

            const questions = this.questionList.filter(q => q.trim() !== '');
            if (questions.length === 0) return;

            this.qaLoading = true;
            try {
                await fetch(`/api/qa/${this.selectedTranscript.id}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(questions)
                });

                // Clear inputs but keep results view open
                this.questionList = [''];
                this.fetchQA(this.selectedTranscript.id);
            } finally {
                this.qaLoading = false; // Just the submission spinner
            }
        },
        async deleteQA(id) {
            if (!confirm("Hapus pertanyaan ini?")) return;
            try {
                const res = await fetch(`/api/qa/${id}`, { method: 'DELETE' });
                if (res.ok) {
                    // Refresh data
                    this.fetchQA(this.selectedTranscript.id);
                }
            } catch (e) {
                alert("Gagal menghapus QA.");
            }
        },

        downloadQA() {
            if (!this.selectedTranscript) return;
            // Direct link to download
            window.open(`/api/transcripts/${this.selectedTranscript.id}/download_qa`, '_blank');
        }
    }
}
