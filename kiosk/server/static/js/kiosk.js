/**
 * BioFusion Kiosk — Client-side JavaScript
 * Handles HTMX events and camera preview lifecycle.
 */

// ─── HTMX Event Hooks ──────────────────────────────────────────────────────

// After any HTMX swap, handle cleanup
document.addEventListener('htmx:afterSwap', function(event) {
    // If we swapped back to idle, ensure camera stream is stopped
    const preview = document.getElementById('camera-preview');
    if (!preview) {
        // No preview on screen — camera stream will stop naturally
        // since the <img> tag requesting /api/preview is removed
    }
});

// Before a request, disable the triggering button to prevent double-clicks
document.addEventListener('htmx:beforeRequest', function(event) {
    const trigger = event.detail.elt;
    if (trigger && trigger.tagName === 'BUTTON') {
        trigger.disabled = true;
        trigger.style.opacity = '0.6';
    }
});

// After request completes (success or error), re-enable buttons
document.addEventListener('htmx:afterRequest', function(event) {
    const trigger = event.detail.elt;
    if (trigger && trigger.tagName === 'BUTTON') {
        trigger.disabled = false;
        trigger.style.opacity = '1';
    }
});

// Handle request errors gracefully
document.addEventListener('htmx:responseError', function(event) {
    console.error('HTMX request error:', event.detail);
});

// ─── Browser camera capture ────────────────────────────────────────────────
// Used when the server has no camera of its own (CAPTURE_MODE == "browser").
// cv2.VideoCapture opens a device on the machine running Python, so a hosted
// server can never reach the visitor's webcam — the browser grabs the frame
// and posts it to /api/capture-upload instead.

const BrowserCamera = (function () {
    let stream = null;

    function describeError(err) {
        if (!navigator.mediaDevices) {
            return 'Camera access needs a secure (https) connection.';
        }
        switch (err && err.name) {
            case 'NotAllowedError':
            case 'SecurityError':
                return 'Camera permission was denied. Allow it in your browser, or choose an image instead.';
            case 'NotFoundError':
            case 'OverconstrainedError':
                return 'No camera found on this device.';
            case 'NotReadableError':
                return 'The camera is already in use by another app.';
            default:
                return 'Could not start the camera: ' + ((err && err.message) || 'unknown error');
        }
    }

    function showFallback(message) {
        const box = document.getElementById('browser-camera-fallback');
        const text = document.getElementById('browser-camera-error');
        const capture = document.getElementById('browser-capture');
        if (text) text.textContent = message;
        if (box) box.hidden = false;
        if (capture) capture.hidden = true;
    }

    async function start() {
        const video = document.getElementById('browser-video');
        if (!video) return;
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            showFallback(describeError(null));
            return;
        }
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                // Rear camera where there is one — the X-ray is in front of the user
                video: {
                    facingMode: { ideal: 'environment' },
                    width: { ideal: 1920 },
                    height: { ideal: 1080 }
                },
                audio: false
            });
            video.srcObject = stream;
            await video.play();
        } catch (err) {
            console.error('getUserMedia failed:', err);
            showFallback(describeError(err));
        }
    }

    function stop() {
        if (!stream) return;
        stream.getTracks().forEach(function (t) { t.stop(); });
        stream = null;
    }

    function setBusy(busy) {
        const indicator = document.getElementById('loading-indicator');
        // htmx reveals its indicators via .htmx-request; match that so the
        // fetch-based upload uses the same overlay as every other request.
        if (indicator) indicator.classList.toggle('htmx-request', busy);
        const capture = document.getElementById('browser-capture');
        if (capture) capture.disabled = busy;
    }

    function swapContent(html) {
        const target = document.getElementById('kiosk-content');
        if (!target) return;
        // Same 0.18s cross-fade the htmx swaps use.
        target.classList.add('htmx-swapping');
        setTimeout(function () {
            target.innerHTML = html;
            target.classList.remove('htmx-swapping');
            if (window.htmx) window.htmx.process(target);
        }, 180);
    }

    async function send(blob, filename) {
        setBusy(true);
        try {
            const form = new FormData();
            form.append('image', blob, filename);
            const res = await fetch('/api/capture-upload', { method: 'POST', body: form });
            const html = await res.text();
            stop();
            swapContent(html);
        } catch (err) {
            console.error('Upload failed:', err);
            showFallback('Upload failed: ' + ((err && err.message) || 'unknown error'));
        } finally {
            setBusy(false);
        }
    }

    function capture() {
        const video = document.getElementById('browser-video');
        const canvas = document.getElementById('browser-canvas');
        if (!video || !canvas) return;
        if (!video.videoWidth) {
            showFallback('The camera is still starting up. Try again in a moment.');
            return;
        }
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(function (blob) {
            if (blob) send(blob, 'capture.jpg');
        }, 'image/jpeg', 0.92);
    }

    return { start: start, stop: stop, capture: capture, send: send };
})();

// The preview is swapped in by htmx, so bind by delegation rather than on load.
document.addEventListener('click', function (event) {
    if (event.target.closest && event.target.closest('#browser-capture')) {
        event.preventDefault();
        BrowserCamera.capture();
    }
});

document.addEventListener('change', function (event) {
    if (event.target && event.target.id === 'browser-file') {
        const file = event.target.files && event.target.files[0];
        if (file) BrowserCamera.send(file, file.name || 'upload.jpg');
    }
});

// Start the camera when the preview appears, release it when it goes away.
document.addEventListener('htmx:afterSwap', function () {
    if (document.getElementById('browser-camera')) {
        BrowserCamera.start();
    } else {
        BrowserCamera.stop();
    }
});

// Never leave the camera light on.
window.addEventListener('pagehide', function () { BrowserCamera.stop(); });

// ─── Prevent zoom on double-tap (kiosk mode) ───────────────────────────────
document.addEventListener('dblclick', function(e) {
    e.preventDefault();
}, { passive: false });

// ─── Prevent context menu (kiosk mode) ──────────────────────────────────────
document.addEventListener('contextmenu', function(e) {
    e.preventDefault();
});

// ─── Console greeting ───────────────────────────────────────────────────────
console.log('%c🏥 BioFusion Kiosk', 'font-size: 20px; font-weight: bold; color: #2563EB;');
console.log('%cAI-Assisted Pneumonia Detection System', 'font-size: 12px; color: #94A3B8;');
