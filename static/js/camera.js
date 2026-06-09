// AttendAI — camera.js
// Core camera logic for the attendance scanner is in attendance.html (inline script)
// and enroll.html (inline script). This file is loaded on every page.

// Prevent accidental form double-submit
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('form').forEach(function (form) {
    form.addEventListener('submit', function () {
      const btn = form.querySelector('button[type="submit"]');
      if (btn) {
        btn.disabled = true;
        btn.textContent = 'Processing…';
      }
    });
  });
});
