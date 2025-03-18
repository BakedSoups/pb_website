console.log('Script initialized');

// DOM Elements
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded');
    
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
    
    const wordCountInput = document.getElementById('word-count');
    const summaryStyleInput = document.getElementById('summary-style');
    const applySummarySettingsBtn = document.getElementById('apply-summary-settings');

    const chatSection = document.getElementById('chat-section');
    const chatHistory = document.getElementById('chat-history');
    const chatInputText = document.getElementById('chat-input-text');
    const sendQuestionBtn = document.getElementById('send-question');

    let currentTranscript = '';
    let processing = false;
    let summarySettings = {
        wordCount: 100,
        style: 'overview'
    };
    let appliedSettings = null;
    let uploadStartTime = null;
    let currentJobId = null;
    let jobCheckInterval = null;

    const API_BASE_URL = '/api';  // Use relative path for production

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
    
    setupSettingsChangeHandlers();

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

    function showLargeFileProcessingMessage(jobId) {
        const container = document.createElement('div');
        container.style.textAlign = 'center';
        container.style.padding = '2rem 1rem';
        
        const title = document.createElement('h3');
        title.textContent = 'Processing Large Audio File';
        title.style.marginBottom = '1rem';
        title.style.color = '#4F46E5';
        
        const infoText = document.createElement('p');
        infoText.innerHTML = `Your file is being processed in the background.<br>This may take several minutes for large files.`;
        infoText.style.marginBottom = '1.5rem';
        
        const jobIdText = document.createElement('p');
        jobIdText.textContent = `Job ID: ${jobId}`;
        jobIdText.style.fontSize = '0.875rem';
        jobIdText.style.color = '#6B7280';
        jobIdText.style.marginBottom = '1rem';
        
        const statusBox = document.createElement('div');
        statusBox.id = 'job-status-box';
        statusBox.style.padding = '1rem';
        statusBox.style.backgroundColor = '#F3F4F6';
        statusBox.style.borderRadius = '0.5rem';
        statusBox.style.marginBottom = '1.5rem';
        statusBox.textContent = 'Initializing...';
        
        const progressCircle = document.createElement('div');
        progressCircle.className = 'loading';
        progressCircle.style.margin = '1.5rem auto';
        
        container.appendChild(title);
        container.appendChild(infoText);
        container.appendChild(jobIdText);
        container.appendChild(statusBox);
        container.appendChild(progressCircle);
        
        return container;
    }
    async function handleFileUpload(e) {
        console.log('Handle file upload called');
        const file = e.target.files[0];
        if (!file) {
            console.log('No file selected');
            return;
        }
        
        console.log('File selected:', file.name, file.type, file.size);
        
        const fileSizeMB = file.size / (1024 * 1024);
        const isVeryLargeFile = fileSizeMB > 100; // Files > 100MB need special treatment
        const isLargeFile = fileSizeMB > 50; // Files > 50MB use the large file endpoint
        
        if (isVeryLargeFile) {
            console.log(`Very large file detected: ${fileSizeMB.toFixed(2)} MB`);
            const confirmed = confirm(`This file is very large (${fileSizeMB.toFixed(2)} MB). Would you like to process only the first 30 minutes? This is recommended for better reliability.`);
            if (confirmed) {
                console.log('User chose to trim the file to 30 minutes');
            } else {
                console.log('User chose to process the entire file');
            }
        } else if (isLargeFile) {
            console.log(`Large file detected: ${fileSizeMB.toFixed(2)} MB`);
            const confirmed = confirm(`This file is large (${fileSizeMB.toFixed(2)} MB) and will be processed in the background. This may take several minutes. Continue?`);
            if (!confirmed) {
                fileInfo.textContent = 'No file selected';
                return;
            }
        }
        
        const validTypes = ['audio/mp3', 'audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/x-m4a', 'audio/m4a', 'audio/webm'];
        const validExtensions = ['.mp3', '.wav', '.ogg', '.m4a', '.webm', '.mp4'];
        
        const hasValidType = validTypes.includes(file.type);
        const hasValidExtension = validExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
        
        if (!hasValidType && !hasValidExtension) {
            status.textContent = 'Error: Please upload a valid audio file (MP3, WAV, OGG, M4A)';
            console.log('Invalid file type:', file.type, 'with filename:', file.name);
            return;
        }

        fileInfo.textContent = `File: ${file.name} (${formatFileSize(file.size)})`;
        status.textContent = 'Processing...';
        progressBar.style.display = 'block';
        progress.style.width = '0%';
        processing = true;
        uploadStartTime = Date.now();

        if (transcriptSection) transcriptSection.style.display = 'none';
        if (summarySection) summarySection.style.display = 'none';
        if (chatSection) chatSection.style.display = 'none';
        
        if (transcriptSection && transcriptContent) {
            transcriptSection.style.display = 'block';
            transcriptContent.innerHTML = '';
            transcriptContent.appendChild(showTranscriptLoading());
        }

        simulateProgress(isLargeFile);
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            if (isVeryLargeFile && confirm(`This file is very large (${fileSizeMB.toFixed(2)} MB). Would you like to process only the first 30 minutes? This is recommended for better reliability.`)) {
                formData.append('trim_duration', '1800'); // 30 minutes in seconds
            }
            
            console.log('Sending file to backend...');
            
            const endpoint = isLargeFile ? `${API_BASE_URL}/transcribe-large` : `${API_BASE_URL}/transcribe`;
            console.log('Using endpoint:', endpoint);
            
            const controller = new AbortController();
            const timeoutDuration = isLargeFile ? 60000 : 300000; // 1 minute for large files (just for initial response), 5 minutes for small files
            const timeoutId = setTimeout(() => controller.abort(), timeoutDuration);
            
            let response;
            try {
                console.log('Request headers:', {
                    method: 'POST',
                    formDataKeys: [...formData.keys()]
                });
                
                response = await fetch(endpoint, {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                });
                clearTimeout(timeoutId);

                console.log('Response status:', response.status);
                console.log('Response headers:', [...response.headers.entries()]);
                
                const rawText = await response.text();
                console.log('Raw response beginning (first 500 chars):', rawText.substring(0, 500));
                
                let data;
                try {
                    data = JSON.parse(rawText);
                    console.log('Parsed JSON successfully:', data);
                } catch (jsonError) {
                    console.error('JSON parse error:', jsonError);
                    
                    // Display raw response for debugging
                    if (transcriptContent) {
                        transcriptContent.innerHTML = '';
                        transcriptContent.innerHTML = `
                            <div style="color: red; margin-bottom: 15px; font-weight: bold;">
                                Error: Server returned invalid JSON response
                            </div>
                            <div style="margin-bottom: 15px;">
                                <strong>Status code:</strong> ${response.status}<br>
                                <strong>Content type:</strong> ${response.headers.get('content-type') || 'unknown'}<br>
                                <strong>Response size:</strong> ${rawText.length} characters
                            </div>
                            <div style="font-size: 12px; background: #f5f5f5; padding: 10px; overflow: auto; max-height: 300px; border: 1px solid #ddd; border-radius: 4px;">
                                <pre>${rawText.length > 1000 ? rawText.substring(0, 1000) + '...' : rawText}</pre>
                            </div>
                            <div style="margin-top: 15px;">
                                <p>This error usually occurs when:</p>
                                <ul>
                                    <li>The server encountered an internal error</li>
                                    <li>The file is too large for processing</li>
                                    <li>The server timed out during processing</li>
                                </ul>
                                <p>Please try with a smaller audio file or contact support.</p>
                            </div>
                        `;
                    }
                    
                    status.textContent = 'Error: Server returned invalid data';
                    processing = false;
                    return;
                }
                
                // Handle large file (background job) response
                if (isLargeFile && data.job_id) {
                    handleLargeFileJob(data.job_id);
                    return;
                }
                
                // If we have a regular response with transcript
                console.log('Transcription completed');
                const processingTime = ((Date.now() - uploadStartTime) / 1000).toFixed(1);
                
                // Update progress to 100%
                progress.style.width = '100%';
                status.textContent = `Transcription complete! (${processingTime}s)`;
                
                // Display the transcript
                currentTranscript = data.transcript;
                if (transcriptContent) {
                    transcriptContent.innerHTML = '';
                    transcriptContent.textContent = currentTranscript;
                }
                
                // Show chat section
                if (chatSection) chatSection.style.display = 'block';
                
                processing = false;
            } catch (fetchError) {
                console.error('Fetch error:', fetchError);
                
                if (fetchError.name === 'AbortError') {
                    status.textContent = 'Error: Request timed out. The server is taking too long to process.';
                } else {
                    status.textContent = `Error: ${fetchError.message}`;
                }
                
                if (transcriptContent) {
                    transcriptContent.innerHTML = '';
                    
                    const errorDiv = document.createElement('div');
                    errorDiv.style.padding = '1rem';
                    errorDiv.style.backgroundColor = '#FEF2F2';
                    errorDiv.style.border = '1px solid #F87171';
                    errorDiv.style.borderRadius = '0.5rem';
                    errorDiv.style.color = '#B91C1C';
                    
                    const errorTitle = document.createElement('h3');
                    errorTitle.textContent = 'Network Error';
                    errorTitle.style.marginBottom = '0.5rem';
                    errorTitle.style.fontWeight = 'bold';
                    
                    const errorMessage = document.createElement('p');
                    errorMessage.textContent = fetchError.message || 'Failed to connect to the server';
                    
                    errorDiv.appendChild(errorTitle);
                    errorDiv.appendChild(errorMessage);
                    
                    transcriptContent.appendChild(errorDiv);
                }
                
                processing = false;
                return;
            }
        } catch (error) {
            console.error('Unhandled error:', error);
            status.textContent = `Error: ${error.message}`;
            
            if (transcriptContent) {
                transcriptContent.innerHTML = '';
                
                const errorContainer = document.createElement('div');
                errorContainer.style.padding = '1rem';
                errorContainer.style.backgroundColor = '#FEF2F2';
                errorContainer.style.border = '1px solid #F87171';
                errorContainer.style.borderRadius = '0.5rem';
                errorContainer.style.color = '#B91C1C';
                
                const errorTitle = document.createElement('h3');
                errorTitle.textContent = 'Error Processing Audio';
                errorTitle.style.marginBottom = '0.5rem';
                errorTitle.style.fontWeight = 'bold';
                
                const errorMessage = document.createElement('p');
                errorMessage.textContent = error.message || 'An unknown error occurred while processing your audio file.';
                
                const errorHelp = document.createElement('p');
                errorHelp.style.marginTop = '1rem';
                errorHelp.innerHTML = `
                    <strong>Troubleshooting:</strong>
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem;">
                        <li>Try a shorter audio file (under 30 minutes)</li>
                        <li>Convert your file to MP3 format if possible</li>
                        <li>Try the "process first 30 minutes" option for large files</li>
                        <li>Ensure the file is not corrupted</li>
                        <li>Try again in a few minutes</li>
                    </ul>
                `;
                
                errorContainer.appendChild(errorTitle);
                errorContainer.appendChild(errorMessage);
                errorContainer.appendChild(errorHelp);
                
                transcriptContent.appendChild(errorContainer);
            }
            
            processing = false;
        }
    }

    // Handle large file background job
    function handleLargeFileJob(jobId) {
        console.log('Handling large file job:', jobId);
        currentJobId = jobId;
        
        // Display the job processing UI
        if (transcriptContent) {
            transcriptContent.innerHTML = '';
            transcriptContent.appendChild(showLargeFileProcessingMessage(jobId));
        }
        
        // Update progress to 100% for upload phase
        progress.style.width = '100%';
        status.textContent = 'File uploaded and queued for processing';
        
        // Start checking job status
        const statusBox = document.getElementById('job-status-box');
        let elapsedTime = 0;
        
        // Clear any existing interval
        if (jobCheckInterval) {
            clearInterval(jobCheckInterval);
        }
        
        // Set up the interval to check job status
        jobCheckInterval = setInterval(async () => {
            try {
                const jobStatus = await checkJobStatus(jobId);
                elapsedTime += 5;
                
                if (statusBox) {
                    if (jobStatus.status === 'completed') {
                        statusBox.textContent = 'Transcription completed successfully!';
                        statusBox.style.backgroundColor = '#ECFDF5';
                        statusBox.style.color = '#065F46';
                        
                        // Clear the interval
                        clearInterval(jobCheckInterval);
                        jobCheckInterval = null;
                        
                        // Display the transcript
                        setTimeout(() => {
                            currentTranscript = jobStatus.transcript;
                            if (transcriptContent) {
                                transcriptContent.innerHTML = '';
                                transcriptContent.textContent = currentTranscript;
                            }
                            
                            // Show chat section
                            if (chatSection) chatSection.style.display = 'block';
                            
                            processing = false;
                        }, 1000);
                    } else if (jobStatus.status === 'failed') {
                        statusBox.textContent = `Error: ${jobStatus.error || 'Processing failed'}`;
                        statusBox.style.backgroundColor = '#FEF2F2';
                        statusBox.style.color = '#B91C1C';
                        
                        // Clear the interval
                        clearInterval(jobCheckInterval);
                        jobCheckInterval = null;
                        processing = false;
                    } else {
                        // Still processing
                        statusBox.textContent = `Processing... (${elapsedTime}s elapsed)`;
                    }
                }
            } catch (error) {
                console.error('Error checking job status:', error);
                if (statusBox) {
                    statusBox.textContent = `Error checking status: ${error.message}`;
                    statusBox.style.backgroundColor = '#FEF2F2';
                    statusBox.style.color = '#B91C1C';
                }
                
                // After several failures, stop checking
                if (elapsedTime > 300) {  // Stop after 5 minutes of failures
                    clearInterval(jobCheckInterval);
                    jobCheckInterval = null;
                    processing = false;
                }
            }
        }, 5000);  // Check every 5 seconds
    }

    // Check job status
    async function checkJobStatus(jobId) {
        const response = await fetch(`${API_BASE_URL}/job-status/${jobId}`);
        
        if (!response.ok) {
            throw new Error(`Failed to check job status: ${response.status}`);
        }
        
        return await response.json();
    }

    // Modified simulated progress for long files
    function simulateProgress(isLargeFile) {
        // This simulates progress while waiting for the actual transcription
        console.log('Simulating progress');
        const totalSteps = isLargeFile ? 100 : 95; // For large files, go to 100% since we're just uploading
        let currentStep = 0;
        
        // For large files, progress will be faster (just showing upload progress)
        const stepInterval = isLargeFile ? 50 : 100; // Faster for large files since we're just showing upload
        
        const interval = setInterval(() => {
            if (!processing || currentStep >= totalSteps) {
                clearInterval(interval);
                return;
            }
            
            // For large files, increase normally since it's just upload progress
            // For small files, slow down near the end to simulate processing
            const increment = isLargeFile 
                ? 1 
                : (currentStep < 50 ? 1 : (currentStep < 80 ? 0.5 : 0.1));
            
            currentStep += increment;
            progress.style.width = `${currentStep}%`;
            
            // Update status message based on progress
            if (isLargeFile) {
                status.textContent = 'Uploading file...';
            } else {
                if (currentStep < 10) {
                    status.textContent = 'Processing audio file...';
                } else if (currentStep < 30) {
                    status.textContent = 'Removing silence...';
                } else if (currentStep < 60) {
                    status.textContent = 'Processing audio...';
                } else {
                    status.textContent = 'Transcribing...';
                }
            }
        }, stepInterval);
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
            
            summaryContent.innerHTML = '';
            summaryContent.textContent = data.summary;
            summarizeBtn.classList.add('fade-out');
            
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
        
        summaryContent.innerHTML = '';
        
        summaryContent.appendChild(showLoading());
        
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
                throw new Error(errorData.error || 'Failed to regenerate summary');
            }
            
            const data = await response.json();
            
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

    async function applySummarySettings() {
        if (!currentTranscript || processing) return;
        
        const newSettings = getSummarySettings();
        console.log('Applying summary settings:', newSettings);
        
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
            
            if (applySummarySettingsBtn) {
                applySummarySettingsBtn.disabled = false;
                applySummarySettingsBtn.classList.remove('disabled');
            }
        } finally {
            processing = false;
        }
    }

    function setupSettingsChangeHandlers() {
        if (wordCountInput) {
            wordCountInput.addEventListener('input', handleSettingsChange);
        }
        
        if (summaryStyleInput) {
            summaryStyleInput.addEventListener('input', handleSettingsChange);
        }
    }

    function handleSettingsChange() {
        const currentSettings = getSummarySettings();
        
        const isDifferent = !appliedSettings || 
                            currentSettings.wordCount !== appliedSettings.wordCount || 
                            currentSettings.style !== appliedSettings.style;
        
        if (isDifferent && applySummarySettingsBtn) {
            applySummarySettingsBtn.classList.remove('success', 'inactive');
        }
    }

    async function sendQuestion() {
        const questionText = chatInputText.value.trim();
        if (!questionText || processing || !currentTranscript) return;
        
        addMessageToChat(questionText, 'user');
        chatInputText.value = '';
        
        processing = true;
        
        const aiMessageContainer = document.createElement('div');
        aiMessageContainer.className = 'chat-message ai-message';
        aiMessageContainer.appendChild(showLoading());
        chatHistory.appendChild(aiMessageContainer);
        
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
            
            chatHistory.removeChild(aiMessageContainer);
            
            addMessageToChat(data.answer, 'ai');
        } catch (error) {
            console.error('Error:', error);
            
            chatHistory.removeChild(aiMessageContainer);
            
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