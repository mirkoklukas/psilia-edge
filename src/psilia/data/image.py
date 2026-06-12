"""NumPy / OpenCV image helpers."""

from __future__ import annotations

import cv2
import numpy as np


def bgr_to_gray(bgr: np.ndarray) -> np.ndarray:
    """Convert an H×W×3 BGR image to H×W grayscale (``uint8`` or same float dtype as input).

    Uses OpenCV ``COLOR_BGR2GRAY`` (BT.601 luma), matching ``cv2.imdecode`` frame layout.
    """
    if bgr.ndim != 3 or bgr.shape[-1] != 3:
        raise ValueError(f"expected H×W×3 BGR array, got shape {tuple(bgr.shape)}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
