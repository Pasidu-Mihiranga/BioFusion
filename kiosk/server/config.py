"""
BioFusion Kiosk — Configuration
All hardware and application settings in one place.
"""

import os

# ─── ESP32 Serial ────────────────────────────────────────────────────────────
SERIAL_PORT = os.environ.get("KIOSK_SERIAL_PORT", "/dev/tty.usbserial-0001")
BAUD_RATE = int(os.environ.get("KIOSK_BAUD_RATE", "115200"))
SERIAL_TIMEOUT = 2  # seconds

# ─── Camera ──────────────────────────────────────────────────────────────────
CAMERA_INDEX = int(os.environ.get("KIOSK_CAMERA_INDEX", "2"))
CAPTURE_WIDTH = 1920
CAPTURE_HEIGHT = 1080
PREVIEW_WIDTH = 640
PREVIEW_HEIGHT = 480
JPEG_QUALITY = 90

# ─── Model ───────────────────────────────────────────────────────────────────
# Checkpoints are shared with the Streamlit app and live outside the tracked
# tree (*.pth is gitignored), so a deploy's `git reset --hard` leaves them be.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.environ.get("BIOFUSION_MODELS_DIR", os.path.join(_REPO_ROOT, "models"))

# The kiosk photographs a film under a light box, so it wants the checkpoint
# trained with phone-photo augmentation rather than the direct-radiograph one.
MODEL_WEIGHTS = os.environ.get(
    "KIOSK_MODEL_WEIGHTS", os.path.join(MODELS_DIR, "pneumonia_resnet50_best.pth")
)

# Fall back to the older in-tree location if the shared dir has not been populated.
if not os.path.exists(MODEL_WEIGHTS):
    _legacy = os.path.join(os.path.dirname(__file__), "model", "pneumonia_resnet50_best.pth")
    if os.path.exists(_legacy):
        MODEL_WEIGHTS = _legacy

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTURES_DIR = os.path.join(os.path.dirname(BASE_DIR), "captures")
REPORTS_DIR = os.path.join(os.path.dirname(BASE_DIR), "reports")

# Ensure directories exist
os.makedirs(CAPTURES_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# ─── Server ──────────────────────────────────────────────────────────────────
HOST = os.environ.get("KIOSK_HOST", "0.0.0.0")
PORT = int(os.environ.get("KIOSK_PORT", "5050"))
DEBUG = os.environ.get("KIOSK_DEBUG", "false").lower() == "true"

# Public base URL used in QR codes / report links (e.g. https://kiosk.example.com).
# Leave unset for local hardware use — the app then falls back to the LAN IP:port.
PUBLIC_BASE_URL = os.environ.get("KIOSK_PUBLIC_BASE_URL", "").rstrip("/")

# ─── UI ──────────────────────────────────────────────────────────────────────
AUTO_RESET_SECONDS = 60  # auto-reset to idle after this many seconds
