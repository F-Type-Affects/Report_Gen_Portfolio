/**
 * Unified Progress Tracking Module
 * Handles both single-step and multi-step progress tracking with SSE
 * Compatible with Flask SSE endpoint at /progress/<session_id>
 */

class UnifiedProgressTracker {
    constructor(sessionId, config = {}) {
        this.sessionId = sessionId;
        this.eventSource = null;
        this.isTracking = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        
        // Configuration with defaults
        this.config = {
            reportType: config.reportType || 'Report',
            timeout: config.timeout || 600000, // 10 minutes default
            autoRedirect: config.autoRedirect !== false, // Default true
            redirectUrl: config.redirectUrl || '/',
            redirectDelay: config.redirectDelay || 3000,
            onSuccess: config.onSuccess || null,
            onError: config.onError || null,
            ...config
        };
        
        // DOM elements - will be populated when tracking starts
        this.elements = {};
        
        console.log(`Initialized progress tracker for session: ${this.sessionId}`);
    }

    /**
     * Initialize DOM element references
     * Called automatically when starting tracking
     */
    initializeElements() {
        this.elements = {
            progressFill: document.getElementById('progressFill'),
            loadingText: document.getElementById('loading-text'),
            loadingIndicator: document.getElementById('loading-indicator'),
            steps: ['step-1', 'step-2', 'step-3'].map(id => document.getElementById(id)).filter(el => el)
        };
        
        console.log('Progress tracker elements initialized:', this.elements);
    }

    /**
     * Start progress tracking with Server-Sent Events
     */
    startTracking() {
        if (this.isTracking || !this.sessionId) {
            console.warn('Progress tracking already active or no session ID provided');
            return;
        }
        
        this.isTracking = true;
        this.reconnectAttempts = 0;
        
        // Initialize DOM elements
        this.initializeElements();
        
        // Show loading indicator if available
        if (this.elements.loadingIndicator) {
            this.elements.loadingIndicator.style.display = 'block';
        }
        
        console.log(`Starting progress tracking for ${this.config.reportType} session: ${this.sessionId}`);
        
        this.connectToProgressStream();
        
        // Set timeout for the entire operation
        this.timeoutId = setTimeout(() => {
            if (this.isTracking) {
                this.handleTimeout();
            }
        }, this.config.timeout);
    }

    /**
     * Establish SSE connection to progress endpoint
     */
    connectToProgressStream() {
        try {
            // Close existing connection if any
            if (this.eventSource) {
                this.eventSource.close();
            }
            
            // Create new EventSource connection with correct URL prefix
            const url = `/api/progress/${this.sessionId}`;
            this.eventSource = new EventSource(url);
            
            console.log(`Connecting to progress stream: ${url}`);
            
            // Handle successful connection
            this.eventSource.onopen = (event) => {
                console.log('Progress connection established');
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('connected');
            };
            
            // Handle incoming progress messages
            this.eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleProgressUpdate(data);
                } catch (error) {
                    console.error('Error parsing progress data:', error, event.data);
                }
            };
            
            // Handle connection errors
            this.eventSource.onerror = (error) => {
                console.error('EventSource error:', error);
                this.handleConnectionError();
            };
            
        } catch (error) {
            console.error('Failed to create EventSource:', error);
            this.handleConnectionError();
        }
    }

    /**
     * Handle incoming progress updates
     */
    handleProgressUpdate(data) {
        console.log('Raw progress update received:', data);
        
        // Handle different status states
        switch (data.status) {
            case 'starting':
                console.log('Status: starting');
                this.updateStarting(data);
                break;
            case 'in_progress':
                console.log('Status: in_progress');
                this.updateInProgress(data);
                break;
            case 'completed':
                console.log('Status: completed');
                this.updateCompleted(data);
                break;
            case 'error':
                console.log('Status: error');
                this.updateError(data);
                break;
            case 'no_data':
                this.handleNoData();
                break;
            case 'waiting':
                // Just heartbeat, don't log spam
                break;
            default:
                console.warn('Unknown progress status:', data.status);
                // Treat unknown status as in_progress if we have progress data
                if (data.overall_progress !== undefined) {
                    console.log('Treating unknown status as in_progress');
                    this.updateInProgress(data);
                }
                break;
        }
    }

    /**
     * Update UI for starting state
     */
    updateStarting(data) {
        this.updateConnectionStatus('active');
        
        if (this.elements.loadingText && data.message) {
            this.elements.loadingText.textContent = data.message;
            this.elements.loadingText.style.color = '';
        }
        
        // Initialize progress bar
        if (this.elements.progressFill) {
            this.elements.progressFill.style.width = '0%';
        }
    }

    /**
     * Update UI for in-progress state
     */
    updateInProgress(data) {
        console.log('Updating progress UI:', data);
        
        // Update overall progress bar
        if (this.elements.progressFill && data.overall_progress !== undefined) {
            const progress = Math.min(100, Math.max(0, data.overall_progress));
            this.elements.progressFill.style.width = `${progress}%`;
            console.log(`Progress bar updated to: ${progress}%`);
        }
        
        // Update loading text
        if (this.elements.loadingText && data.message) {
            this.elements.loadingText.textContent = data.message;
            this.elements.loadingText.style.color = '';
            console.log(`Loading text updated: ${data.message}`);
        }
        
        // Update individual steps if available
        if (data.steps && Array.isArray(data.steps)) {
            data.steps.forEach((step, index) => {
                this.updateStepStatus(index, step);
            });
        }
        
        // Force a repaint to ensure changes are visible
        if (this.elements.progressFill) {
            this.elements.progressFill.offsetHeight; // Trigger reflow
        }
    }

    /**
     * Update individual step status
     */
    updateStepStatus(stepIndex, stepData) {
        if (stepIndex >= this.elements.steps.length || !this.elements.steps[stepIndex]) {
            return;
        }
        
        const stepElement = this.elements.steps[stepIndex];
        const statusElement = stepElement.querySelector('.step-status');
        
        if (!statusElement) return;
        
        console.log(`Updating step ${stepIndex}:`, stepData);
        
        // Remove existing status classes
        stepElement.classList.remove('active', 'completed', 'error', 'pending');
        
        // Update based on step status
        switch (stepData.status) {
            case 'in_progress':
                stepElement.classList.add('active');
                statusElement.textContent = '🔄';
                console.log(`Step ${stepIndex} set to in_progress`);
                break;
            case 'completed':
                stepElement.classList.add('completed');
                statusElement.textContent = '✅';
                console.log(`Step ${stepIndex} set to completed`);
                break;
            case 'error':
                stepElement.classList.add('error');
                statusElement.textContent = '❌';
                console.log(`Step ${stepIndex} set to error`);
                break;
            case 'pending':
            default:
                stepElement.classList.add('pending');
                statusElement.textContent = '⏳';
                console.log(`Step ${stepIndex} set to pending`);
                break;
        }
        
        // Force a repaint
        stepElement.offsetHeight; // Trigger reflow
    }

    /**
     * Update UI for completion state
     */
    updateCompleted(data) {
        console.log(`${this.config.reportType} completed successfully`);
        
        // Update final progress
        if (this.elements.progressFill) {
            this.elements.progressFill.style.width = '100%';
        }
        
        if (this.elements.loadingText) {
            this.elements.loadingText.textContent = data.message || `${this.config.reportType} completed successfully!`;
            this.elements.loadingText.style.color = '#059669'; // Green
        }
        
        // Mark all steps as completed if available
        if (data.steps && Array.isArray(data.steps)) {
            data.steps.forEach((step, index) => {
                this.updateStepStatus(index, step);
            });
        }
        
        // Show success notification
        this.showNotification('success', data.message || `${this.config.reportType} completed successfully!`);
        
        // Execute custom success callback if provided
        if (this.config.onSuccess) {
            this.config.onSuccess(data);
        }
        
        // Auto-redirect after delay
        if (this.config.autoRedirect) {
            setTimeout(() => {
                this.redirectAfterCompletion(data);
            }, this.config.redirectDelay);
        }
        
        this.stopTracking();
    }

    /**
     * Update UI for error state
     */
    updateError(data) {
        console.error(`${this.config.reportType} failed:`, data.error);
        
        if (this.elements.loadingText) {
            this.elements.loadingText.textContent = data.message || `An error occurred during ${this.config.reportType} generation`;
            this.elements.loadingText.style.color = '#dc2626'; // Red
        }
        
        // Mark current step as error if available
        if (data.current_step !== undefined && this.elements.steps[data.current_step]) {
            this.updateStepStatus(data.current_step, { status: 'error' });
        }
        
        // Show error notification
        this.showNotification('error', data.error || 'Unknown error occurred');
        
        // Execute custom error callback if provided
        if (this.config.onError) {
            this.config.onError(data);
        }
        
        this.stopTracking();
    }

    /**
     * Handle connection errors with automatic reconnection
     */
    handleConnectionError() {
        console.error('Lost connection to progress stream');
        
        if (this.reconnectAttempts < this.maxReconnectAttempts && this.isTracking) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            
            if (this.elements.loadingText) {
                this.elements.loadingText.textContent = `Connection lost. Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`;
                this.elements.loadingText.style.color = '#f59e0b'; // Amber
            }
            
            setTimeout(() => {
                if (this.isTracking) {
                    this.connectToProgressStream();
                }
            }, this.reconnectDelay * this.reconnectAttempts);
        } else {
            console.error('Max reconnection attempts reached');
            if (this.elements.loadingText) {
                this.elements.loadingText.textContent = `Connection lost. ${this.config.reportType} may still be processing...`;
                this.elements.loadingText.style.color = '#f59e0b';
            }
            this.updateConnectionStatus('disconnected');
        }
    }

    /**
     * Handle timeout scenario
     */
    handleTimeout() {
        console.warn(`${this.config.reportType} timeout reached`);
        
        if (this.elements.loadingText) {
            this.elements.loadingText.textContent = `${this.config.reportType} is taking longer than expected...`;
            this.elements.loadingText.style.color = '#f59e0b';
        }
        
        this.showNotification('warning', `${this.config.reportType} is taking longer than expected. Please check back later.`);
    }

    /**
     * Handle no data scenario
     */
    handleNoData() {
        console.warn('No progress data available');
        if (this.elements.loadingText) {
            this.elements.loadingText.textContent = 'Initializing progress tracking...';
        }
    }

    /**
     * Update connection status indicator (if available)
     */
    updateConnectionStatus(status) {
        const indicator = document.getElementById('connection-status');
        if (indicator) {
            indicator.className = `connection-status ${status}`;
            indicator.textContent = status;
        }
    }

    /**
     * Show notification to user
     */
    showNotification(type, message) {
        const colors = {
            success: '#059669',
            error: '#dc2626',
            warning: '#f59e0b',
            info: '#2563eb'
        };
        
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${colors[type] || colors.info};
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            z-index: 10001;
            font-weight: 600;
            max-width: 400px;
            word-wrap: break-word;
        `;
        
        if (type === 'error') {
            notification.innerHTML = `
                <div>${this.config.reportType} generation failed!</div>
                <div style="font-size: 14px; margin-top: 5px; opacity: 0.9;">${message}</div>
                <button onclick="this.parentElement.remove()" style="margin-top: 10px; background: rgba(255,255,255,0.2); border: none; color: white; padding: 5px 10px; border-radius: 4px; cursor: pointer;">Close</button>
            `;
        } else {
            notification.textContent = message;
            // Auto-remove success/warning notifications
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.remove();
                }
            }, type === 'success' ? 5000 : 8000);
        }
        
        document.body.appendChild(notification);
    }

    /**
     * Handle redirect after completion
     */
    redirectAfterCompletion(data) {
        // Special handling for ASCE Summary - redirect to display page
        if (this.config.reportType.toLowerCase().includes('summary')) {
            window.location.href = '/asce/display_asce_summary_results';
        } else {
            window.location.href = this.config.redirectUrl;
        }
    }

    /**
     * Stop progress tracking and clean up resources
     */
    stopTracking() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        
        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
            this.timeoutId = null;
        }
        
        this.isTracking = false;
        console.log(`Progress tracking stopped for ${this.config.reportType}`);
    }

    /**
     * Static method to initialize progress tracking from data attributes
     */
    static initializeFromPage(customConfig = {}) {
        const pageContainer = document.querySelector('.page-container');
        const sessionId = pageContainer ? pageContainer.getAttribute('data-progress-session-id') : null;
        
        if (!sessionId) {
            console.log('No progress session ID found on page');
            return null;
        }
        
        // Determine report type from URL or page context
        let reportType = 'Report';
        const path = window.location.pathname;
        
        if (path.includes('asce_summary') || path.includes('generate_asce_summary')) {
            reportType = 'ASCE Summary';
        } else if (path.includes('asce') || path.includes('generate_asce_full_report')) {
            reportType = 'ASCE Full Report';
        } else if (path.includes('soil') || path.includes('generate_soil_survey')) {
            reportType = 'USDA Soil Survey';
        } else if (path.includes('generate_all_reports')) {
            reportType = 'All Reports';
        }
        
        // Merge with custom configuration
        const config = {
            reportType,
            timeout: reportType === 'All Reports' ? 900000 : 600000, // 15 min for all, 10 min for individual
            ...customConfig
        };
        
        console.log(`Initializing progress tracker with session ID: ${sessionId}, type: ${reportType}`);
        
        const tracker = new UnifiedProgressTracker(sessionId, config);
        tracker.startTracking();
        
        return tracker;
    }
}

// Global progress tracker instance
let globalProgressTracker = null;

/**
 * Initialize progress tracking when DOM is ready
 */
function initializeProgressTracking(customConfig = {}) {
    if (globalProgressTracker) {
        console.warn('Progress tracker already initialized');
        return globalProgressTracker;
    }
    
    globalProgressTracker = UnifiedProgressTracker.initializeFromPage(customConfig);
    return globalProgressTracker;
}

/**
 * Clean up progress tracking on page unload
 */
function cleanupProgressTracking() {
    if (globalProgressTracker) {
        globalProgressTracker.stopTracking();
        globalProgressTracker = null;
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeProgressTracking();
});

// Cleanup on page unload
window.addEventListener('beforeunload', cleanupProgressTracking);

// Export for manual initialization if needed
window.UnifiedProgressTracker = UnifiedProgressTracker;
window.initializeProgressTracking = initializeProgressTracking;
window.cleanupProgressTracking = cleanupProgressTracking;