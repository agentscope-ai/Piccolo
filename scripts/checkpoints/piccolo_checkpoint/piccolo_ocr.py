"""Optional PP-OCRv5 detection and English recognition using Transformers."""

from importlib import import_module
from math import ceil, floor
from threading import Lock

import numpy as np
import torch
from transformers import (
    AutoImageProcessor,
    AutoModelForObjectDetection,
    AutoModelForTextRecognition,
)

from .piccolo_images import map_unique_images, normalize_image

DETECTOR_ID = "PaddlePaddle/PP-OCRv5_mobile_det_safetensors"
RECOGNIZER_ID = "PaddlePaddle/en_PP-OCRv5_mobile_rec_safetensors"
MAX_IMAGE_PIXELS = 1_638_400
RECOGNITION_BATCH_SIZE = 8
DETECTION_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
DETECTION_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _detection_pixels(cv2, image):
    """Match the original detector's OpenCV resize and BGR normalization."""
    height, width = image.shape[:2]
    if height + width < 64:
        image = cv2.copyMakeBorder(
            image, 0, max(0, 32 - height), 0, max(0, 32 - width), cv2.BORDER_CONSTANT
        )
        height, width = image.shape[:2]
    scale = min(1, 960 / max(height, width))
    size = tuple(
        max(32, round(int(side * scale) / 32) * 32) for side in (width, height)
    )
    resized = cv2.resize(image, size).astype(np.float32) * (1 / 255)
    pixels = (resized - DETECTION_MEAN) / DETECTION_STD
    return torch.from_numpy(pixels.transpose(2, 0, 1)[None])


def _reading_order(boxes):
    ordered = sorted(boxes, key=lambda box: (box[0, 1], box[0, 0]))
    for index in range(1, len(ordered)):
        for j in range(index, 0, -1):
            current, previous = ordered[j][0], ordered[j - 1][0]
            if abs(current[1] - previous[1]) >= 10 or current[0] >= previous[0]:
                break
            ordered[j - 1], ordered[j] = ordered[j], ordered[j - 1]
    return ordered


def _corners(cv2, rect):
    left, other_left, right, other_right = sorted(
        cv2.boxPoints(rect), key=lambda point: point[0]
    )
    if left[1] >= other_left[1]:
        left, other_left = other_left, left
    if right[1] >= other_right[1]:
        right, other_right = other_right, right
    return np.array([left, right, other_right, other_left])


def _box_score(cv2, scores, box):
    height, width = scores.shape
    left = max(0, floor(box[:, 0].min()))
    top = max(0, floor(box[:, 1].min()))
    right = min(width - 1, ceil(box[:, 0].max()))
    bottom = min(height - 1, ceil(box[:, 1].max()))
    region = scores[top : bottom + 1, left : right + 1]
    mask = np.zeros(region.shape, dtype=np.uint8)
    cv2.fillPoly(mask, [(box - [left, top]).astype(np.int32)], 1)
    return cv2.mean(region, mask)[0]


def _detection_boxes(cv2, pyclipper, scores, size):
    """Apply PP-OCRv5 DB polygon expansion before rescaling to the image."""
    height, width = scores.shape
    scale = np.array(size) / [width, height]
    contours, _ = cv2.findContours(
        (scores > 0.3).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )
    boxes = []
    for contour in contours[:1000]:
        rect = cv2.minAreaRect(contour)
        if min(rect[1]) < 3:
            continue
        box = _corners(cv2, rect)
        if _box_score(cv2, scores, box) < 0.6:
            continue
        distance = 1.5 * cv2.contourArea(box) / cv2.arcLength(box, True)
        offset = pyclipper.PyclipperOffset()
        offset.AddPath(box, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
        polygons = offset.Execute(distance)
        if not polygons:
            continue
        try:
            expanded = np.array(polygons, dtype=np.int32).reshape(-1, 2)
        except ValueError:
            expanded = np.array(polygons[0], dtype=np.int32)
        rect = cv2.minAreaRect(expanded)
        if min(rect[1]) >= 5:
            box = np.clip(np.rint(_corners(cv2, rect) * scale), 0, size)
            boxes.append(box.astype(np.int32))
    return _reading_order(boxes)


def _crop_line(cv2, image, polygon):
    corners = _corners(cv2, cv2.minAreaRect(polygon))
    top_left, top_right, bottom_right, bottom_left = corners
    width = max(
        1,
        int(
            max(
                np.linalg.norm(top_right - top_left),
                np.linalg.norm(bottom_right - bottom_left),
            )
        ),
    )
    height = max(
        1,
        int(
            max(
                np.linalg.norm(bottom_left - top_left),
                np.linalg.norm(bottom_right - top_right),
            )
        ),
    )
    target = np.array(
        [[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float32
    )
    matrix = cv2.getPerspectiveTransform(corners, target)
    crop = cv2.warpPerspective(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return np.rot90(crop).copy() if height / width >= 1.5 else crop


def _recognition_pixels(cv2, crops):
    """Resize BGR lines at their own aspect ratios and right-pad the batch."""
    widths = [48 * (crop.shape[1] / crop.shape[0]) for crop in crops]
    pads = [min(3200, max(320, int(width))) for width in widths]
    pixels = np.zeros((len(crops), 3, 48, max(pads)), dtype=np.float32)
    for index, (crop, width, pad) in enumerate(zip(crops, widths, pads, strict=True)):
        width = min(pad, ceil(width))
        resized = cv2.resize(crop, (width, 48)).astype(np.float32).transpose(2, 0, 1)
        pixels[index, :, :, :width] = (resized / 255.0 - 0.5) / 0.5
    return torch.from_numpy(pixels)


class TorchOCR:
    """Load local OCR weights once and reuse them for request images."""

    def __init__(self, detector=DETECTOR_ID, recognizer=RECOGNIZER_ID, *, device="cpu"):
        try:
            self._cv2 = import_module("cv2")
            self._pyclipper = import_module("pyclipper")
        except ImportError as error:
            raise RuntimeError(
                "Torch OCR requires opencv-python-headless and pyclipper"
            ) from error
        self.device = torch.device(device)
        opts = {"local_files_only": True, "dtype": torch.float32}
        self.detector = (
            AutoModelForObjectDetection.from_pretrained(detector, **opts)
            .to(self.device)
            .eval()
        )
        self.recognizer = (
            AutoModelForTextRecognition.from_pretrained(recognizer, **opts)
            .to(self.device)
            .eval()
        )
        self.rec_processor = AutoImageProcessor.from_pretrained(
            recognizer, local_files_only=True
        )
        self._lock = Lock()

    @torch.inference_mode()
    def recognize(self, images):
        with self._lock, torch.autocast(self.device.type, enabled=False):
            return map_unique_images(images, self._recognize)

    def _recognize(self, image):
        image = normalize_image(image, MAX_IMAGE_PIXELS)
        bgr = np.asarray(image)[:, :, ::-1].copy()
        pixels = _detection_pixels(self._cv2, bgr).to(self.device)
        detected = self.detector(pixel_values=pixels)
        scores = detected.last_hidden_state[0, 0].float().cpu().numpy()
        boxes = _detection_boxes(self._cv2, self._pyclipper, scores, image.size)
        crops = [_crop_line(self._cv2, bgr, box) for box in boxes]
        # Group similar widths for recognition, then restore reading order.
        order = sorted(
            range(len(crops)), key=lambda i: crops[i].shape[1] / crops[i].shape[0]
        )
        lines = [""] * len(crops)
        for start in range(0, len(order), RECOGNITION_BATCH_SIZE):
            indices = order[start : start + RECOGNITION_BATCH_SIZE]
            batch = [crops[i] for i in indices]
            pixels = _recognition_pixels(self._cv2, batch).to(self.device)
            prediction = self.recognizer(pixel_values=pixels)
            prediction.last_hidden_state = prediction.last_hidden_state.cpu()
            decoded = self.rec_processor.post_process_text_recognition(prediction)
            for index, item in zip(indices, decoded, strict=True):
                lines[index] = item["text"]
        return "\n".join(lines)
