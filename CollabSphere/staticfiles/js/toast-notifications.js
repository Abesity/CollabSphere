/**
 * Toast Notification System
 * Replaces browser alerts with styled toast notifications
 */

// SVG Icons
const ToastIcons = {
    success: `<svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>`,
    error: `<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`,
    warning: `<svg viewBox="0 0 24 24"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>`,
    info: `<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>`,
    close: `<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`
};

// Titles for each type
const ToastTitles = {
    success: 'Success',
    error: 'Error',
    warning: 'Warning',
    info: 'Info'
};

/**
 * Initialize toast container
 */
function initToastContainer() {
    if (!document.getElementById('toast-container')) {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    return document.getElementById('toast-container');
}

/**
 * Show a toast notification
 * @param {string} message - The message to display
 * @param {string} type - Type: 'success', 'error', 'warning', 'info'
 * @param {object} options - Additional options
 */
function showToast(message, type = 'info', options = {}) {
    const container = initToastContainer();
    
    const {
        title = ToastTitles[type],
        duration = 4000,
        showProgress = true
    } = options;
    
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.innerHTML = `
        <div class="toast-icon">${ToastIcons[type]}</div>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
        <button class="toast-close" aria-label="Close">${ToastIcons.close}</button>
        ${showProgress ? '<div class="toast-progress"></div>' : ''}
    `;
    
    // Set progress animation duration
    if (showProgress) {
        const progress = toast.querySelector('.toast-progress');
        if (progress) {
            progress.style.animationDuration = `${duration}ms`;
        }
    }
    
    container.appendChild(toast);
    
    // Close button handler
    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => dismissToast(toast));
    
    // Auto dismiss
    const timeoutId = setTimeout(() => dismissToast(toast), duration);
    toast.dataset.timeoutId = timeoutId;
    
    return toast;
}

/**
 * Dismiss a toast notification
 */
function dismissToast(toast) {
    if (toast.dataset.timeoutId) {
        clearTimeout(parseInt(toast.dataset.timeoutId));
    }
    toast.classList.add('toast-exit');
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 300);
}

/**
 * Success toast shorthand
 */
function showSuccess(message, options = {}) {
    return showToast(message, 'success', options);
}

/**
 * Error toast shorthand
 */
function showError(message, options = {}) {
    return showToast(message, 'error', options);
}

/**
 * Warning toast shorthand
 */
function showWarning(message, options = {}) {
    return showToast(message, 'warning', options);
}

/**
 * Info toast shorthand
 */
function showInfo(message, options = {}) {
    return showToast(message, 'info', options);
}

/**
 * Show confirmation dialog
 * @param {object} options - Dialog options
 * @returns {Promise<boolean>} - Resolves to true if confirmed, false if cancelled
 */
function showConfirmDialog(options = {}) {
    const {
        title = 'Confirm Action',
        message = 'Are you sure you want to proceed?',
        confirmText = 'Confirm',
        cancelText = 'Cancel',
        type = 'warning', // 'warning' or 'danger'
        confirmClass = type === 'danger' ? 'confirm' : 'primary'
    } = options;
    
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'confirm-dialog-overlay';
        
        const iconSvg = type === 'danger' 
            ? `<svg viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>`
            : `<svg viewBox="0 0 24 24"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>`;
        
        overlay.innerHTML = `
            <div class="confirm-dialog">
                <div class="confirm-dialog-icon ${type}">${iconSvg}</div>
                <div class="confirm-dialog-title">${title}</div>
                <div class="confirm-dialog-message">${message}</div>
                <div class="confirm-dialog-actions">
                    <button class="confirm-dialog-btn cancel">${cancelText}</button>
                    <button class="confirm-dialog-btn ${confirmClass}">${confirmText}</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        
        const cancelBtn = overlay.querySelector('.cancel');
        const confirmBtn = overlay.querySelector(`.${confirmClass}`);
        
        const closeDialog = (result) => {
            overlay.style.animation = 'fadeIn 0.2s ease-out reverse';
            setTimeout(() => {
                if (overlay.parentNode) {
                    overlay.parentNode.removeChild(overlay);
                }
                resolve(result);
            }, 200);
        };
        
        cancelBtn.addEventListener('click', () => closeDialog(false));
        confirmBtn.addEventListener('click', () => closeDialog(true));
        
        // Close on overlay click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                closeDialog(false);
            }
        });
        
        // Close on Escape key
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                document.removeEventListener('keydown', escHandler);
                closeDialog(false);
            }
        };
        document.addEventListener('keydown', escHandler);
        
        // Focus confirm button
        confirmBtn.focus();
    });
}

/**
 * Replace native alert with styled toast
 * Call this to override window.alert globally
 */
function overrideNativeAlert() {
    window.nativeAlert = window.alert;
    window.alert = function(message) {
        // Detect if it's an error message
        const isError = message.toLowerCase().includes('error');
        const type = isError ? 'error' : 'info';
        showToast(message, type);
    };
}

/**
 * Replace native confirm with styled dialog
 * Note: This returns a Promise, so existing code using confirm() synchronously won't work
 */
function showConfirm(message, options = {}) {
    return showConfirmDialog({
        message,
        ...options
    });
}

// Initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    initToastContainer();
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        showToast,
        showSuccess,
        showError,
        showWarning,
        showInfo,
        showConfirmDialog,
        showConfirm,
        dismissToast,
        overrideNativeAlert
    };
}
