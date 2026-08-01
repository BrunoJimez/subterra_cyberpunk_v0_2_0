from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

from .config import CHARACTER_ROLES, MOTION_CHOICES


@dataclass
class CharacterSpec:
    path: str
    name: str = "character"
    role: str = "support"
    motion: str = "auto"
    scale: float = 0.72
    depth: float = 0.5
    flip: bool = False

    @classmethod
    def parse(cls, raw: str) -> "CharacterSpec":
        """Parse PATH::ROLE::MOTION::NAME. Only PATH is required."""
        parts = raw.split("::")
        path = parts[0].strip()
        role = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "support"
        motion = parts[2].strip() if len(parts) > 2 and parts[2].strip() else "auto"
        name = parts[3].strip() if len(parts) > 3 and parts[3].strip() else Path(path).stem
        if role not in CHARACTER_ROLES:
            role = "support"
        if motion not in MOTION_CHOICES:
            motion = "auto"
        return cls(path=path, role=role, motion=motion, name=name)


def _relevant_components(mask: np.ndarray) -> np.ndarray:
    binary = (mask > 32).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if n <= 1:
        return mask
    areas = stats[1:, cv2.CC_STAT_AREA]
    largest = max(1, int(areas.max()))
    keep = np.zeros_like(binary)
    for idx, area in enumerate(areas, start=1):
        if int(area) >= max(20, int(largest * .018)):
            keep[labels == idx] = 1
    return np.where(keep > 0, mask, 0).astype(np.uint8)


def _border_distance_mask(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    strip_h = max(1, h // 20); strip_w = max(1, w // 20)
    border = np.concatenate([
        image[:strip_h].reshape(-1, 3), image[-strip_h:].reshape(-1, 3),
        image[:, :strip_w].reshape(-1, 3), image[:, -strip_w:].reshape(-1, 3),
    ], axis=0).astype(np.float32)
    bg = np.median(border, axis=0)
    dist = np.linalg.norm(image.astype(np.float32) - bg[None, None, :], axis=2)
    lo, hi = np.percentile(dist, [48, 88])
    alpha = np.clip((dist - lo) / max(1.0, hi - lo), 0, 1)
    yy, xx = np.mgrid[0:h, 0:w]
    center = 1.0 - np.clip(np.sqrt(((xx-w*.5)/(w*.72))**2 + ((yy-h*.5)/(h*.78))**2), 0, 1)
    alpha = np.maximum(alpha, center * .58)
    return np.clip(alpha * 255, 0, 255).astype(np.uint8)


def _detect_faces(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    try:
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.07, 4, minSize=(28, 28))
        return [tuple(map(int, f)) for f in faces]
    except Exception:
        return []


def _face_guided_mask(image: np.ndarray) -> np.ndarray | None:
    faces = _detect_faces(image)
    if not faces:
        return None
    h, w = image.shape[:2]
    mask = np.full((h, w), cv2.GC_BGD, np.uint8)
    for x, y, fw, fh in faces:
        x0=max(0,x-int(fw*.18)); x1=min(w,x+fw+int(fw*.18))
        y0=max(0,y-int(fh*.18)); y1=min(h,y+fh+int(fh*.18))
        mask[y0:y1,x0:x1]=cv2.GC_FGD
        bx0=max(0,x-int(fw*.95)); bx1=min(w,x+fw+int(fw*.95))
        by0=max(0,y-int(fh*.10)); by1=min(h,y+int(fh*5.2))
        mask[by0:by1,bx0:bx1]=np.maximum(mask[by0:by1,bx0:bx1],cv2.GC_PR_FGD)
        mask[y0:y1,x0:x1]=cv2.GC_FGD
    try:
        bg_model=np.zeros((1,65),np.float64); fg_model=np.zeros((1,65),np.float64)
        cv2.grabCut(image,mask,None,bg_model,fg_model,4,cv2.GC_INIT_WITH_MASK)
        return np.where((mask==cv2.GC_FGD)|(mask==cv2.GC_PR_FGD),255,0).astype(np.uint8)
    except cv2.error:
        return None


def extract_subject(image: np.ndarray, mode: str = "auto") -> tuple[np.ndarray, np.ndarray]:
    if image.ndim != 3:
        raise ValueError("Imagem de personagem inválida.")
    useful_alpha = image.shape[2] == 4 and float(np.mean(image[:, :, 3] < 250)) > .001
    if useful_alpha:
        bgr = image[:, :, :3].copy(); alpha = image[:, :, 3].copy()
    else:
        bgr = image[:, :, :3].copy(); h, w = bgr.shape[:2]; alpha = None
        if mode != "none" and min(h, w) >= 80:
            alpha = _face_guided_mask(bgr)
            if alpha is None:
                try:
                    mask = np.zeros((h, w), np.uint8)
                    bg_model = np.zeros((1, 65), np.float64); fg_model = np.zeros((1, 65), np.float64)
                    inset_x = max(2, int(w * .025)); inset_y = max(2, int(h * .025))
                    rect = (inset_x, inset_y, max(2, w - 2*inset_x), max(2, h - 2*inset_y))
                    cv2.grabCut(bgr, mask, rect, bg_model, fg_model, 4, cv2.GC_INIT_WITH_RECT)
                    alpha = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
                except cv2.error:
                    alpha = None
            if alpha is not None:
                coverage = float(np.mean(alpha > 0))
                if coverage < .025 or coverage > .94:
                    alpha = None
        if alpha is None:
            alpha = _border_distance_mask(bgr)
    alpha = _relevant_components(alpha)
    k = max(3, int(round(min(alpha.shape) * .008)) | 1)
    alpha = cv2.GaussianBlur(alpha, (k, k), 0)
    return bgr, alpha


def _crop_to_alpha(bgr: np.ndarray, alpha: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.where(alpha > 12)
    if len(xs) == 0:
        return bgr, np.full(bgr.shape[:2], 255, np.uint8)
    pad = max(4, int(min(bgr.shape[:2]) * .025))
    x0, x1 = max(0, int(xs.min()) - pad), min(bgr.shape[1], int(xs.max()) + pad + 1)
    y0, y1 = max(0, int(ys.min()) - pad), min(bgr.shape[0], int(ys.max()) + pad + 1)
    return bgr[y0:y1, x0:x1].copy(), alpha[y0:y1, x0:x1].copy()


def alpha_composite(dst: np.ndarray, src: np.ndarray, alpha: np.ndarray, x: int, y: int) -> None:
    h, w = src.shape[:2]
    x0, y0 = max(0, x), max(0, y); x1, y1 = min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    sx0, sy0 = x0 - x, y0 - y; sx1, sy1 = sx0 + (x1-x0), sy0 + (y1-y0)
    a = alpha[sy0:sy1, sx0:sx1].astype(np.float32)[..., None] / 255.0
    roi = dst[y0:y1, x0:x1].astype(np.float32); fg = src[sy0:sy1, sx0:sx1].astype(np.float32)
    dst[y0:y1, x0:x1] = np.clip(fg*a + roi*(1-a), 0, 255).astype(np.uint8)


class CharacterAsset:
    def __init__(self, spec: CharacterSpec, extraction: str = "auto"):
        self.spec = spec
        raw = cv2.imread(spec.path, cv2.IMREAD_UNCHANGED)
        if raw is None:
            raise FileNotFoundError(f"Imagem de personagem não encontrada ou inválida: {spec.path}")
        bgr, alpha = extract_subject(raw, extraction)
        self.bgr, self.alpha = _crop_to_alpha(bgr, alpha)
        if spec.flip:
            self.bgr = cv2.flip(self.bgr, 1); self.alpha = cv2.flip(self.alpha, 1)
        self.seed = int(hashlib.sha1(str(Path(spec.path).resolve()).encode()).hexdigest()[:8], 16)
        self.face = self._detect_face()
        self.rig = self._infer_rig()

    @property
    def aspect(self) -> float:
        return self.bgr.shape[1] / max(1, self.bgr.shape[0])

    def _detect_face(self) -> tuple[int, int, int, int] | None:
        faces = _detect_faces(self.bgr)
        return tuple(max(faces, key=lambda r: r[2] * r[3])) if faces else None

    def _infer_rig(self) -> dict[str, float | bool | list[float]]:
        h, w = self.bgr.shape[:2]
        if self.face:
            x, y, fw, fh = self.face
            head_center = [(x + fw*.5)/w, (y + fh*.48)/h]
            head_size = [fw/w, fh/h]
            shoulder_y = min(.58, (y + fh*1.65)/h)
        else:
            head_center = [.5, .18]; head_size = [.25, .22]; shoulder_y = .34
        return {
            "version": 2,
            "face_detected": bool(self.face),
            "head_center": [round(float(v), 5) for v in head_center],
            "head_size": [round(float(v), 5) for v in head_size],
            "shoulder_y": round(float(shoulder_y), 5),
            "pelvis_y": .68,
            "ground_y": .98,
            "left_hand_hint": [.18, .62],
            "right_hand_hint": [.82, .62],
        }

    def save_bundle(self, png_path: str | Path) -> tuple[Path, Path]:
        out = Path(png_path); out.parent.mkdir(parents=True, exist_ok=True)
        rgba = cv2.cvtColor(self.bgr, cv2.COLOR_BGR2BGRA); rgba[:, :, 3] = self.alpha
        if not cv2.imwrite(str(out), rgba):
            raise RuntimeError(f"Não foi possível salvar {out}")
        rig_path = out.with_suffix(".rig.json")
        rig_path.write_text(json.dumps({"character": asdict(self.spec), "rig": self.rig}, ensure_ascii=False, indent=2), encoding="utf-8")
        return out, rig_path

    def _zone_masks(self, h: int, w: int) -> dict[str, np.ndarray]:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        yn = yy / max(1, h-1); xn = xx / max(1, w-1)
        hx, hy = self.rig["head_center"]  # type: ignore[misc]
        hsx, hsy = self.rig["head_size"]  # type: ignore[misc]
        head = np.exp(-(((xn-hx)/max(.08, hsx*.75))**2 + ((yn-hy)/max(.07, hsy*.80))**2)*1.6)
        torso = np.clip(1 - np.abs(yn-.52)/.33, 0, 1) * np.clip(1 - np.abs(xn-.5)/.62, 0, 1)
        lower = np.clip((yn-.50)/.48, 0, 1)
        left = np.clip((.55-xn)/.45, 0, 1) * torso
        right = np.clip((xn-.45)/.45, 0, 1) * torso
        outer = np.clip(np.abs(xn-.5)/.5, 0, 1) * np.clip((.75-yn)/.75, 0, 1)
        return {"head": head.astype(np.float32), "torso": torso.astype(np.float32), "lower": lower.astype(np.float32),
                "left": left.astype(np.float32), "right": right.astype(np.float32), "outer": outer.astype(np.float32)}

    @staticmethod
    def _ease(p: float) -> float:
        p = float(np.clip(p, 0, 1)); return p*p*(3-2*p)

    def _deform(self, image: np.ndarray, alpha: np.ndarray, t: float, energy: float, impact: float,
                motion: str, strength: float, secondary: float, phase_offset: float) -> tuple[np.ndarray, np.ndarray]:
        h, w = image.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        z = self._zone_masks(h, w)
        phase = t * (1.15 + energy * 1.9) + (self.seed % 1000) / 137.0 + phase_offset*math.tau
        breath = math.sin(phase) * (1.0 + 2.8*strength)
        dx = math.sin(phase*.68) * w*.010*strength*z["head"]
        dy = -breath*z["torso"]
        # Secondary motion: hair, coat edges and detached graphic shapes trail behind the torso.
        dx += math.sin(phase*.82-.8) * w*.018*secondary*z["outer"]
        dy += math.cos(phase*.71-.5) * h*.006*secondary*z["outer"]

        if motion in {"sway", "dance", "sing"}:
            dx += math.sin(t*(2.2+energy*3.0)+phase_offset) * w*(.014+.035*strength) * (z["torso"] + .55*z["lower"])
            dy += -impact*h*.014*z["torso"]
            if motion == "dance":
                dx += math.sin(t*5.2+phase_offset*3) * w*.032*strength*(z["left"]-z["right"])
                dy += math.cos(t*4.6) * h*.014*strength*z["lower"]
        elif motion in {"walk", "run"}:
            speed = 6.1 if motion == "run" else 3.4
            step = math.sin(t*speed + phase_offset*math.tau)
            dy += step*h*(.014 if motion == "run" else .009)*strength*z["lower"]
            dx += math.sin(t*speed*.5)*w*.015*z["torso"]
            dx += step*w*.025*strength*(z["left"]-z["right"])
        elif motion == "dramatic_turn":
            p = self._ease(min(1.0, (t % 3.2)/.75))
            dx += math.sin(p*math.pi)*w*.075*z["head"]*strength
            dx += math.sin(p*math.pi*.7)*w*.025*z["torso"]*strength
        elif motion in {"look_left", "look_right"}:
            direction = -1 if motion == "look_left" else 1
            dx += direction*w*.035*(.55+.45*math.sin(t*.8)**2)*z["head"]*strength
        elif motion == "nod":
            dy += math.sin(t*3.1)*h*.018*z["head"]*strength
        elif motion == "reach":
            dx += w*.055*z["right"]*strength*(.55+.45*math.sin(t*1.6))
            dy -= h*.022*z["right"]*strength
        elif motion == "recoil":
            pulse = math.exp(-((t % 1.4)-.18)**2/.018)
            dx -= pulse*w*.055*z["torso"]*strength
            dy += pulse*h*.022*z["head"]*strength
        elif motion == "crouch":
            p = .5+.5*math.sin(t*1.4)
            dy += p*h*.10*z["torso"]*strength + p*h*.04*z["head"]*strength
        elif motion == "jump":
            jump = abs(math.sin(t*1.65+phase_offset*2))*h*.08*strength
            dy -= jump*(z["head"]+z["torso"]+z["lower"])
        elif motion == "fight_pose":
            dx += math.sin(t*1.8)*w*.025*z["head"]
            dx += w*.045*(z["left"]-z["right"])*strength
            dy -= h*.025*(z["left"]+z["right"])*strength
        elif motion == "levitate":
            dy += math.sin(t*1.4)*h*.022*strength
        elif motion in {"glitch", "hologram"}:
            bands = ((yy.astype(np.int32)//max(2,h//24))%3==0).astype(np.float32)
            dx += bands*math.sin(t*17.0)*w*.020*max(impact,.25)

        map_x = np.clip(xx-dx, 0, w-1).astype(np.float32)
        map_y = np.clip(yy-dy, 0, h-1).astype(np.float32)
        out = cv2.remap(image, map_x, map_y, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
        a = cv2.remap(alpha, map_x, map_y, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
        return out, a

    def _blink(self, image: np.ndarray, alpha: np.ndarray, t: float, rate: float) -> tuple[np.ndarray, np.ndarray]:
        if self.face is None or rate <= 0:
            return image, alpha
        interval = 4.0 + (self.seed % 30)/10.0; phase = t % interval
        amount = max(0.0, 1.0-abs(phase-.13)/.13)*rate
        if amount <= .02:
            return image, alpha
        x,y,w,h=self.face; y0=max(0,y+int(h*.24)); y1=min(image.shape[0],y+int(h*.52)); x0=max(0,x+int(w*.08)); x1=min(image.shape[1],x+int(w*.92))
        roi=image[y0:y1,x0:x1]; ar=alpha[y0:y1,x0:x1]
        if roi.size==0:return image,alpha
        nh=max(1,int(roi.shape[0]*(1-.72*amount))); shrunk=cv2.resize(roi,(roi.shape[1],nh),interpolation=cv2.INTER_AREA); shrunk_a=cv2.resize(ar,(ar.shape[1],nh),interpolation=cv2.INTER_AREA)
        canvas=np.zeros_like(roi);canvas_a=np.zeros_like(ar);off=(roi.shape[0]-nh)//2;canvas[off:off+nh]=shrunk;canvas_a[off:off+nh]=shrunk_a
        canvas=cv2.inpaint(canvas,(canvas_a<10).astype(np.uint8)*255,2,cv2.INPAINT_TELEA)
        image=image.copy();alpha=alpha.copy();image[y0:y1,x0:x1]=canvas;alpha[y0:y1,x0:x1]=np.maximum(canvas_a,ar)
        return image,alpha

    def _mouth_pulse(self, image: np.ndarray, alpha: np.ndarray, pulse: float) -> tuple[np.ndarray, np.ndarray]:
        if self.face is None or pulse <= .01:
            return image, alpha
        x,y,w,h=self.face; x0=max(0,x+int(w*.22));x1=min(image.shape[1],x+int(w*.78));y0=max(0,y+int(h*.60));y1=min(image.shape[0],y+int(h*.82))
        roi=image[y0:y1,x0:x1]; ar=alpha[y0:y1,x0:x1]
        if roi.size==0:return image,alpha
        factor=1.0+.24*float(np.clip(pulse,0,1));nh=max(1,int(roi.shape[0]*factor));grown=cv2.resize(roi,(roi.shape[1],nh),interpolation=cv2.INTER_CUBIC);grown_a=cv2.resize(ar,(ar.shape[1],nh),interpolation=cv2.INTER_CUBIC)
        crop=(nh-roi.shape[0])//2; grown=grown[crop:crop+roi.shape[0]];grown_a=grown_a[crop:crop+roi.shape[0]]
        out=image.copy();ao=alpha.copy();out[y0:y1,x0:x1]=grown;ao[y0:y1,x0:x1]=np.maximum(ar,grown_a)
        return out,ao

    def rendered(self, t: float, energy: float, impact: float, motion: str, strength: float,
                 target_height: int, outline: float=.5, world: str="neon_graphic_grit", facing: int=1,
                 secondary_motion: float=.68, lip_sync: float=.65, phase: float=0.0) -> tuple[np.ndarray, np.ndarray]:
        if motion == "auto":
            motion = "sing" if self.spec.role in {"vocalist","performer"} else "sway" if self.spec.role=="crowd" else "idle"
        img, alpha = self._deform(self.bgr, self.alpha, t, energy, impact, motion, strength, secondary_motion, phase)
        img, alpha = self._blink(img, alpha, t+phase*2.0, .75)
        if motion == "sing" and lip_sync > 0:
            vocal_pulse = np.clip((energy*.45 + impact*.85) * (.55+.45*abs(math.sin(t*8.0+phase*5))), 0, 1)
            img, alpha = self._mouth_pulse(img, alpha, vocal_pulse*lip_sync)
        if facing < 0:
            img=cv2.flip(img,1);alpha=cv2.flip(alpha,1)
        if motion=="hologram" or self.spec.role=="hologram":
            img=cv2.cvtColor(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY),cv2.COLOR_GRAY2BGR)
            img[:,:,0]=np.clip(img[:,:,0].astype(np.float32)*1.35+25,0,255);img[:,:,2]=np.clip(img[:,:,2].astype(np.float32)*.8+40,0,255)
            alpha=(alpha.astype(np.float32)*(.55+.25*math.sin(t*9.0))).clip(0,255).astype(np.uint8);alpha[::4]=(alpha[::4].astype(np.float32)*.35).astype(np.uint8)
        elif motion=="glitch" and impact>.35:
            shift=max(1,int(img.shape[1]*.012*impact));b,g,r=cv2.split(img);b=np.roll(b,shift,1);r=np.roll(r,-shift,1);img=cv2.merge([b,g,r])
        scale=target_height/max(1,img.shape[0]);tw=max(2,int(img.shape[1]*scale));th=max(2,int(target_height))
        img=cv2.resize(img,(tw,th),interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_CUBIC);alpha=cv2.resize(alpha,(tw,th),interpolation=cv2.INTER_CUBIC)
        if outline>0:
            k=max(1,int(round(min(tw,th)*(.004+outline*.006))));kernel=np.ones((k*2+1,k*2+1),np.uint8);edge=cv2.dilate(alpha,kernel)-alpha
            color=np.zeros_like(img);color[:]=(15,8,24) if world=="future_noir_cel" else (12,5,20);canvas=np.zeros_like(img);canvas[edge>0]=color[edge>0]
            expanded=cv2.dilate(alpha,kernel);a=alpha.astype(np.float32)[...,None]/255.0;img=np.clip(img.astype(np.float32)*a+canvas.astype(np.float32)*(1-a),0,255).astype(np.uint8);alpha=np.maximum(alpha,expanded)
        return img,alpha
