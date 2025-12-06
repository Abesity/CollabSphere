// Admin Dashboard JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap components
    initializeBootstrapComponents();
    
    // Sidebar toggle functionality
    setupSidebarToggle();
    
    // Search functionality
    setupSearch();
    
    // Load statistics
    loadStatistics();
    
    // Initialize modals
    setupModals();
    
    // Form validation
    setupFormValidation();
});

function initializeBootstrapComponents() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
}

function setupSidebarToggle() {
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.querySelector('.admin-sidebar');
    const mainContent = document.querySelector('.admin-main');
    
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            mainContent.classList.toggle('expanded');
            
            // Update localStorage
            const isCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('sidebarCollapsed', isCollapsed);
        });
        
        // Check for saved sidebar state
        const savedState = localStorage.getItem('sidebarCollapsed');
        if (savedState === 'true') {
            sidebar.classList.add('collapsed');
            mainContent.classList.add('expanded');
        }
    }
}

function setupSearch() {
    const searchInput = document.querySelector('.topbar-search input');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                const form = this.closest('form');
                if (form) {
                    form.submit();
                }
            }
        });
    }
}

function loadStatistics() {
    // Load user registration stats
    const weeklyUsersElement = document.getElementById('weeklyUsers');
    if (weeklyUsersElement) {
        fetch('/admin/api/user-stats/')
            .then(response => response.json())
            .then(data => {
                if (data.data) {
                    const today = new Date();
                    const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
                    
                    const recentUsers = data.data.filter(item => {
                        const itemDate = new Date(item.date);
                        return itemDate >= weekAgo;
                    });
                    
                    const weeklyCount = recentUsers.reduce((sum, item) => sum + (item.count || 0), 0);
                    weeklyUsersElement.textContent = weeklyCount;
                }
            })
            .catch(error => {
                console.error('Error loading weekly stats:', error);
                weeklyUsersElement.textContent = '0';
            });
    }
    
    // Load system stats for dashboard
    const dashboardStatsElement = document.querySelector('.stats-grid');
    if (dashboardStatsElement) {
        fetch('/admin/api/system-stats/')
            .then(response => response.json())
            .then(data => {
                // Update any stats on the page
                updateDashboardStats(data);
            })
            .catch(error => {
                console.error('Error loading system stats:', error);
            });
    }
}

function updateDashboardStats(stats) {
    // Update any dynamic stats on the dashboard
    const usersTodayElement = document.querySelector('[data-stat="users-today"]');
    const tasksTodayElement = document.querySelector('[data-stat="tasks-today"]');
    
    if (usersTodayElement && stats.users_today !== undefined) {
        usersTodayElement.textContent = stats.users_today;
    }
    
    if (tasksTodayElement && stats.tasks_today !== undefined) {
        tasksTodayElement.textContent = stats.tasks_today;
    }
}

function setupModals() {
    // Handle delete confirmation modals
    const deleteButtons = document.querySelectorAll('.delete-user-btn, .delete-task-btn');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const target = this.getAttribute('data-target');
            const modalElement = document.getElementById(target);
            
            if (modalElement) {
                const modal = new bootstrap.Modal(modalElement);
                modal.show();
            }
        });
    });
    
    // Handle export modal
    const exportModal = document.getElementById('exportModal');
    if (exportModal) {
        exportModal.addEventListener('show.bs.modal', function() {
            // Load export options dynamically
            loadExportOptions();
        });
    }
}

function loadExportOptions() {
    // This could be extended to load dynamic export options
    console.log('Loading export options...');
}

function setupFormValidation() {
    const forms = document.querySelectorAll('form[data-validate]');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
            }
        });
    });
}

function validateForm(form) {
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    // Email validation
    const emailField = form.querySelector('input[type="email"]');
    if (emailField && emailField.value.trim()) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(emailField.value)) {
            emailField.classList.add('is-invalid');
            isValid = false;
        }
    }
    
    return isValid;
}

// Utility function for debouncing
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Show notification function
function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existingAlerts = document.querySelectorAll('.custom-alert');
    existingAlerts.forEach(alert => alert.remove());

    // Create notification
    const alertDiv = document.createElement('div');
    alertDiv.className = `custom-alert alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    // Style notification
    alertDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        min-width: 300px;
        max-width: 400px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    `;

    // Add to page
    document.body.appendChild(alertDiv);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            const bsAlert = new bootstrap.Alert(alertDiv);
            bsAlert.close();
        }
    }, 5000);
}

// Export function
function exportData(type, format = 'json') {
    const exportBtn = document.querySelector(`[data-export="${type}"]`);
    if (exportBtn) {
        const originalText = exportBtn.innerHTML;
        exportBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Exporting...';
        exportBtn.disabled = true;
        
        let url;
        if (format === 'csv') {
            url = `/admin/export/${type}/?format=csv`;
            // Trigger download
            window.location.href = url;
        } else {
            url = `/admin/export/${type}/`;
            fetch(url)
                .then(response => response.json())
                .then(data => {
                    // Create downloadable JSON file
                    const dataStr = JSON.stringify(data, null, 2);
                    const dataBlob = new Blob([dataStr], { type: 'application/json' });
                    const url = window.URL.createObjectURL(dataBlob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `${type}_export_${new Date().toISOString().split('T')[0]}.json`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                    
                    showNotification(`${type} exported successfully!`, 'success');
                })
                .catch(error => {
                    console.error('Export error:', error);
                    showNotification('Export failed', 'danger');
                })
                .finally(() => {
                    exportBtn.innerHTML = originalText;
                    exportBtn.disabled = false;
                });
        }
    }

    // Real-time data updates
function startLiveUpdates() {
    // Update dashboard stats every 30 seconds
    setInterval(() => {
        if (document.querySelector('.dashboard-container')) {
            loadStatistics();
        }
    }, 30000);
    
    // Check for new notifications
    setInterval(() => {
        checkNewNotifications();
    }, 60000);
}

function checkNewNotifications() {
    fetch('/admin/api/system-stats/')
        .then(response => response.json())
        .then(data => {
            // Check if there are new users or tasks
            if (data.users_today > 0 || data.tasks_today > 0) {
                showNotification(
                    `New activity: ${data.users_today} users, ${data.tasks_today} tasks today`,
                    'info'
                );
            }
        });
}

// Chart initialization
function initCharts() {
    // Weekly user registration chart
    const weeklyUsersCtx = document.getElementById('weeklyUsersChart');
    if (weeklyUsersCtx) {
        fetch("{% url 'admin_app_collabsphere:api_user_stats' %}")
            .then(response => response.json())
            .then(data => {
                createLineChart(weeklyUsersCtx, data.data.slice(0, 7).reverse());
            });
    }
}

function createLineChart(ctx, data) {
    // Chart.js implementation
    const dates = data.map(item => new Date(item.date).toLocaleDateString('en-US', { weekday: 'short' }));
    const counts = data.map(item => item.count);
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [{
                label: 'New Users',
                data: counts,
                borderColor: 'var(--secondary-color)',
                backgroundColor: 'rgba(61, 116, 195, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

    document.addEventListener('DOMContentLoaded', function() {
        initializeBootstrapComponents();
        setupSidebarToggle();
        setupSearch();
        loadStatistics();
        setupModals();
        setupFormValidation();
        initCharts();
        startLiveUpdates();
    });
    }


    