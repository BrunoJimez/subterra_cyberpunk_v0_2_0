from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict
from pathlib import Path

from subterra_cyberpunk.audio_analysis import analyze_audio
from subterra_cyberpunk.character import CharacterAsset, CharacterSpec
from subterra_cyberpunk.config import I2V_MODES, RESOLUTION_PRESETS, RenderConfig, WORLD_CHOICES
from subterra_cyberpunk.filters import FILTER_NAMES
from subterra_cyberpunk.hardware import diagnose, save_report
from subterra_cyberpunk.lyrics import captions_to_json, load_captions
from subterra_cyberpunk.narrative import build_story
from subterra_cyberpunk.renderer import render_film, resolve_encoder
from subterra_cyberpunk.report import write_html_report


def positive_int(value: str) -> int:
    n=int(value)
    if n<=0:raise argparse.ArgumentTypeError("deve ser maior que zero")
    return n


def unit_float(value: str) -> float:
    n=float(value)
    if not 0<=n<=1:raise argparse.ArgumentTypeError("deve estar entre 0 e 1")
    return n


def resolve_resolution(args: argparse.Namespace) -> tuple[int,int]:
    if bool(args.width)!=bool(args.height):raise ValueError("Para resolução personalizada, informe --width e --height juntos.")
    width,height=(args.width,args.height) if args.width and args.height else RESOLUTION_PRESETS[args.resolution]
    if width<320 or height<180:raise ValueError("A resolução mínima é 320x180.")
    return width-width%2,height-height%2


def cmd_diagnose(args: argparse.Namespace) -> int:
    report=diagnose(args.path);save_report(report,args.output);print(json.dumps(asdict(report),ensure_ascii=False,indent=2));print(f"\nRelatório salvo em: {Path(args.output).resolve()}");return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    summary,json_path,npz_path=analyze_audio(args.audio,args.workdir);print(json.dumps(asdict(summary),ensure_ascii=False,indent=2));print(f"\nAnálise: {json_path.resolve()}\nFeatures: {npz_path.resolve()}");return 0


def cmd_prepare_character(args: argparse.Namespace) -> int:
    spec=CharacterSpec.parse(args.character);asset=CharacterAsset(spec,args.extraction);out,rig=asset.save_bundle(args.output)
    print(f"Personagem preparado: {out.resolve()}\nRig 2.5D: {rig.resolve()}\nRecorte: {asset.bgr.shape[1]}x{asset.bgr.shape[0]} · face detectada: {bool(asset.face)}")
    return 0


def cmd_i2v_status(args: argparse.Namespace) -> int:
    package=Path(args.package_dir);clips=Path(args.clips_dir);manifest=package/"manifest.json"
    if not manifest.exists():raise FileNotFoundError(f"Manifesto não encontrado: {manifest}")
    data=json.loads(manifest.read_text(encoding="utf-8"));expected=[int(i) for i in data.get("shots",[])];available=[]
    for sid in expected:
        if any((clips/f"shot_{sid:04d}{ext}").exists() for ext in [".mp4",".mkv",".mov",".avi",".webm"]):available.append(sid)
    missing=[i for i in expected if i not in available]
    print(json.dumps({"expected":len(expected),"available":len(available),"missing":len(missing),"missing_shots":missing},indent=2));return 0


def cmd_render(args: argparse.Namespace) -> int:
    audio=Path(args.audio)
    if not audio.exists():raise FileNotFoundError(f"Áudio não encontrado: {audio}")
    output=Path(args.output)
    if output.suffix.lower() not in {".mp4",".mkv",".avi"}:raise ValueError("A saída deve usar .mp4, .mkv ou .avi")
    workdir=Path(args.workdir or output.parent/f"{output.stem}_project");workdir.mkdir(parents=True,exist_ok=True)
    seed=args.seed if args.seed is not None else random.SystemRandom().randint(1,2_147_483_647);width,height=resolve_resolution(args)
    specs=[CharacterSpec.parse(raw) for raw in args.character]
    for spec in specs:
        if not Path(spec.path).exists():raise FileNotFoundError(f"Imagem de personagem não encontrada: {spec.path}")

    print("[1/7] Analisando áudio e estrutura narrativa...")
    summary,analysis_path,features_path=analyze_audio(audio,workdir);duration=min(summary.duration_seconds,args.preview_seconds) if args.preview_seconds else summary.duration_seconds
    print("[2/7] Carregando letra/legenda...")
    captions=load_captions(args.lyrics,duration) if args.lyrics else []
    if captions:(workdir/"captions.json").write_text(json.dumps(captions_to_json(captions),ensure_ascii=False,indent=2),encoding="utf-8");print(f"  {len(captions)} segmentos carregados.")
    else:print("  Sem letra; será usada tipografia procedural.")

    print("[3/7] Construindo continuidade, coreografia e arcos dos personagens...")
    character_data=[asdict(s) for s in specs];(workdir/"characters.json").write_text(json.dumps(character_data,ensure_ascii=False,indent=2),encoding="utf-8")
    story_path=workdir/"story.json";story=build_story(analysis_path,seed,story_path,args.world,args.filter,captions_to_json(captions),args.edit_density,character_data,args.continuity_strength)
    write_html_report(analysis_path,story_path,workdir/"report.html")

    package_dir=args.i2v_package_dir or (str(workdir/"i2v_packages") if args.i2v_mode in {"package","package_and_clips"} else "")
    cfg=RenderConfig(width=width,height=height,fps=args.fps,seed=seed,world=args.world,quality=args.quality,render_scale=args.render_scale,strobe=args.strobe,
        audio_mode=args.audio_mode,encoder=args.encoder,crf=args.crf,preset=args.ffmpeg_preset,filter_name=args.filter,filter_intensity=args.filter_intensity,
        edit_density=args.edit_density,typography=not args.no_typography,safe_flashes=not args.unsafe_flashes,motion_strength=args.motion_strength,
        character_scale=args.character_scale,crowd_density=args.crowd_density,parallax_strength=args.parallax_strength,subject_extraction=args.subject_extraction,
        preserve_identity=not args.no_preserve_identity,character_outline=args.character_outline,background_motion=args.background_motion,
        continuity_strength=args.continuity_strength,secondary_motion=args.secondary_motion,lip_sync=args.lip_sync,action_trails=args.action_trails,
        camera_smoothing=args.camera_smoothing,i2v_mode=args.i2v_mode,i2v_package_dir=package_dir,i2v_clips_dir=args.i2v_clips_dir or "",i2v_strength=args.i2v_strength)
    (workdir/"render_config.json").write_text(json.dumps(asdict(cfg),ensure_ascii=False,indent=2),encoding="utf-8")

    print("[4/7] Preparando rigs de personagens...")
    if specs:
        cache=workdir/"character_cache";cache.mkdir(exist_ok=True)
        for i,spec in enumerate(specs,1):
            print(f"  {i}. {spec.name} · {spec.role} · {spec.motion}")
            try:CharacterAsset(spec,args.subject_extraction).save_bundle(cache/f"{i:02d}_{Path(spec.path).stem}.png")
            except Exception as exc:print(f"  AVISO ao preparar {spec.name}: {exc}")
    else:print("  Nenhuma referência: serão usados personagens gráficos procedurais originais.")

    print(f"[5/7] Plano criado: {len(story.get('shots',[]))} planos · continuidade={args.continuity_strength:.2f}")
    if args.i2v_mode in {"package","package_and_clips"}:print(f"  Pacotes I2V serão exportados para: {Path(package_dir).resolve()}")
    if args.i2v_mode in {"clips","package_and_clips"}:print(f"  Clipes I2V serão lidos de: {Path(args.i2v_clips_dir).resolve()}")

    encoder=resolve_encoder(cfg.encoder,output);print(f"[6/7] Renderizando {width}x{height} @ {args.fps:g} fps | mundo={args.world} | seed={seed} | encoder={encoder}")
    last_pct=-1
    def progress(done:int,total:int)->None:
        nonlocal last_pct
        pct=int(done*100/total)
        if pct!=last_pct:print(f"  {pct:3d}% ({done}/{total} frames)",flush=True);last_pct=pct
    render_film(audio,output,features_path,story_path,cfg,duration,specs,args.media,progress)
    print("[7/7] Finalizado.");print(f"Vídeo: {output.resolve()}\nProjeto: {workdir.resolve()}\nSeed: {seed}");return 0


def make_parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(description="SUBTERRA-CYBERPUNK 0.2 — música para filme animado com continuidade, rigs 2.5D e ponte I2V local.")
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("diagnose",help="Analisa hardware, FFmpeg e espaço em disco.");p.add_argument("--path",default=".");p.add_argument("--output",default="hardware_report.json");p.set_defaults(func=cmd_diagnose)
    p=sub.add_parser("analyze",help="Analisa profundamente um arquivo de áudio.");p.add_argument("audio");p.add_argument("--workdir",default="analysis_output");p.set_defaults(func=cmd_analyze)
    p=sub.add_parser("prepare-character",help="Recorta uma imagem e salva PNG transparente + rig JSON.");p.add_argument("character",help="PATH ou PATH::PAPEL::MOVIMENTO::NOME");p.add_argument("output",help="PNG de saída");p.add_argument("--extraction",choices=["auto","none"],default="auto");p.set_defaults(func=cmd_prepare_character)
    p=sub.add_parser("i2v-status",help="Compara pacotes I2V esperados com clipes gerados localmente.");p.add_argument("package_dir");p.add_argument("clips_dir");p.set_defaults(func=cmd_i2v_status)
    p=sub.add_parser("render",help="Cria o filme cyberpunk completo.")
    p.add_argument("audio");p.add_argument("output");p.add_argument("--character",action="append",default=[],help="PATH::PAPEL::MOVIMENTO::NOME. Pode ser repetido.");p.add_argument("--media",action="append",default=[]);p.add_argument("--lyrics")
    p.add_argument("--resolution",choices=sorted(RESOLUTION_PRESETS),default="1080p");p.add_argument("--width",type=positive_int);p.add_argument("--height",type=positive_int);p.add_argument("--fps",type=float,default=30.0);p.add_argument("--seed",type=int)
    p.add_argument("--world",choices=WORLD_CHOICES,default="auto_director");p.add_argument("--filter",choices=FILTER_NAMES,default="auto");p.add_argument("--filter-intensity",type=unit_float,default=.72);p.add_argument("--edit-density",type=unit_float,default=.68)
    p.add_argument("--motion-strength",type=unit_float,default=.72);p.add_argument("--secondary-motion",type=unit_float,default=.68);p.add_argument("--lip-sync",type=unit_float,default=.65);p.add_argument("--action-trails",type=unit_float,default=.32);p.add_argument("--continuity-strength",type=unit_float,default=.82);p.add_argument("--camera-smoothing",type=unit_float,default=.76)
    p.add_argument("--character-scale",type=float,default=.72);p.add_argument("--character-outline",type=unit_float,default=.55);p.add_argument("--crowd-density",type=unit_float,default=.55);p.add_argument("--parallax-strength",type=unit_float,default=.55);p.add_argument("--background-motion",type=unit_float,default=.65)
    p.add_argument("--subject-extraction",choices=["auto","none"],default="auto");p.add_argument("--no-preserve-identity",action="store_true");p.add_argument("--quality",choices=["draft","high"],default="high");p.add_argument("--render-scale",type=float,default=.75);p.add_argument("--strobe",type=unit_float,default=.12);p.add_argument("--unsafe-flashes",action="store_true");p.add_argument("--no-typography",action="store_true")
    p.add_argument("--i2v-mode",choices=I2V_MODES,default="off");p.add_argument("--i2v-package-dir");p.add_argument("--i2v-clips-dir");p.add_argument("--i2v-strength",type=unit_float,default=.82)
    p.add_argument("--audio-mode",choices=["preserve","normalize","streaming","cinema","club"],default="preserve");p.add_argument("--encoder",default="auto",choices=["auto","libx264","libx265","h264_nvenc","hevc_nvenc","h264_amf","hevc_amf","h264_qsv","hevc_qsv"]);p.add_argument("--crf",type=int,default=18);p.add_argument("--ffmpeg-preset",default="medium");p.add_argument("--preview-seconds",type=float);p.add_argument("--workdir");p.set_defaults(func=cmd_render)
    return parser


def main() -> int:
    parser=make_parser();args=parser.parse_args()
    try:return int(args.func(args))
    except KeyboardInterrupt:print("\nCancelado pelo usuário.",file=sys.stderr);return 130
    except Exception as exc:print(f"ERRO: {exc}",file=sys.stderr);return 1


if __name__=="__main__":raise SystemExit(main())
