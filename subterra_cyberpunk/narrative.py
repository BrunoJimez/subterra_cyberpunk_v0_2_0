from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .worlds import GRIT_SCENES, NOIR_SCENES


ROLE_SCENES = {
    "neon_graphic_grit": {
        "intro": ["red_apartment", "surveillance_alley", "cable_cathedral"],
        "breakdown": ["red_apartment", "cyber_lab", "hologram_plaza"],
        "buildup": ["surveillance_alley", "underground_train", "neon_megacity"],
        "drop": ["stage_riot", "hologram_plaza", "neon_megacity"],
        "climax": ["stage_riot", "neon_megacity", "cable_cathedral"],
        "outro": ["red_apartment", "surveillance_alley"],
        "development": GRIT_SCENES,
    },
    "future_noir_cel": {
        "intro": ["rooftop_sunset", "night_overlook", "intimate_room"],
        "breakdown": ["intimate_room", "night_overlook", "corporate_tower"],
        "buildup": ["skyline_transit", "violet_alley", "corporate_tower"],
        "drop": ["future_club", "chase_corridor", "skyline_transit"],
        "climax": ["future_club", "chase_corridor", "corporate_tower"],
        "outro": ["rooftop_sunset", "night_overlook"],
        "development": NOIR_SCENES,
    },
}

CAMERAS = [
    "closeup", "medium", "wide", "tracking", "low_angle", "over_shoulder",
    "silhouette", "crash_zoom", "dolly", "handheld_graphic",
]
TRANSITIONS = [
    "cut", "flash", "ink", "pixel", "luma", "hologram", "motion_blur",
    "whip", "silhouette_wipe", "match_shape",
]
LAYOUTS = ["single_left", "single_center", "single_right", "duo", "triangle", "foreground_background"]


def _world_for_section(rng: np.random.Generator, requested: str, role: str, energy: float) -> str:
    if requested in {"neon_graphic_grit", "future_noir_cel"}:
        return requested
    if requested == "hybrid_cyberpunk":
        return "neon_graphic_grit" if rng.random() < (.50 + .25 * energy) else "future_noir_cel"
    if role in {"drop", "climax"} or energy > .60:
        return "neon_graphic_grit"
    if role in {"intro", "breakdown", "outro"}:
        return "future_noir_cel"
    return str(rng.choice(["neon_graphic_grit", "future_noir_cel"], p=[.56, .44]))


def _action_for_role(rng: np.random.Generator, role: str, character_role: str, energy: float) -> str:
    if character_role in {"vocalist", "performer"}:
        pool = ["sing", "sway", "dramatic_turn", "reach", "nod"]
        weights = [.44, .20, .14, .12, .10]
        return str(rng.choice(pool, p=weights))
    if character_role == "hologram":
        return "hologram"
    if character_role == "crowd":
        return "dance" if energy > .42 else "sway"
    if character_role == "antagonist":
        if role in {"drop", "climax"}:
            return str(rng.choice(["fight_pose", "run", "recoil", "dramatic_turn"], p=[.35, .25, .18, .22]))
        return str(rng.choice(["stare", "look_left", "look_right", "walk"], p=[.40, .18, .18, .24]))
    if role in {"drop", "climax"}:
        return str(rng.choice(["run", "dance", "dramatic_turn", "jump", "glitch"], p=[.20, .23, .24, .16, .17]))
    if role == "breakdown":
        return str(rng.choice(["stare", "idle", "levitate", "look_left", "nod"], p=[.32, .28, .12, .15, .13]))
    if role == "buildup":
        return str(rng.choice(["walk", "dramatic_turn", "stare", "crouch", "reach"], p=[.34, .22, .18, .12, .14]))
    return str(rng.choice(["idle", "walk", "sway", "stare", "look_right", "nod"], p=[.23, .20, .19, .16, .12, .10]))


def _filter_for_world(rng: np.random.Generator, world: str) -> str:
    if world == "neon_graphic_grit":
        return str(rng.choice(["cyber_magenta", "pink_signal", "digital_decay", "industrial_rust", "comic_ink", "vhs_tape"]))
    return str(rng.choice(["cinematic_night", "electric_cobalt", "vaporwave", "dream_haze", "comic_ink", "cinematic_teal_orange"]))


def _base_screen_x(role: str, index: int) -> float:
    table = {
        "protagonist": .40,
        "vocalist": .50,
        "performer": .50,
        "support": .68,
        "antagonist": .76,
        "hologram": .72,
        "android": .64,
        "creature": .72,
        "crowd": .50,
    }
    x = table.get(role, .50)
    if index % 2 and role in {"support", "android", "creature"}:
        x = 1.0 - x
    return x


def _choose_visible(
    rng: np.random.Generator,
    characters: list[dict[str, Any]],
    previous_visible: list[int],
    role: str,
    continuity: float,
) -> list[int]:
    if not characters:
        return []
    max_visible = min(len(characters), 3 if role in {"drop", "climax", "development"} else 2)
    target_count = int(rng.integers(1, max_visible + 1))
    if role in {"drop", "climax"} and len(characters) >= 2:
        target_count = max(2, target_count)
    keep: list[int] = []
    for idx in previous_visible:
        if len(keep) >= target_count:
            break
        if rng.random() < continuity:
            keep.append(idx)
    protagonist = next((i for i, c in enumerate(characters) if c.get("role") in {"protagonist", "vocalist"}), None)
    if protagonist is not None and protagonist not in keep and role not in {"outro"} and rng.random() < .70:
        keep.append(protagonist)
    available = [i for i in range(len(characters)) if i not in keep]
    rng.shuffle(available)
    keep.extend(available[: max(0, target_count - len(keep))])
    return sorted(keep[:target_count])


def _layout_targets(layout: str, count: int) -> list[tuple[float, float, float]]:
    """Return x, scale and depth targets in normalized screen space."""
    if count <= 1:
        x = .50
        if layout == "single_left":
            x = .32
        elif layout == "single_right":
            x = .68
        return [(x, 1.0, .46)]
    if count == 2:
        if layout == "foreground_background":
            return [(.37, 1.08, .28), (.68, .83, .68)]
        return [(.32, .96, .44), (.68, .94, .52)]
    return [(.22, .86, .58), (.50, 1.0, .42), (.78, .84, .64)]


def _shot_prompt(world: str, location: str, camera: str, actions: list[str], role: str) -> str:
    style = (
        "original crimson-magenta graphic cyberpunk music-video art, deep black ink shadows, halftone, neon electricity"
        if world == "neon_graphic_grit"
        else "original future-noir cel animation, angular silhouettes, clean color blocks, violet-blue city lighting"
    )
    action_text = ", ".join(actions) if actions else "atmospheric character movement"
    return f"{style}; {location}; {camera} shot; {role}; characters performing {action_text}; preserve character identity and costume; cinematic motion"


def build_story(
    analysis_json: str | Path,
    seed: int,
    output_path: str | Path,
    world: str = "auto_director",
    filter_name: str = "auto",
    captions: list[dict[str, Any]] | None = None,
    edit_density: float = .68,
    characters: list[dict[str, Any]] | None = None,
    continuity_strength: float = .82,
) -> dict[str, Any]:
    data = json.loads(Path(analysis_json).read_text(encoding="utf-8"))
    rng = np.random.default_rng(seed)
    bpm = max(60.0, float(data.get("estimated_bpm") or 120.0))
    beat = 60.0 / bpm
    edit_density = float(np.clip(edit_density, 0, 1))
    continuity_strength = float(np.clip(continuity_strength, 0, 1))
    characters = characters or []

    states: dict[int, dict[str, Any]] = {}
    arcs: list[dict[str, Any]] = []
    for idx, char in enumerate(characters):
        x = _base_screen_x(str(char.get("role", "support")), idx)
        states[idx] = {"x": x, "facing": -1 if x > .5 else 1, "depth": .5, "visible": False}
        arcs.append({
            "character": idx,
            "name": char.get("name", f"character_{idx}"),
            "role": char.get("role", "support"),
            "home_screen_x": round(x, 3),
            "motif": str(rng.choice(["electricity", "rain", "ink", "hologram", "glass", "signal_noise"])),
            "dramatic_goal": str(rng.choice(["escape", "perform", "confront", "observe", "protect", "transform"])),
        })

    scenes: list[dict[str, Any]] = []
    shots: list[dict[str, Any]] = []
    previous_location = ""
    previous_visible: list[int] = []
    shot_id = 0

    for scene_index, section in enumerate(data["sections"]):
        role = section.get("role", "development")
        energy = float(section.get("energy", .4))
        scene_world = _world_for_section(rng, world, role, energy)
        pool = ROLE_SCENES[scene_world].get(role, ROLE_SCENES[scene_world]["development"])
        location = str(rng.choice(pool))
        for _ in range(4):
            if location != previous_location or len(pool) == 1:
                break
            location = str(rng.choice(pool))
        previous_location = location
        alt_pool = [s for s in ROLE_SCENES[scene_world]["development"] if s != location]
        alt_location = str(rng.choice(alt_pool)) if alt_pool else location

        if role in {"drop", "climax"}:
            division = float(rng.choice([.5, 1, 2], p=[.18, .58, .24]))
        elif role == "breakdown":
            division = float(rng.choice([4, 8, 12]))
        else:
            division = float(rng.choice([2, 4, 8], p=[.26, .49, .25]))
        base_shot_seconds = max(.32, beat * division * (1.42 - edit_density * .78))
        section_start = float(section["start"])
        section_end = float(section["end"])
        section_duration = max(.05, section_end - section_start)
        shot_count = max(1, int(np.ceil(section_duration / base_shot_seconds)))
        scene_shot_ids: list[int] = []

        for local_index in range(shot_count):
            start = section_start + local_index * section_duration / shot_count
            end = section_start + (local_index + 1) * section_duration / shot_count
            visible = _choose_visible(rng, characters, previous_visible, role, continuity_strength)
            previous_visible = visible
            layout = str(rng.choice(LAYOUTS))
            camera = str(rng.choice(CAMERAS))
            if role == "breakdown" and rng.random() < .55:
                camera = str(rng.choice(["closeup", "over_shoulder", "silhouette", "dolly"]))
            if role in {"drop", "climax"} and rng.random() < .55:
                camera = str(rng.choice(["tracking", "low_angle", "crash_zoom", "handheld_graphic"]))
            shot_location = alt_location if local_index % 4 == 3 and edit_density > .35 else location
            targets = _layout_targets(layout, max(1, len(visible)))
            blocking: dict[str, dict[str, Any]] = {}
            actions: list[str] = []

            for pos, char_idx in enumerate(visible):
                char = characters[char_idx]
                requested = str(char.get("motion", "auto"))
                action = requested if requested != "auto" else _action_for_role(rng, role, str(char.get("role", "support")), energy)
                actions.append(action)
                tx, scale, depth = targets[pos % len(targets)]
                state = states[char_idx]
                old_x = float(state["x"])
                if not state["visible"]:
                    entrance_side = -1 if tx < .5 else 1
                    x_start = -.16 if entrance_side < 0 else 1.16
                else:
                    x_start = old_x
                jitter = float(rng.normal(0, .035 * (1.0 - continuity_strength)))
                x_end = float(np.clip(old_x * continuity_strength + (tx + jitter) * (1.0 - continuity_strength), .12, .88))
                if action in {"walk", "run"}:
                    travel = (.24 if action == "walk" else .42) * (1 if rng.random() > .5 else -1)
                    x_end = float(np.clip(x_start + travel, .10, .90))
                facing = 1 if x_end < .5 else -1
                if len(visible) > 1:
                    other_target = targets[(pos + 1) % len(targets)][0]
                    facing = 1 if other_target > x_end else -1
                blocking[str(char_idx)] = {
                    "x_start": round(float(x_start), 4),
                    "x_end": round(float(x_end), 4),
                    "scale": round(float(scale), 4),
                    "depth": round(float(depth), 4),
                    "facing": int(facing),
                    "action": action,
                    "entrance": "slide" if not state["visible"] else "hold",
                    "exit": "hold",
                    "vertical_offset": round(float(rng.uniform(-.025, .018)), 4),
                    "phase": round(float(rng.random()), 4),
                }
                state.update({"x": x_end, "facing": facing, "depth": depth, "visible": True})

            for idx, state in states.items():
                if idx not in visible:
                    state["visible"] = False

            transition = str(rng.choice(TRANSITIONS))
            scene_filter = _filter_for_world(rng, scene_world) if filter_name == "auto" else filter_name
            shot = {
                "shot": shot_id,
                "scene": scene_index,
                "start": round(start, 5),
                "end": round(end, 5),
                "duration": round(end - start, 5),
                "role": role,
                "world": scene_world,
                "location": shot_location,
                "camera": camera,
                "transition": transition,
                "filter": scene_filter,
                "visible_characters": visible,
                "blocking": blocking,
                "layout": layout,
                "character_intensity": round(float(rng.uniform(.58, .98)), 3),
                "glitch_density": round(float(rng.uniform(.06, .78) * (.72 + energy * .48)), 3),
                "light_pulse": round(float(rng.uniform(.35, .95)), 3),
                "typography_mode": str(rng.choice(["none", "subtitle", "title_card", "terminal", "fragment"], p=[.22, .29, .15, .16, .18])),
                "prompt": _shot_prompt(scene_world, shot_location, camera, actions, role),
            }
            shots.append(shot)
            scene_shot_ids.append(shot_id)
            shot_id += 1

        scenes.append({
            "scene": scene_index,
            "start": section_start,
            "end": section_end,
            "role": role,
            "world": scene_world,
            "location": location,
            "alt_location": alt_location,
            "shot_ids": scene_shot_ids,
        })

    story = {
        "version": "0.2.0",
        "engine": "SUBTERRA-CYBERPUNK Character Film Engine",
        "seed": int(seed),
        "audio": data["source"],
        "duration_seconds": data["duration_seconds"],
        "bpm": data["estimated_bpm"],
        "key": data["estimated_key"],
        "mood": data["mood_tags"],
        "world_mode": world,
        "edit_density": edit_density,
        "continuity_strength": continuity_strength,
        "visual_language": [
            "original cyberpunk character cinema", "audio-driven acting", "layered 2.5D character rig",
            "shot-to-shot continuity", "neon graphic grit", "future-noir cel animation",
            "procedural city worlds", "music-video montage", "local offline rendering",
        ],
        "characters": characters,
        "character_arcs": arcs,
        "captions": captions or [],
        "scenes": scenes,
        "shots": shots,
    }
    Path(output_path).write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")
    return story
