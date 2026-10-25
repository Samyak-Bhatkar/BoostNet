document.addEventListener("DOMContentLoaded", async () => {
    const chk = document.getElementById("chk-auto-intercept");
    const openBtn = document.getElementById("btn-open-dashboard");

    const settings = await chrome.storage.local.get({ autoIntercept: true });
    chk.checked = settings.autoIntercept;

    chk.addEventListener("change", () => {
        chrome.storage.local.set({ autoIntercept: chk.checked });
    });

    openBtn.addEventListener("click", () => {
        chrome.tabs.create({ url: "http://127.0.0.1:9051" });
    });
});
