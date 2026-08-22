"""
BioFusion Kiosk — Flask Application
Main entry point for the hospital kiosk web interface.
"""

import os
import sys
import glob
import socket
import logging
from datetime import datetime
from flask import (
    Flask, render_template, Response, jsonify, send_file, request
)
from PIL import Image
import numpy as np

from config import (
    SERIAL_PORT, BAUD_RATE, SERIAL_TIMEOUT,
    CAMERA_INDEX, CAPTURE_WIDTH, CAPTURE_HEIGHT,
    PREVIEW_WIDTH, PREVIEW_HEIGHT, JPEG_QUALITY,
    MODEL_WEIGHTS, CAPTURES_DIR, REPORTS_DIR,
    HOST, PORT, DEBUG, PUBLIC_BASE_URL, CAPTURE_MODE as CAPTURE_MODE_SETTING
)
from serial_bridge import SerialBridge
from camera import CameraController
from inference import load_model, analyze_image
from report import generate_report_id, generate_pdf_report, generate_qr_code

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ─── Flask App ───────────────────────────────────────────────────────────────
app = Flask(__name__)

# ─── Static asset caching ────────────────────────────────────────────────────
# Flask defaults to Cache-Control: no-cache, which costs a revalidation
# round-trip per asset on every page load. Static filenames here are stable, so
# serve them with a long max-age and cache-bust via the asset_v query stamp
# below, which changes whenever a static file is modified.
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000  # 1 year


def _asset_version():
    """Stamp from the newest static file mtime, so a deploy invalidates caches."""
    newest = 0.0
    for root, _dirs, files in os.walk(app.static_folder):
        for name in files:
            newest = max(newest, os.path.getmtime(os.path.join(root, name)))
    return str(int(newest))


ASSET_VERSION = _asset_version()


def _resolve_capture_mode(mode):
    """Turn "auto" into a concrete mode by looking for a local video device."""
    if mode in ("hardware", "browser"):
        return mode
    if sys.platform.startswith("linux") and not glob.glob("/dev/video*"):
        # A headless server (a cloud VM) has no camera of its own, so the only
        # way to get an image is for the visitor's browser to supply one.
        return "browser"
    return "hardware"


CAPTURE_MODE = _resolve_capture_mode(CAPTURE_MODE_SETTING)


@app.context_processor
def inject_asset_version():
    return {
        "asset_v": ASSET_VERSION,
        "capture_mode": CAPTURE_MODE,
        # Where "Start screening" points, so templates stay mode-agnostic.
        "scan_endpoint": "/api/scan" if CAPTURE_MODE == "hardware" else "/api/browser-preview",
    }


# ─── Hardware Initialization ─────────────────────────────────────────────────
serial_bridge = SerialBridge(port=SERIAL_PORT, baud_rate=BAUD_RATE, timeout=SERIAL_TIMEOUT)
camera = CameraController(
    camera_index=CAMERA_INDEX,
    capture_width=CAPTURE_WIDTH,
    capture_height=CAPTURE_HEIGHT,
    preview_width=PREVIEW_WIDTH,
    preview_height=PREVIEW_HEIGHT,
    jpeg_quality=JPEG_QUALITY,
    captures_dir=CAPTURES_DIR,
)

# ─── Model Loading ──────────────────────────────────────────────────────────
logger.info("Loading model...")
model, device = load_model(MODEL_WEIGHTS)
logger.info(f"Model loaded on {device}")

# ─── Session State ───────────────────────────────────────────────────────────
# Simple in-memory state (single kiosk, single user at a time)
session = {
    "state": "idle",           # idle | scanning | captured | analyzing | results
    "capture_path": None,
    "result": None,
    "overlay": None,
    "report_id": None,
    "report_path": None,
    "qr_image": None,
}

# Store generated reports for download
reports_registry = {}


def get_local_ip():
    """Get the local IP address for QR code URLs."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Main kiosk page."""
    return render_template("index.html",
                           serial_info=serial_bridge.get_status_info(),
                           state=session["state"])


@app.route("/api/scan", methods=["POST"])
def start_scan():
    """Turn on lights, open camera, start preview."""
    serial_bridge.lights_on()
    serial_bridge.set_status("scan")

    if not camera.open():
        return render_template("partials/status.html",
                               status="error",
                               message="Camera not found. Please check the connection."), 500

    session["state"] = "scanning"
    session["capture_path"] = None
    session["result"] = None

    return render_template("partials/preview.html", t=int(datetime.now().timestamp()))


@app.route("/api/preview")
def video_feed():
    """MJPEG video stream for live camera preview."""
    if not camera.is_open():
        camera.open()
    response = Response(
        camera.generate_preview_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


def _analyse_and_render(capture_path, pil_image):
    """Inference, report, QR and results partial.

    Shared by both capture paths: the hardware camera and the browser upload.
    """
    serial_bridge.set_status("process")
    session["state"] = "analyzing"
    session["capture_path"] = capture_path

    # Run inference
    try:
        result = analyze_image(model, device, pil_image)
    except Exception as e:
        logger.error(f"Inference error: {e}")
        serial_bridge.set_status("idle")
        return render_template("partials/status.html",
                               status="error",
                               message=f"Analysis failed: {e}"), 500

    # Generate report
    report_id = generate_report_id()
    overlay = result["overlay"]

    try:
        report_path = generate_pdf_report(
            report_id=report_id,
            capture_path=capture_path,
            result=result,
            overlay=overlay,
            reports_dir=REPORTS_DIR
        )
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        report_path = None

    # Generate QR code
    base_url = PUBLIC_BASE_URL or f"http://{get_local_ip()}:{PORT}"
    report_url = f"{base_url}/api/report/{report_id}"

    try:
        qr_image = generate_qr_code(report_url)
        qr_filename = f"qr_{report_id}.png"
        qr_path = os.path.join(REPORTS_DIR, qr_filename)
        qr_image.save(qr_path)
    except Exception as e:
        logger.error(f"QR code generation error: {e}")
        qr_path = None

    # Update session
    session["state"] = "results"
    session["result"] = result
    session["overlay"] = overlay
    session["report_id"] = report_id
    session["report_path"] = report_path

    # Register report for download
    reports_registry[report_id] = report_path

    # Set status LED
    if result["class_name"] == "NORMAL":
        serial_bridge.set_status("normal")
    else:
        serial_bridge.set_status("pneumonia")

    # Save overlay as image for display
    overlay_filename = f"overlay_{report_id}.png"
    overlay_path = os.path.join(REPORTS_DIR, overlay_filename)
    Image.fromarray(overlay.astype(np.uint8)).save(overlay_path)

    # No-op in browser mode, where the camera was never opened
    camera.release()

    return render_template("partials/results.html",
                           result=result,
                           capture_path=capture_path,
                           overlay_path=overlay_path,
                           qr_path=qr_path,
                           report_id=report_id,
                           report_url=report_url)


@app.route("/api/capture", methods=["POST"])
def capture():
    """Capture a photo with the kiosk's own webcam and start analysis."""
    camera.stop_preview()

    capture_path, pil_image = camera.capture()
    if capture_path is None:
        serial_bridge.set_status("idle")
        serial_bridge.lights_off()
        return render_template("partials/status.html",
                               status="error",
                               message="Capture failed. Please try again."), 500

    serial_bridge.lights_off()
    return _analyse_and_render(capture_path, pil_image)


@app.route("/api/browser-preview", methods=["GET", "POST"])
def browser_preview():
    """Hand back the browser-camera UI. No server hardware is touched."""
    session["state"] = "scanning"
    session["capture_path"] = None
    session["result"] = None
    return render_template("partials/browser_preview.html")


@app.route("/api/capture-upload", methods=["POST"])
def capture_upload():
    """Analyse a frame captured by the visitor's own browser.

    cv2.VideoCapture opens a device on the machine running Python, so a hosted
    server can never reach a client's webcam. In browser mode the page grabs
    the frame with getUserMedia and posts it here instead.
    """
    uploaded = request.files.get("image")
    if uploaded is None or not uploaded.filename:
        return render_template("partials/status.html",
                               status="error",
                               message="No image received. Please try again."), 400

    try:
        pil_image = Image.open(uploaded.stream)
        pil_image = pil_image.convert("RGB")
    except Exception as e:
        logger.error(f"Upload decode error: {e}")
        return render_template("partials/status.html",
                               status="error",
                               message="That file could not be read as an image."), 400

    filename = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    capture_path = os.path.join(CAPTURES_DIR, filename)
    pil_image.save(capture_path, "JPEG", quality=JPEG_QUALITY)

    return _analyse_and_render(capture_path, pil_image)


@app.route("/api/report/<report_id>")
def download_report(report_id):
    """Download PDF report by ID."""
    report_path = reports_registry.get(report_id)
    if report_path and os.path.exists(report_path):
        return send_file(report_path, as_attachment=True,
                         download_name=f"BioFusion_Report_{report_id}.pdf")
    return "Report not found", 404


@app.route("/api/image/<path:filename>")
def serve_image(filename):
    """Serve captured images and overlays."""
    # Check in captures and reports directories
    for directory in [CAPTURES_DIR, REPORTS_DIR]:
        filepath = os.path.join(directory, os.path.basename(filename))
        if os.path.exists(filepath):
            # Filenames carry a report id or capture timestamp, so they are
            # immutable once written and safe to cache hard.
            return send_file(filepath, max_age=31536000)
    return "Image not found", 404


@app.route("/api/reset", methods=["POST"])
def reset():
    """Reset kiosk to idle state."""
    camera.stop_preview()
    camera.release()
    serial_bridge.lights_off()
    serial_bridge.set_status("idle")

    session["state"] = "idle"
    session["capture_path"] = None
    session["result"] = None
    session["overlay"] = None
    session["report_id"] = None
    session["report_path"] = None

    return render_template("partials/status.html",
                           status="idle",
                           message="Ready for next scan")


@app.route("/api/cancel", methods=["POST"])
def cancel_scan():
    """Cancel an in-progress scan."""
    camera.stop_preview()
    camera.release()
    serial_bridge.lights_off()
    serial_bridge.set_status("idle")

    session["state"] = "idle"

    return render_template("partials/status.html",
                           status="idle",
                           message="Scan cancelled")


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Connect to ESP32
    serial_bridge.connect()

    logger.info(f"Starting BioFusion Kiosk on http://{get_local_ip()}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True)
