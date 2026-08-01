from __future__ import annotations

"""Authorial post-production filters for SUBTERRA.

The presets reproduce broad visual families familiar from mobile social-video
editors (vintage, cinematic, vibrant, monochrome, glitch, etc.) without trying
to clone proprietary LUTs byte-for-byte.
"""

from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np


@dataclass(frozen=True)
class FilterPreset:
    exposure: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0
    temperature: float = 0.0
    tint: float = 0.0
    gamma: float = 1.0
    fade: float = 0.0
    grain: float = 0.0
    vignette: float = 0.0
    bloom: float = 0.0
    sharpen: float = 0.0
    chroma: float = 0.0
    special: str = "none"


FILTER_PRESETS: dict[str, FilterPreset] = {
    "none": FilterPreset(),
    "auto": FilterPreset(),
    # Clean / social-video families
    "clean_pop": FilterPreset(exposure=0.05, contrast=1.08, saturation=1.15, sharpen=0.18),
    "vivid": FilterPreset(exposure=0.02, contrast=1.14, saturation=1.32, sharpen=0.22),
    "soft_portrait": FilterPreset(exposure=0.08, contrast=0.90, saturation=0.92, temperature=0.08, fade=0.06, bloom=0.08),
    "pastel": FilterPreset(exposure=0.10, contrast=0.82, saturation=0.78, temperature=0.04, fade=0.16, special="pastel"),
    "bright_air": FilterPreset(exposure=0.12, contrast=0.92, saturation=1.08, temperature=-0.03, fade=0.04),
    "food_warm": FilterPreset(exposure=0.05, contrast=1.08, saturation=1.22, temperature=0.14, sharpen=0.15),
    "landscape_crisp": FilterPreset(exposure=0.01, contrast=1.18, saturation=1.20, temperature=-0.03, sharpen=0.28),
    # Cinema / photographic
    "cinematic_teal_orange": FilterPreset(contrast=1.22, saturation=0.95, temperature=0.03, fade=0.03, vignette=0.28, bloom=0.08, special="teal_orange"),
    "cinematic_night": FilterPreset(exposure=-0.08, contrast=1.25, saturation=0.72, temperature=-0.16, vignette=0.42, bloom=0.12, special="night"),
    "cinematic_bleach": FilterPreset(exposure=0.02, contrast=1.35, saturation=0.38, grain=0.12, vignette=0.18, special="bleach"),
    "cinematic_green": FilterPreset(exposure=-0.03, contrast=1.18, saturation=0.78, tint=-0.14, fade=0.04, vignette=0.30, special="green"),
    "anamorphic_dream": FilterPreset(contrast=1.08, saturation=0.92, temperature=0.05, bloom=0.28, vignette=0.25, chroma=0.12, special="anamorphic"),
    "silver_screen": FilterPreset(contrast=1.18, saturation=0.0, grain=0.15, vignette=0.30, special="silver"),
    # Vintage / analog
    "vintage_70s": FilterPreset(exposure=0.04, contrast=0.92, saturation=0.88, temperature=0.18, fade=0.14, grain=0.14, vignette=0.25, special="vintage"),
    "vintage_90s": FilterPreset(exposure=0.02, contrast=1.02, saturation=1.05, temperature=0.06, fade=0.08, grain=0.18, chroma=0.06, special="vhs"),
    "polaroid": FilterPreset(exposure=0.08, contrast=0.92, saturation=0.82, temperature=0.10, fade=0.10, grain=0.08, special="polaroid"),
    "faded_film": FilterPreset(exposure=0.04, contrast=0.78, saturation=0.72, temperature=0.08, fade=0.24, grain=0.14, vignette=0.12),
    "sepia_archive": FilterPreset(exposure=0.02, contrast=1.02, saturation=0.55, temperature=0.22, fade=0.08, grain=0.16, vignette=0.22, special="sepia"),
    "cross_process": FilterPreset(contrast=1.18, saturation=1.18, tint=0.08, grain=0.08, vignette=0.16, special="cross"),
    "super8": FilterPreset(exposure=0.05, contrast=1.08, saturation=0.82, temperature=0.16, fade=0.07, grain=0.25, vignette=0.38, special="super8"),
    "vhs_tape": FilterPreset(contrast=1.08, saturation=0.90, grain=0.20, chroma=0.15, special="vhs"),
    # Monochrome
    "noir": FilterPreset(exposure=-0.03, contrast=1.40, saturation=0.0, grain=0.12, vignette=0.44, sharpen=0.15),
    "matte_bw": FilterPreset(exposure=0.03, contrast=0.88, saturation=0.0, fade=0.18, grain=0.12),
    "high_key_bw": FilterPreset(exposure=0.14, contrast=1.10, saturation=0.0, fade=0.03, sharpen=0.12),
    "cyanotype": FilterPreset(contrast=1.18, saturation=0.0, fade=0.04, grain=0.10, special="cyanotype"),
    # Techno / underground
    "underground_blue": FilterPreset(exposure=-0.05, contrast=1.26, saturation=0.86, temperature=-0.22, vignette=0.35, bloom=0.12, special="blue"),
    "acid_green": FilterPreset(exposure=-0.02, contrast=1.25, saturation=1.16, tint=-0.24, bloom=0.10, vignette=0.20, special="acid"),
    "cyber_magenta": FilterPreset(contrast=1.22, saturation=1.28, tint=0.22, bloom=0.18, chroma=0.10, vignette=0.22, special="magenta"),
    "vaporwave": FilterPreset(exposure=0.03, contrast=1.08, saturation=1.32, tint=0.18, bloom=0.20, chroma=0.08, special="vaporwave"),
    "infrared": FilterPreset(contrast=1.28, saturation=1.18, special="infrared", grain=0.08, vignette=0.22),
    "night_vision": FilterPreset(exposure=0.02, contrast=1.32, saturation=0.0, grain=0.22, vignette=0.42, bloom=0.10, special="night_vision"),
    "thermal": FilterPreset(contrast=1.18, saturation=1.25, special="thermal"),
    "industrial_rust": FilterPreset(exposure=-0.05, contrast=1.28, saturation=0.68, temperature=0.13, grain=0.16, vignette=0.32, special="rust"),
    "concrete": FilterPreset(exposure=-0.04, contrast=1.20, saturation=0.28, temperature=-0.04, grain=0.14, vignette=0.25),
    "digital_decay": FilterPreset(contrast=1.22, saturation=1.08, grain=0.18, chroma=0.22, sharpen=0.18, special="digital"),
    "pink_signal": FilterPreset(exposure=0.04, contrast=1.14, saturation=1.26, tint=0.28, bloom=0.10, special="pink"),
    "electric_cobalt": FilterPreset(exposure=-0.02, contrast=1.30, saturation=1.24, temperature=-0.28, bloom=0.14, special="cobalt"),
    # Specialty
    "dream_haze": FilterPreset(exposure=0.08, contrast=0.88, saturation=0.90, fade=0.10, bloom=0.34, vignette=0.14),
    "golden_hour": FilterPreset(exposure=0.08, contrast=1.02, saturation=1.10, temperature=0.24, bloom=0.08, special="gold"),
    "winter": FilterPreset(exposure=0.06, contrast=1.02, saturation=0.72, temperature=-0.20, fade=0.05, special="winter"),
    "emerald": FilterPreset(contrast=1.12, saturation=1.02, tint=-0.18, special="emerald"),
    "comic_ink": FilterPreset(contrast=1.35, saturation=1.18, sharpen=0.35, special="comic"),
    "posterize": FilterPreset(contrast=1.15, saturation=1.18, special="posterize"),
    "pixel_lut": FilterPreset(contrast=1.18, saturation=1.12, grain=0.06, special="pixel"),
}

FILTER_NAMES = list(FILTER_PRESETS)

AUTO_FILTER_POOL = [
    "cinematic_teal_orange", "cinematic_night", "vintage_90s", "vhs_tape",
    "underground_blue", "acid_green", "cyber_magenta", "industrial_rust",
    "digital_decay", "pink_signal", "electric_cobalt", "noir", "dream_haze",
]


def _saturation(img: np.ndarray, amount: float) -> np.ndarray:
    luma = img[..., 0] * 0.114 + img[..., 1] * 0.587 + img[..., 2] * 0.299
    return luma[..., None] + (img - luma[..., None]) * amount


def _temperature_tint(img: np.ndarray, temperature: float, tint: float) -> np.ndarray:
    out = img.copy()
    out[..., 2] += temperature * 0.16
    out[..., 0] -= temperature * 0.14
    out[..., 1] -= tint * 0.08
    out[..., 2] += tint * 0.08
    out[..., 0] += tint * 0.08
    return out


def _special(img: np.ndarray, name: str) -> np.ndarray:
    if name == "none":
        return img
    b, g, r = cv2.split(np.clip(img, 0, 1).astype(np.float32))
    if name == "teal_orange":
        shadows = 1.0 - np.clip((r + g + b) / 3.0 * 2.0, 0, 1)
        highlights = 1.0 - shadows
        b += shadows * 0.10; g += shadows * 0.04
        r += highlights * 0.10; g += highlights * 0.025
    elif name == "night":
        b = b * 1.15 + 0.035; g *= 0.94; r *= 0.78
    elif name == "bleach":
        gray = (0.114*b + 0.587*g + 0.299*r)
        overlay = np.where(gray < .5, 2*gray*gray, 1-2*(1-gray)*(1-gray))
        b = .35*b + .65*overlay; g = .35*g + .65*overlay; r = .35*r + .65*overlay
    elif name == "green":
        g = g * 1.08 + 0.02; b *= .94; r *= .90
    elif name == "silver":
        gray = 0.114*b + 0.587*g + 0.299*r
        b = g = r = np.power(gray, .92)
    elif name in {"vintage", "polaroid", "sepia", "super8"}:
        rr = 0.393*r + 0.769*g + 0.189*b
        gg = 0.349*r + 0.686*g + 0.168*b
        bb = 0.272*r + 0.534*g + 0.131*b
        mix = {"vintage": .22, "polaroid": .16, "sepia": .48, "super8": .24}[name]
        b = b*(1-mix)+bb*mix; g = g*(1-mix)+gg*mix; r = r*(1-mix)+rr*mix
    elif name == "cross":
        r = np.sqrt(np.clip(r,0,1)); g = np.power(np.clip(g,0,1),1.08); b = np.power(np.clip(b,0,1),1.18)
    elif name == "pastel":
        b = .82*b+.18; g=.82*g+.18; r=.82*r+.18
    elif name == "blue":
        b = b*1.18+.035; g*=.98; r*=.76
    elif name == "acid":
        g = g*1.28+.035; r*=.86; b*=.82
    elif name in {"magenta", "pink", "vaporwave"}:
        r = r*1.16+.035; b=b*1.12+.025; g*=.86
    elif name == "infrared":
        gray = 0.114*b + 0.587*g + 0.299*r
        r = np.clip(gray*1.45,0,1); g=np.clip(1.15-gray*.55,0,1); b=np.clip((1-gray)*.75,0,1)
    elif name == "night_vision":
        gray = 0.114*b + 0.587*g + 0.299*r
        b = gray*.08; g=np.clip(gray*1.35,0,1); r=gray*.10
    elif name == "thermal":
        gray = np.clip((0.114*b + 0.587*g + 0.299*r)*255,0,255).astype(np.uint8)
        return cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO).astype(np.float32)/255.0
    elif name == "rust":
        r=r*1.10+.025; g*=.78; b*=.62
    elif name == "digital":
        r=np.power(np.clip(r,0,1),.92); b=np.power(np.clip(b,0,1),1.08)
    elif name == "cobalt":
        b=b*1.30+.035; g*=.90; r*=.70
    elif name == "gold":
        r=r*1.12+.025; g=g*1.03+.01; b*=.78
    elif name == "winter":
        b=b*1.12+.025; g*=1.02; r*=.88
    elif name == "emerald":
        g=g*1.16+.02; b*=.94; r*=.82
    elif name == "cyanotype":
        gray=0.114*b+0.587*g+0.299*r; b=gray*1.05+.08; g=gray*.78+.03; r=gray*.35
    elif name == "anamorphic":
        b=b*1.08; r=r*1.05
    elif name == "vhs":
        b=np.roll(b,2,axis=1); r=np.roll(r,-2,axis=1)
    elif name == "posterize":
        levels=6; b=np.floor(b*levels)/levels; g=np.floor(g*levels)/levels; r=np.floor(r*levels)/levels
    elif name == "pixel":
        levels=8; b=np.round(b*levels)/levels; g=np.round(g*levels)/levels; r=np.round(r*levels)/levels
    elif name == "comic":
        # Edge darkening is added after merge.
        pass
    return cv2.merge([b,g,r])


def _bloom(frame: np.ndarray, amount: float) -> np.ndarray:
    if amount <= 0:
        return frame
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mask = np.clip((gray.astype(np.float32)-150.0)/105.0,0,1)[...,None]
    blur = cv2.GaussianBlur(frame,(0,0),max(2.0, min(frame.shape[:2])/180.0))
    return np.clip(frame.astype(np.float32)+blur.astype(np.float32)*mask*amount*.65,0,255).astype(np.uint8)


def _vignette(frame: np.ndarray, amount: float) -> np.ndarray:
    if amount <= 0:
        return frame
    h,w=frame.shape[:2]
    y,x=np.mgrid[-1:1:complex(0,h),-1:1:complex(0,w)]
    radius=np.sqrt(x*x+y*y)
    mask=np.clip(1.0-amount*np.power(np.clip(radius/.95,0,1),1.7),0,1)
    return np.clip(frame.astype(np.float32)*mask[...,None],0,255).astype(np.uint8)


def _chromatic(frame: np.ndarray, amount: float) -> np.ndarray:
    if amount <= 0:
        return frame
    shift=max(1,int(round(frame.shape[1]*0.006*amount)))
    b,g,r=cv2.split(frame)
    b=np.roll(b,shift,axis=1); r=np.roll(r,-shift,axis=1)
    return cv2.merge([b,g,r])


def apply_filter(
    frame: np.ndarray,
    name: str,
    intensity: float = 1.0,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Apply a named filter and blend it with the original by intensity."""
    if name not in FILTER_PRESETS or name in {"none", "auto"} or intensity <= 0:
        return frame
    p=FILTER_PRESETS[name]
    original=frame
    img=frame.astype(np.float32)/255.0
    img=img*np.power(2.0,p.exposure)
    img=(img-.5)*p.contrast+.5
    img=_saturation(img,p.saturation)
    img=_temperature_tint(img,p.temperature,p.tint)
    img=np.power(np.clip(img,0,1),1.0/max(.05,p.gamma))
    if p.fade>0:
        img=img*(1-p.fade)+(.5+np.mean(img,axis=2,keepdims=True)*.08)*p.fade
    img=_special(img,p.special)
    out=np.clip(img*255,0,255).astype(np.uint8)

    if p.special == "comic":
        gray=cv2.cvtColor(out,cv2.COLOR_BGR2GRAY)
        edge=cv2.Canny(gray,60,150)
        out[edge>0]=(out[edge>0].astype(np.float32)*.22).astype(np.uint8)
    out=_bloom(out,p.bloom)
    if p.sharpen>0:
        blur=cv2.GaussianBlur(out,(0,0),1.2)
        out=cv2.addWeighted(out,1+p.sharpen,blur,-p.sharpen,0)
    out=_chromatic(out,p.chroma)
    out=_vignette(out,p.vignette)
    if p.grain>0:
        rng=rng or np.random.default_rng(0)
        noise=rng.normal(0,255*p.grain*.12,out.shape[:2]).astype(np.float32)
        out=np.clip(out.astype(np.float32)+noise[...,None],0,255).astype(np.uint8)
    alpha=float(np.clip(intensity,0,1))
    return cv2.addWeighted(original,1-alpha,out,alpha,0)
