// ============================================================
// STUDENT MANAGEMENT SYSTEM - JavaScript
// Sidebar Toggle, Theme Toggle & UI Enhancements
// ============================================================

/**
 * Toggle sidebar visibility on mobile screens.
 */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    let overlay = document.querySelector('.sidebar-overlay');

    sidebar.classList.toggle('active');

    // Create or toggle overlay
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        overlay.addEventListener('click', () => {
            sidebar.classList.remove('active');
            overlay.classList.remove('active');
        });
        document.body.appendChild(overlay);
    }

    overlay.classList.toggle('active');
}

/**
 * Toggle between dark and light theme.
 */
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('sms-theme', newTheme);

    // Update icon
    const icon = document.querySelector('#themeToggle i');
    if (icon) {
        icon.className = newTheme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
    }
}

/**
 * Load saved theme on page load.
 */
function loadTheme() {
    const savedTheme = localStorage.getItem('sms-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);

    const icon = document.querySelector('#themeToggle i');
    if (icon) {
        icon.className = savedTheme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
    }
}

/**
 * DOMContentLoaded event handler for all UI enhancements.
 */
document.addEventListener('DOMContentLoaded', () => {
    // Load theme
    loadTheme();

    // Auto-dismiss flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach((msg, index) => {
        setTimeout(() => {
            msg.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            msg.style.opacity = '0';
            msg.style.transform = 'translateY(-10px)';
            setTimeout(() => msg.remove(), 500);
        }, 5000 + index * 500);
    });

    // Add input animation on focus
    const inputs = document.querySelectorAll('.form-group input, .form-group select, .form-group textarea');
    inputs.forEach(input => {
        input.addEventListener('focus', () => {
            input.parentElement.classList.add('input-focused');
        });
        input.addEventListener('blur', () => {
            input.parentElement.classList.remove('input-focused');
        });
    });

    // Animate stat cards on scroll into view
    const statCards = document.querySelectorAll('.stat-card');
    if (statCards.length > 0) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                    entry.target.style.animation = `fadeInUp 0.6s ease ${index * 0.1}s both`;
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });

        statCards.forEach(card => observer.observe(card));
    }

    // Animate table rows on scroll
    const tableRows = document.querySelectorAll('.table-row-animate');
    if (tableRows.length > 0) {
        const rowObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    rowObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.05 });

        tableRows.forEach(row => rowObserver.observe(row));
    }

    // Animate progress bars
    const progressBars = document.querySelectorAll('.progress-bar');
    if (progressBars.length > 0) {
        const barObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const bar = entry.target;
                    const width = bar.style.width;
                    bar.style.width = '0%';
                    setTimeout(() => {
                        bar.style.width = width;
                    }, 100);
                    barObserver.unobserve(bar);
                }
            });
        }, { threshold: 0.1 });

        progressBars.forEach(bar => barObserver.observe(bar));
    }

    // Close sidebar when pressing Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.querySelector('.sidebar-overlay');
            if (sidebar.classList.contains('active')) {
                sidebar.classList.remove('active');
                if (overlay) overlay.classList.remove('active');
            }
        }
    });

    // Number counter animation for stat cards
    const counters = document.querySelectorAll('.counter');
    counters.forEach(counter => {
        const target = parseInt(counter.getAttribute('data-target'));
        if (isNaN(target) || target === 0) return;

        let current = 0;
        const increment = target / 30;
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                counter.textContent = target;
                clearInterval(timer);
            } else {
                counter.textContent = Math.ceil(current);
            }
        }, 30);
    });
});
