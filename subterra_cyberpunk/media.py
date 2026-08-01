from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def cover_resize(frame: np.ndarray, width: int, height: int, zoom: float = 1.0, pan_x: float = 0.0, pan_y: float = 0.0) -> np.ndarray:
    h, w = frame.shape[:2]
    scale = max(width / max(w, 1), height / max(h, 1)) * max(1.0, zoom)
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    extra_x, extra_y = max(0, nw - width), max(0, nh - height)
    x = int(np.clip(extra_x * (0.5 + pan_x * 0.45), 0, extra_x))
    y = int(np.clip(extra_y * (0.5 + pan_y * 0.45), 0, extra_y))
    return resized[y:y + height, x:x + width].copy()


class MediaPool:
    def __init__(self, paths: list[str], width: int, height: int):
        self.width = width
        self.height = height
        self.items: list[dict] = []
        for raw in paths:
            p = Path(raw)
            ext = p.suffix.lower()
            if ext in _IMAGE_EXTS:
                image = cv2.imread(str(p), cv2.IMREAD_COLOR)
                if image is not None:
                    self.items.append({"kind": "image", "path": p, "frame": image})
            elif ext in _VIDEO_EXTS:
                cap = cv2.VideoCapture(str(p))
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
                    self.items.append({"kind": "video", "path": p, "cap": cap, "fps": fps, "frames": max(1, frames), "last_index": None, "last_frame": None})

    def __len__(self) -> int:
        return len(self.items)

    def get(
        self,
        index: int,
        t: float,
        speed: float = 1.0,
        offset: float = 0.0,
        zoom: float = 1.0,
        pan_x: float = 0.0,
        pan_y: float = 0.0,
    ) -> np.ndarray | None:
        if not self.items:
            return None
        item = self.items[index % len(self.items)]
        if item["kind"] == "image":
            return cover_resize(item["frame"], self.width, self.height, zoom, pan_x, pan_y)
        cap = item["cap"]
        frame_index = int(max(0.0, t * speed + offset) * item["fps"]) % item["frames"]
        last_index = item.get("last_index")
        frame = item.get("last_frame")
        ok = frame is not None and frame_index == last_index
        if not ok and last_index is not None and 0 < frame_index - last_index <= 8:
            # Sequential/near-sequential access is much faster than seeking on every output frame.
            ok = True
            for _ in range(frame_index - last_index):
                if not cap.grab():
                    ok = False
                    break
            if ok:
                ok, frame = cap.retrieve()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
            frame_index = 0
        if ok:
            item["last_index"] = frame_index
            item["last_frame"] = frame
            return cover_resize(frame, self.width, self.height, zoom, pan_x, pan_y)
        return None

    def close(self) -> None:
        for item in self.items:
            if item["kind"] == "video":
                item["cap"].release()
