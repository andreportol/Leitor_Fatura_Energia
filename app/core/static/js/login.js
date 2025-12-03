document.addEventListener('DOMContentLoaded', () => {
    const timerEl = document.getElementById('lockout-timer');
    const submitBtn = document.getElementById('login-submit');

    if (!timerEl) return;

    let remaining = parseInt(timerEl.dataset.remaining, 10) || 0;

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
        const secs = Math.floor(seconds % 60).toString().padStart(2, '0');
        return `${mins}:${secs}`;
    };

    const tick = () => {
        if (remaining <= 0) {
            timerEl.textContent = '00:00';
            if (submitBtn) submitBtn.removeAttribute('disabled');
            return;
        }

        timerEl.textContent = formatTime(remaining);
        remaining -= 1;
        setTimeout(tick, 1000);
    };

    tick();
});
