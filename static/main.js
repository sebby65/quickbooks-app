// static/main.js

document.addEventListener("DOMContentLoaded", function () {
    const forecastForm = document.querySelector('form[action^="/forecast"]');
    const emailForm = document.querySelector('form[action="/email"]');
    const downloadBtn = document.querySelector('form[action="/download"] button');

    if (forecastForm) {
        forecastForm.addEventListener("submit", () => {
            forecastForm.querySelector("button").disabled = true;
            forecastForm.querySelector("button").textContent = "Generating...";
        });
    }

    if (emailForm) {
        emailForm.addEventListener("submit", (e) => {
            emailForm.querySelector("button").disabled = true;
            emailForm.querySelector("button").textContent = "Sending...";
        });
    }

    if (downloadBtn) {
        downloadBtn.addEventListener("click", () => {
            downloadBtn.disabled = true;
            setTimeout(() => {
                downloadBtn.disabled = false;
            }, 2000);
        });
    }
});
