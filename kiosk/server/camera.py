"""
BioFusion Kiosk — Camera Controller
USB webcam capture and MJPEG preview streaming via OpenCV.
"""

import cv2
import time
import os
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CameraController:
    """Manages USB webcam for live preview and high-res capture."""

    def __init__(self, camera_index=0, capture_width=1920, capture_height=1080,
                 preview_width=640, preview_height=480, jpeg_quality=90,
                 captures_dir="captures"):
        self.camera_index = camera_index
        self.capture_width = capture_width
        self.capture_height = capture_height
        self.preview_width = preview_width
        self.preview_height = preview_height
        self.jpeg_quality = jpeg_quality
        self.captures_dir = captures_dir

        self.cap = None
        self._lock = threading.Lock()
        self._preview_active = False

    def open(self):
        """Open the webcam. Returns True if successful."""
        with self._lock:
            if self.cap and self.cap.isOpened():
                return True
            # Re-enable DSHOW as MSMF fails on this webcam (Windows only)
            import os
            backend = cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY
            self.cap = cv2.VideoCapture(self.camera_index, backend)
            if not self.cap.isOpened():
                logger.error(f"Failed to open camera at index {self.camera_index}")
                self.cap = None
                return False
            # Let the camera use its native resolution to avoid DSHOW static/corruption bugs
            # self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.preview_width)
            # self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.preview_height)
            logger.info(f"Camera opened at index {self.camera_index}")
            return True

    def release(self):
        """Release the webcam."""
        with self._lock:
            self._preview_active = False
            if self.cap and self.cap.isOpened():
                self.cap.release()
                logger.info("Camera released")
            self.cap = None

    def is_open(self):
        """Check if camera is currently open."""
        return self.cap is not None and self.cap.isOpened()

    def generate_preview_frames(self):
        """
        Generator that yields MJPEG frames for live preview.
        Used with Flask's streaming response.
        """
        self._preview_active = True
        while self._preview_active:
            with self._lock:
                if not self.cap or not self.cap.isOpened():
                    break
                ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            # Resize for preview (maintain landscape/original aspect ratio)
            # The CSS object-fit: cover will handle cropping it to the portrait frame
            frame = cv2.resize(frame, (self.preview_width, self.preview_height))

            # Encode as JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_bytes = buffer.tobytes()

            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
            )

            time.sleep(0.033)  # ~30fps cap

    def stop_preview(self):
        """Stop the preview stream."""
        self._preview_active = False

    def capture(self):
        """
        Capture a high-resolution frame.
        Returns: (image_path, pil_image) or (None, None) on failure.
        """
        from PIL import Image
        import numpy as np

        with self._lock:
            if not self.cap or not self.cap.isOpened():
                logger.error("Camera not open for capture")
                return None, None

            # Don't switch resolutions dynamically, it breaks DSHOW webcams
            # self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.capture_width)
            # self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.capture_height)
            time.sleep(0.3)  # Let camera adjust

            # Grab a few frames to let auto-exposure settle
            for _ in range(5):
                self.cap.read()

            ret, frame = self.cap.read()

            # Don't switch resolutions dynamically
            # self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.preview_width)
            # self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.preview_height)

        if not ret:
            logger.error("Failed to capture frame")
            return None, None

        # Save to captures directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"capture_{timestamp}.jpg"
        filepath = os.path.join(self.captures_dir, filename)

        cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        logger.info(f"Captured image: {filepath}")

        # Convert BGR (OpenCV) to RGB (PIL)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)

        return filepath, pil_image
