document.addEventListener('DOMContentLoaded', function() {
    console.log("Daily Check-in Reminder JS Loaded");

    // Fetch check-in status immediately
    fetch("/home/verify_checkin_status/", {
        method: 'GET',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'include'
    })
    .then(response => response.json())
    .then(data => {
        console.log("Check-in status:", data);
        if (!data.has_checked_in_today) {
            showDailyReminder();
        }
    })
    .catch(error => console.error("Error verifying check-in status:", error));
});

// Function to create and show the reminder alert
function showDailyReminder() {
    const reminder = document.createElement('div');
    reminder.id = "dailyCheckinReminder";

    reminder.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 9999;
        min-width: 350px;
        background-color: #FAFBFB;
        border: 1px solid #c0c6d1;
        color: #2D333A;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.15);
        font-family: 'Inter', sans-serif;
        transition: all 0.3s ease;
    `;

    reminder.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <strong>Daily Check-In Reminder</strong><br>
                You haven’t completed your wellbeing check-in today.
            </div>
            <button id="closeCheckinReminder"
                style="
                    background-color: transparent;
                    color: var(--text-muted);
                    border: none;
                    font-size: 1.2rem;
                    cursor: pointer;
                    line-height: 1;
                ">
                ✕
            </button>
        </div>
    `;

    document.body.appendChild(reminder);

    // Attach close event
    document.getElementById('closeCheckinReminder').addEventListener('click', removeReminder);
}

// Removes the reminder box smoothly
function removeReminder() {
    const reminder = document.getElementById('dailyCheckinReminder');
    if (reminder) {
        reminder.style.opacity = '0';
        reminder.style.transform = 'translateY(10px)';
        setTimeout(() => reminder.remove(), 300);
    }
}
