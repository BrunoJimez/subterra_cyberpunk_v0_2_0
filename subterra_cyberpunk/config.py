from __future__ import annotations

from dataclasses import dataclass


RESOLUTION_PRESETS: dict[str, tuple[int, int]] = {
    "draft": (640, 360),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "2k": (2560, 1440),
    "4k": (3840, 2160),
    "reel": (1080, 1920),
    "tiktok": (1080, 1920),
    "story": (1080, 1920),
    "square": (1080, 1080),
    "portrait_4_5": (1080, 1350),
    "youtube_shorts": (1080, 1920),
    "cinema_2k": (2048, 1080),
    "cinema_4k": (4096, 2160),
    "ultrawide": (2560, 1080),
}

WORLD_CHOICES = [
    "auto_director",
    "neon_graphic_grit",
    "future_noir_cel",
    "hybrid_cyberpunk",
]

CHARACTER_ROLES = [
    "protagonist", "support", "antagonist", "vocalist", "performer",
    "hologram", "crowd", "android", "creature",
]

MOTION_CHOICES = [
    "auto", "idle", "stare", "sway", "dance", "sing", "walk", "run",
    "dramatic_turn", "look_left", "look_right", "nod", "reach", "recoil",
    "crouch", "jump", "fight_pose", "levitate", "glitch", "hologram",
]

I2V_MODES = ["off", "package", "clips", "package_and_clips"]


@dataclass(frozen=True)
class RenderConfig:
    width: int
    height: int
    fps: float = 30.0
    seed: int = 0
    world: str = "auto_director"
    quality: str = "high"
    render_scale: float = 0.75
    strobe: float = 0.12
    audio_mode: str = "preserve"
    encoder: str = "auto"
    crf: int = 18
    preset: str = "medium"
    filter_name: str = "auto"
    filter_intensity: float = 0.72
    edit_density: float = 0.68
    typography: bool = True
    safe_flashes: bool = True
    motion_strength: float = 0.72
    character_scale: float = 0.72
    crowd_density: float = 0.55
    parallax_strength: float = 0.55
    subject_extraction: str = "auto"
    preserve_identity: bool = True
    character_outline: float = 0.55
    background_motion: float = 0.65
    continuity_strength: float = 0.82
    secondary_motion: float = 0.68
    lip_sync: float = 0.65
    action_trails: float = 0.32
    camera_smoothing: float = 0.76
    i2v_mode: str = "off"
    i2v_package_dir: str = ""
    i2v_clips_dir: str = ""
    i2v_strength: float = 0.82
