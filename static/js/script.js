// This script replaces the existing JavaScript in your HTML file
// Add console logs for debugging
console.log('Script initialized');

// DOM Elements
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded');
    
    // Check if elements exist
    const uploadBtn = document.getElementById('upload-btn');
    console.log('Upload button exists:', !!uploadBtn);
    
    const audioFileInput = document.getElementById('audio-file');
    console.log('Audio file input exists:', !!audioFileInput);
    
    const fileInfo = document.getElementById('file-info');
    const progressBar = document.getElementById('progress-bar');
    const progress = document.getElementById('progress');
    const status = document.getElementById('status');

    const transcriptSection = document.getElementById('transcript-section');
    const transcriptContent = document.getElementById('transcript-content');
    const summarizeBtn = document.getElementById('summarize-btn');

    const summarySection = document.getElementById('summary-section');
    const summaryContent = document.getElementById('summary-content');
    const regenerateBtn = document.getElementById('regenerate-btn');
    
    // New summary control elements
    const wordCountInput = document.getElementById('word-count');
    const summaryStyleInput = document.getElementById('summary-style');
    const applySummarySettingsBtn = document.getElementById('apply-summary-settings');

    const chatSection = document.getElementById('chat-section');
    const chatHistory = document.getElementById('chat-history');
    const chatInputText = document.getElementById('chat-input-text');
    const sendQuestionBtn = document.getElementById('send-question');

    // Global variables
    let currentTranscript = '';
    let processing = false;
    let summarySettings = {
        wordCount: 100,
        style: 'overview'
    };
    let appliedSettings = null;

    // API endpoints (adjust these if your Flask server runs on a different port)
    const API_BASE_URL = 'http://localhost:5000/api';

    // Event listeners
    if (uploadBtn) {
        uploadBtn.addEventListener('click', () => {
            console.log('Upload button clicked');
            if (!processing) {
                audioFileInput.click();
            }
        });
    }

    if (audioFileInput) {
        audioFileInput.addEventListener('change', (e) => {
            console.log('File input changed');
            handleFileUpload(e);
        });
    }

    if (summarizeBtn) {
        summarizeBtn.addEventListener('click', () => {
            console.log('Summarize button clicked');
            summarizeTranscript();
        });
    }

    if (regenerateBtn) {
        regenerateBtn.addEventListener('click', () => {
            console.log('Regenerate button clicked');
            regenerateSummary();
        });
    }
    
    // New event listener for apply settings button
    if (applySummarySettingsBtn) {
        applySummarySettingsBtn.addEventListener('click', () => {
            console.log('Apply summary settings button clicked');
            applySummarySettings();
        });
    }

    if (sendQuestionBtn && chatInputText) {
        sendQuestionBtn.addEventListener('click', () => {
            console.log('Send question button clicked');
            sendQuestion();
        });
        
        chatInputText.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendQuestion();
            }
        });
    }
    
    // Set up change handlers for settings inputs
    setupSettingsChangeHandlers();

    // Helper Functions
    function showLoading() {
        const loading = document.createElement('div');
        loading.className = 'loading';
        loading.innerHTML = '<div></div><div></div><div></div>';
        return loading;
    }

    function showTranscriptLoading() {
        const loading = document.createElement('div');
        loading.className = 'transcript-loading';
        
        const wave = document.createElement('div');
        wave.className = 'transcript-wave';
        
        // Add 8 bars for the wave effect
        for (let i = 0; i < 8; i++) {
            const bar = document.createElement('div');
            bar.className = 'bar';
            wave.appendChild(bar);
        }
        
        const text = document.createElement('div');
        text.className = 'transcript-loading-text';
        text.innerHTML = '<span class="typing-animation">Transcribing audio...</span>';
        
        loading.appendChild(wave);
        loading.appendChild(text);
        
        return loading;
    }

    // File upload and processing
    async function handleFileUpload(e) {
        console.log('Handle file upload called');
        const file = e.target.files[0];
        if (!file) {
            console.log('No file selected');
            return;
        }
        
        console.log('File selected:', file.name, file.type, file.size);
        
        const validTypes = ['audio/mp3', 'audio/mpeg', 'audio/wav', 'audio/ogg'];
        if (!validTypes.includes(file.type)) {
            status.textContent = 'Error: Please upload a valid audio file (MP3, WAV, OGG)';
            console.log('Invalid file type:', file.type);
            return;
        }

        fileInfo.textContent = `File: ${file.name} (${formatFileSize(file.size)})`;
        status.textContent = 'Processing...';
        progressBar.style.display = 'block';
        processing = true;

        // Reset content sections
        if (transcriptSection) transcriptSection.style.display = 'none';
        if (summarySection) summarySection.style.display = 'none';
        if (chatSection) chatSection.style.display = 'none';
        
        // Show transcript loading animation
        if (transcriptSection && transcriptContent) {
            transcriptSection.style.display = 'block';
            transcriptContent.innerHTML = '';
            transcriptContent.appendChild(showTranscriptLoading());
        }

        // Start progress animation
        simulateProgress();
        
        try {
            // Create form data to send the file
            const formData = new FormData();
            formData.append('file', file);
            
            console.log('Sending file to backend...');
            
            // Send to backend for processing
            const response = await fetch(`${API_BASE_URL}/transcribe`, {
                method: 'POST',
                body: formData
            });
            
            console.log('Response received:', response.status);
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to transcribe audio');
            }
            
            const data = await response.json();
            console.log('Transcription completed');
            
            // Update progress to 100%
            progress.style.width = '100%';
            status.textContent = 'Transcription complete!';
            
            // Display the transcript
            currentTranscript = data.transcript;
            if (transcriptContent) {
                transcriptContent.innerHTML = '';
                transcriptContent.textContent = currentTranscript;
            }
            
            // Show chat section
            if (chatSection) chatSection.style.display = 'block';
            
            processing = false;
        } catch (error) {
            console.error('Error:', error);
            status.textContent = `Error: ${error.message}`;
            if (transcriptContent) {
                transcriptContent.innerHTML = '';
                transcriptContent.textContent = 'Failed to transcribe audio. Please try again.';
            }
            processing = false;
        }
    }

    function simulateProgress() {
        // This simulates progress while waiting for the actual transcription
        console.log('Simulating progress');
        const totalSteps = 95; // Stop at 95% until we get the actual response
        let currentStep = 0;
        
        const interval = setInterval(() => {
            if (!processing || currentStep >= totalSteps) {
                clearInterval(interval);
                return;
            }
            
            currentStep += 1;
            progress.style.width = `${currentStep}%`;
            
            if (currentStep < 30) {
                status.textContent = 'Removing silence...';
            } else if (currentStep < 60) {
                status.textContent = 'Processing audio...';
            } else if (currentStep < 90) {
                status.textContent = 'Transcribing...';
            }
        }, 100);
    }

    async function summarizeTranscript() {
        if (!currentTranscript || processing) return;
        
        summarizeBtn.disabled = true;
        summarizeBtn.textContent = 'Summarizing...';
        processing = true;
        
        // Clear previous summary
        summaryContent.innerHTML = '';
        
        // Add loading animation
        summaryContent.appendChild(showLoading());
        
        // Show summary section
        summarySection.style.display = 'block';
        
        try {
            const response = await fetch(`${API_BASE_URL}/summarize`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ transcript: currentTranscript })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to summarize transcript');
            }
            
            const data = await response.json();
            
            // Display the summary
            summaryContent.innerHTML = '';
            summaryContent.textContent = data.summary;
            
            // Add fade-out class to the summarize button
            summarizeBtn.classList.add('fade-out');
            
            // After the animation completes, actually hide the element
            setTimeout(() => {
                summarizeBtn.style.display = 'none';
            }, 500); // This should match the CSS transition duration
        } catch (error) {
            console.error('Error:', error);
            summaryContent.innerHTML = '';
            summaryContent.textContent = 'Failed to summarize transcript. Please try again.';
        } finally {
            summarizeBtn.disabled = false;
            processing = false;
        }
    }
    async function regenerateSummary() {
        if (!currentTranscript || processing) return;
        
        regenerateBtn.disabled = true;
        processing = true;
        
        // Get the current settings rather than using defaults
        const currentSettings = getSummarySettings();
        
        // Clear previous summary
        summaryContent.innerHTML = '';
        
        // Add loading animation
        summaryContent.appendChild(showLoading());
        
        try {
            // Send the current settings with the request
            const response = await fetch(`${API_BASE_URL}/summarize`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    transcript: currentTranscript,
                    wordCount: currentSettings.wordCount,
                    style: currentSettings.style
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to regenerate summary');
            }
            
            const data = await response.json();
            
            // Display the new summary
            summaryContent.innerHTML = '';
            summaryContent.textContent = data.summary;
        } catch (error) {
            console.error('Error:', error);
            summaryContent.innerHTML = '';
            summaryContent.textContent = 'Failed to regenerate summary. Please try again.';
        } finally {
            regenerateBtn.disabled = false;
            processing = false;
        }
    }

    // Get current summary settings
    function getSummarySettings() {
        if (wordCountInput && summaryStyleInput) {
            const wordCount = parseInt(wordCountInput.value) || 100;
            const style = summaryStyleInput.value.trim() || 'overview';
            
            summarySettings = {
                wordCount: wordCount,
                style: style
            };
        }
        
        return summarySettings;
    }

    // Apply summary settings
    async function applySummarySettings() {
        if (!currentTranscript || processing) return;
        
        // Get current settings
        const newSettings = getSummarySettings();
        console.log('Applying summary settings:', newSettings);
        
        // Disable the button while processing and change its appearance
        if (applySummarySettingsBtn) {
            applySummarySettingsBtn.disabled = true;
            applySummarySettingsBtn.classList.add('disabled');
        }
        
        processing = true;
        
        // Store existing content in case of error
        const oldContent = summaryContent.innerHTML;
        
        // Add loading animation to the summary content
        if (summaryContent) {
            summaryContent.innerHTML = '';
            summaryContent.appendChild(showLoading());
        }
        
        try {
            const response = await fetch(`${API_BASE_URL}/customize-summary`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    transcript: currentTranscript,
                    wordCount: newSettings.wordCount,
                    style: newSettings.style
                })
            });
            
            console.log('Customize summary response:', response.status);
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to customize summary');
            }
            
            const data = await response.json();
            console.log('Received customized summary response:', data);
            
            // Display the customized summary
            if (summaryContent) {
                summaryContent.innerHTML = '';
                summaryContent.textContent = data.summary;
            }
            
            // Change button to success state
            if (applySummarySettingsBtn) {
                applySummarySettingsBtn.disabled = false;
                applySummarySettingsBtn.classList.remove('disabled');
                applySummarySettingsBtn.classList.add('success');
                
                // Store the current settings as the applied settings
                appliedSettings = { ...newSettings };
                
                // After 1.5 seconds, change to inactive state
                setTimeout(() => {
                    applySummarySettingsBtn.classList.remove('success');
                    applySummarySettingsBtn.classList.add('inactive');
                }, 1500);
            }
            
        } catch (error) {
            console.error('Error customizing summary:', error);
            
            // Restore previous content on error
            if (summaryContent) {
                summaryContent.innerHTML = oldContent;
            }
            
            // Reset button state
            if (applySummarySettingsBtn) {
                applySummarySettingsBtn.disabled = false;
                applySummarySettingsBtn.classList.remove('disabled');
            }
        } finally {
            processing = false;
        }
    }

    // Add this handler to monitor changes in the settings inputs
    function setupSettingsChangeHandlers() {
        if (wordCountInput) {
            wordCountInput.addEventListener('input', handleSettingsChange);
        }
        
        if (summaryStyleInput) {
            summaryStyleInput.addEventListener('input', handleSettingsChange);
        }
    }

    // This function is called when any setting is changed
    function handleSettingsChange() {
        const currentSettings = getSummarySettings();
        
        // Check if current settings are different from applied settings
        const isDifferent = !appliedSettings || 
                            currentSettings.wordCount !== appliedSettings.wordCount || 
                            currentSettings.style !== appliedSettings.style;
        
        if (isDifferent && applySummarySettingsBtn) {
            // Settings have changed, reset the button to active state
            applySummarySettingsBtn.classList.remove('success', 'inactive');
        }
    }

    async function sendQuestion() {
        const questionText = chatInputText.value.trim();
        if (!questionText || processing || !currentTranscript) return;
        
        // Add user message to chat
        addMessageToChat(questionText, 'user');
        chatInputText.value = '';
        
        processing = true;
        
        // Add loading animation
        const aiMessageContainer = document.createElement('div');
        aiMessageContainer.className = 'chat-message ai-message';
        aiMessageContainer.appendChild(showLoading());
        chatHistory.appendChild(aiMessageContainer);
        
        // Scroll to bottom of chat
        chatHistory.scrollTop = chatHistory.scrollHeight;
        
        try {
            const response = await fetch(`${API_BASE_URL}/ask`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    transcript: currentTranscript,
                    question: questionText
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to get answer');
            }
            
            const data = await response.json();
            
            // Remove loading animation
            chatHistory.removeChild(aiMessageContainer);
            
            // Add AI response to chat
            addMessageToChat(data.answer, 'ai');
        } catch (error) {
            console.error('Error:', error);
            
            // Remove loading animation
            chatHistory.removeChild(aiMessageContainer);
            
            // Add error message
            addMessageToChat('Sorry, I couldn\'t process your question. Please try again.', 'ai');
        } finally {
            processing = false;
        }
    }

    function addMessageToChat(message, sender) {
        const messageElement = document.createElement('div');
        messageElement.className = `chat-message ${sender}-message`;
        messageElement.textContent = message;
        chatHistory.appendChild(messageElement);
        
        // Scroll to bottom of chat
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
});