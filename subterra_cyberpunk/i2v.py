from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _cover(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    h, w = frame.shape[:2]
    scale = max(width/max(1,w), height/max(1,h))
    nw, nh = max(2,int(round(w*scale))), max(2,int(round(h*scale)))
    resized = cv2.resize(frame,(nw,nh),interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_CUBIC)
    x=max(0,(nw-width)//2);y=max(0,(nh-height)//2)
    return resized[y:y+height,x:x+width].copy()


class I2VClipPool:
    """Reads optional local image-to-video clips named shot_0000.mp4, shot_0001.mp4, etc."""
    def __init__(self, directory: str | Path | None, width: int, height: int):
        self.directory = Path(directory) if directory else None
        self.width=width;self.height=height
        self.captures: dict[int, cv2.VideoCapture] = {}
        self.meta: dict[int, tuple[float,float,int]] = {}
        if self.directory and self.directory.exists():
            for path in self.directory.glob("shot_*.*"):
                if path.suffix.lower() not in {".mp4",".mkv",".mov",".avi",".webm"}:
                    continue
                try: shot_id=int(path.stem.split("_")[-1])
                except ValueError: continue
                cap=cv2.VideoCapture(str(path))
                if not cap.isOpened():
                    cap.release();continue
                fps=float(cap.get(cv2.CAP_PROP_FPS) or 24.0);frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                duration=frames/max(.001,fps)
                self.captures[shot_id]=cap;self.meta[shot_id]=(fps,duration,frames)

    def has(self, shot_id: int) -> bool:
        return shot_id in self.captures

    def get(self, shot_id: int, local_t: float) -> np.ndarray | None:
        cap=self.captures.get(shot_id)
        if cap is None:return None
        fps,duration,frames=self.meta[shot_id]
        t=max(0.0,local_t)
        if duration>0:t=min(t,duration-1/max(fps,1))
        index=min(max(0,int(round(t*fps))),max(0,frames-1))
        cap.set(cv2.CAP_PROP_POS_FRAMES,index)
        ok,frame=cap.read()
        if not ok:return None
        return _cover(frame,self.width,self.height)

    def close(self) -> None:
        for cap in self.captures.values():cap.release()
        self.captures.clear()


class ShotPackageWriter:
    """Exports deterministic keyframes and metadata for any local I2V application."""
    def __init__(self, directory: str | Path | None, story: dict[str, Any], width: int, height: int, fps: float):
        self.directory=Path(directory) if directory else None
        self.story=story;self.width=width;self.height=height;self.fps=fps;self.written:set[int]=set()
        if self.directory:
            self.directory.mkdir(parents=True,exist_ok=True)
            (self.directory/"README_I2V.txt").write_text(
                "SUBTERRA-CYBERPUNK — pacote local image-to-video\n\n"
                "Cada shot_XXXX_keyframe.png é o quadro inicial de um plano.\n"
                "Cada shot_XXXX.json contém duração, prompt, câmera, mundo e ações.\n"
                "Gere um clipe local com a mesma duração, salve como shot_XXXX.mp4 e, no programa, selecione esta pasta como Pasta de clipes I2V.\n"
                "Nenhuma API paga é usada. O modelo/aplicativo generativo não é incluído no pacote principal.\n",
                encoding="utf-8",
            )

    def write(self, shot: dict[str, Any], frame: np.ndarray) -> None:
        if self.directory is None:return
        sid=int(shot.get("shot",0))
        if sid in self.written:return
        self.written.add(sid)
        key=self.directory/f"shot_{sid:04d}_keyframe.png"
        cv2.imwrite(str(key),frame)
        metadata={
            "shot":sid,
            "start":shot.get("start"),"end":shot.get("end"),"duration":shot.get("duration"),
            "fps":self.fps,"width":self.width,"height":self.height,
            "world":shot.get("world"),"location":shot.get("location"),"camera":shot.get("camera"),
            "characters":shot.get("visible_characters",[]),"blocking":shot.get("blocking",{}),
            "prompt":shot.get("prompt","") + "; animate naturally; no camera cuts inside the clip; keep first-frame identity",
            "negative_prompt":"identity drift, costume change, extra limbs, duplicate face, unreadable anatomy, watermark, logo, text",
            "expected_output":f"shot_{sid:04d}.mp4",
        }
        (self.directory/f"shot_{sid:04d}.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")

    def finalize(self) -> None:
        if self.directory is None:return
        manifest={
            "version":"0.2.0","engine":"SUBTERRA-CYBERPUNK Local I2V Bridge",
            "shot_count":len(self.written),"shots":sorted(self.written),
            "naming":"shot_XXXX.mp4",
        }
        (self.directory/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
