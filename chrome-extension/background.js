/**
 * BoostNet Chrome Extension Service Worker (Manifest V3)
 * Intercepts downloads > 2 MB, extracts Cookie, Referer, and User-Agent headers,
 * cancels Chrome's single-thread download, and dispatches to BoostNet Chunk Engine.
 */

const BOOSTNET_API_URL = "http://127.0.0.1:9051/api/v1/downloads";
const MIN_INTERCEPT_BYTES = 2 * 1024 * 1024; // 2 MB

chrome.downloads.onCreated.addListener(async (downloadItem) => {
    // Check if auto-intercept is enabled
    const settings = await chrome.storage.local.get({ autoIntercept: true });
    if (!settings.autoIntercept) return;

    // Check if download URL is already internal or from BoostNet itself
    if (downloadItem.url.includes("127.0.0.1:9051") || downloadItem.url.includes("127.0.0.1:9055")) {
        return;
    }

    // Check file size threshold (if known)
    if (downloadItem.totalBytes > 0 && downloadItem.totalBytes < MIN_INTERCEPT_BYTES) {
        return; // Small file, allow normal Chrome download
    }

    console.log(`[BoostNet] Intercepting download: ${downloadItem.filename} (${downloadItem.url})`);

    // Cancel Chrome's built-in single-connection download
    chrome.downloads.cancel(downloadItem.id, () => {
        chrome.downloads.erase({ id: downloadItem.id });
    });

    // Extract cookies for the download domain to solve auth/signed URLs
    let cookieHeader = "";
    try {
        const cookies = await chrome.cookies.getAll({ url: downloadItem.url });
        cookieHeader = cookies.map(c => `${c.name}=${c.value}`).join("; ");
    } catch (e) {
        console.warn("[BoostNet] Could not extract cookies:", e);
    }

    const payload = {
        url: downloadItem.url,
        filename: downloadItem.filename ? downloadItem.filename.split(/[\\/]/).pop() : null,
        headers: {
            "Cookie": cookieHeader,
            "Referer": downloadItem.referrer || "",
            "User-Agent": navigator.userAgent
        }
    };

    try {
        const res = await fetch(BOOSTNET_API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const task = await res.json();
        console.log("[BoostNet] Handed off to Parallel Range Accelerator:", task);

        // Update badge
        chrome.action.setBadgeText({ text: "⚡" });
        chrome.action.setBadgeBackgroundColor({ color: "#10b981" });
    } catch (e) {
        console.error("[BoostNet] Failed to reach local daemon:", e);
    }
});
