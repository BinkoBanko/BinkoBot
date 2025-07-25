// Dashboard JavaScript functionality

document.addEventListener('DOMContentLoaded', function() {
    // Initialize dashboard
    initializeDashboard();
    
    // Set up refresh functionality
    setupRefreshHandlers();
    
    // Load additional stats
    loadDashboardStats();
});

function initializeDashboard() {
    console.log('Dashboard initialized');
    
    // Add loading states to refresh buttons
    const refreshButtons = document.querySelectorAll('a[href*="refresh-server"]');
    refreshButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            this.classList.add('loading');
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        });
    });
    
    // Animate progress bars
    const progressBars = document.querySelectorAll('.progress-bar');
    progressBars.forEach(bar => {
        const width = bar.style.width;
        bar.style.width = '0%';
        setTimeout(() => {
            bar.style.width = width;
        }, 100);
    });
    
    // Add hover effects to server cards
    const serverCards = document.querySelectorAll('.card');
    serverCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
}

function setupRefreshHandlers() {
    // Handle refresh button clicks
    const refreshButtons = document.querySelectorAll('.btn[href*="refresh-server"]');
    
    refreshButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            const originalText = this.innerHTML;
            
            // Show loading state
            this.classList.add('loading');
            this.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Refreshing...';
            this.disabled = true;
            
            // The actual navigation will happen, but we show immediate feedback
            setTimeout(() => {
                this.innerHTML = originalText;
                this.classList.remove('loading');
                this.disabled = false;
            }, 3000);
        });
    });
}

function loadDashboardStats() {
    // Load additional statistics via API
    fetch('/api/dashboard/stats')
        .then(response => response.json())
        .then(data => {
            updateDashboardStats(data);
        })
        .catch(error => {
            console.error('Error loading dashboard stats:', error);
        });
}

function updateDashboardStats(stats) {
    // Update active servers count
    const activeServersElement = document.getElementById('active-servers');
    if (activeServersElement) {
        animateNumber(activeServersElement, stats.active_servers);
    }
    
    // Update total members count
    const totalMembersElement = document.getElementById('total-members');
    if (totalMembersElement) {
        animateNumber(totalMembersElement, stats.total_members);
    }
}

function animateNumber(element, targetNumber, duration = 1000) {
    const start = parseInt(element.textContent) || 0;
    const increment = (targetNumber - start) / (duration / 16);
    let current = start;
    
    const timer = setInterval(() => {
        current += increment;
        if ((increment > 0 && current >= targetNumber) || 
            (increment < 0 && current <= targetNumber)) {
            current = targetNumber;
            clearInterval(timer);
        }
        element.textContent = Math.floor(current).toLocaleString();
    }, 16);
}

function getVibeScoreColor(score) {
    if (score >= 80) return 'success';
    if (score >= 60) return 'info';
    if (score >= 40) return 'warning';
    return 'danger';
}

function formatVibeScore(score) {
    return Math.round(score * 10) / 10;
}

// Utility function to show notifications
function showNotification(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container');
    if (container) {
        container.insertBefore(alertDiv, container.firstChild);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
}

// Handle server card interactions
function handleServerCardClick(serverId) {
    // Add visual feedback
    const card = document.querySelector(`[data-server-id="${serverId}"]`);
    if (card) {
        card.style.transform = 'scale(0.98)';
        setTimeout(() => {
            card.style.transform = 'scale(1)';
        }, 150);
    }
}

// Add keyboard navigation support
document.addEventListener('keydown', function(e) {
    if (e.key === 'r' && e.ctrlKey) {
        e.preventDefault();
        location.reload();
    }
});

// Check for updates periodically
setInterval(checkForUpdates, 300000); // Check every 5 minutes

function checkForUpdates() {
    // This could ping the server to check if data needs refreshing
    console.log('Checking for updates...');
}

// Export functions for use in other scripts
window.DashboardJS = {
    updateDashboardStats,
    animateNumber,
    getVibeScoreColor,
    formatVibeScore,
    showNotification
};
