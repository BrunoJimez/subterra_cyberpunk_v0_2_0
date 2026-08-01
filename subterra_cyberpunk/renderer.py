from __future__ import annotations

import json
import math
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from .character import CharacterAsset, CharacterSpec, alpha_composite
from .config import RenderConfig
from .filters import apply_filter
from .i2v import I2VClipPool, ShotPackageWriter
from .media import MediaPool
from .worlds import CyberWorldRenderer


class FeatureStream:
    def __init__(self, npz_path: str | Path):
        d=np.load(npz_path);self.times=d["times"]
        self.channels={k:d[k] for k in d.files if k not in {"times","beat_times","section_bounds"}}
        self.beat_times=d["beat_times"];self.section_bounds=d["section_bounds"]

    def value(self,name:str,t:float)->float:
        arr=self.channels.get(name)
        return 0.0 if arr is None or len(arr)==0 else float(np.interp(t,self.times,arr))

    def beat_pulse(self,t:float,decay:float=9.0)->float:
        if len(self.beat_times)==0:return 0.0
        i=np.searchsorted(self.beat_times,t,side="right")-1
        if i<0:return 0.0
        return float(math.exp(-max(0.0,t-float(self.beat_times[i]))*decay))


class CyberpunkRenderer:
    def __init__(self,config:RenderConfig,features_path:str|Path,story_path:str|Path,
                 character_specs:list[CharacterSpec]|None=None,media_paths:list[str]|None=None):
        self.cfg=config;self.features=FeatureStream(features_path)
        self.story=json.loads(Path(story_path).read_text(encoding="utf-8"));self.rng=np.random.default_rng(config.seed)
        self.iw=max(320,int(round(config.width*config.render_scale/2)*2));self.ih=max(180,int(round(config.height*config.render_scale/2)*2))
        self.world=CyberWorldRenderer(self.iw,self.ih,config.seed);self.media=MediaPool(media_paths or [],self.iw,self.ih)
        self.characters=[]
        for spec in character_specs or []:
            try:self.characters.append(CharacterAsset(spec,config.subject_extraction))
            except Exception as exc:print(f"AVISO: personagem ignorado ({spec.path}): {exc}")
        self.shots=list(self.story.get("shots",[]))
        if not self.shots:self.shots=self._legacy_shots()
        self.shot_starts=np.asarray([float(s.get("start",0)) for s in self.shots],np.float64)
        self.last_frame=np.zeros((self.ih,self.iw,3),np.uint8);self.feedback=np.zeros_like(self.last_frame)
        self.camera_state=np.asarray([1.0,0.0,0.0,0.0],np.float64)
        self.i2v=I2VClipPool(config.i2v_clips_dir if config.i2v_mode in {"clips","package_and_clips"} else None,self.iw,self.ih)
        self.packages=ShotPackageWriter(config.i2v_package_dir if config.i2v_mode in {"package","package_and_clips"} else None,self.story,self.iw,self.ih,config.fps)

    def _legacy_shots(self)->list[dict]:
        shots=[];sid=0
        for scene in self.story.get("scenes",[]):
            start=float(scene.get("start",0));end=float(scene.get("end",start+1));step=max(.5,float(scene.get("shot_seconds",2.0)))
            count=max(1,int(math.ceil((end-start)/step)))
            for i in range(count):
                s=start+(end-start)*i/count;e=start+(end-start)*(i+1)/count
                shots.append({**scene,"shot":sid,"start":s,"end":e,"duration":e-s,"blocking":{},"prompt":"legacy procedural cyberpunk shot"});sid+=1
        return shots

    def _shot(self,t:float)->dict:
        idx=int(np.searchsorted(self.shot_starts,t,side="right")-1);idx=max(0,min(len(self.shots)-1,idx))
        return self.shots[idx]

    @staticmethod
    def _ease(p:float)->float:
        p=float(np.clip(p,0,1));return p*p*(3-2*p)

    @staticmethod
    def _posterize(frame:np.ndarray,levels:int)->np.ndarray:
        levels=max(2,levels);return (np.round(frame.astype(np.float32)/255*(levels-1))/(levels-1)*255).clip(0,255).astype(np.uint8)

    def _stylize_character(self,img:np.ndarray,world:str,intensity:float)->np.ndarray:
        original=img
        if world=="future_noir_cel":
            smooth=cv2.bilateralFilter(img,7,55,55);stylized=self._posterize(smooth,7);gray=cv2.cvtColor(stylized,cv2.COLOR_BGR2GRAY);edge=cv2.Canny(gray,55,130);stylized[edge>0]=(9,5,18)
            lum=gray.astype(np.float32)/255;stylized[:,:,0]=np.clip(stylized[:,:,0].astype(np.float32)*(1.05+.12*(1-lum)),0,255);stylized[:,:,2]=np.clip(stylized[:,:,2].astype(np.float32)*(.98+.10*lum),0,255)
        else:
            stylized=self._posterize(img,6);hsv=cv2.cvtColor(stylized,cv2.COLOR_BGR2HSV).astype(np.float32);hsv[:,:,1]=np.clip(hsv[:,:,1]*1.18+8,0,255);hsv[:,:,2]=np.clip((hsv[:,:,2]-80)*1.25+80,0,255);stylized=cv2.cvtColor(hsv.astype(np.uint8),cv2.COLOR_HSV2BGR)
            gray=cv2.cvtColor(stylized,cv2.COLOR_BGR2GRAY);edge=cv2.Canny(gray,45,115);stylized[edge>0]=(3,1,8);stylized[:,:,2]=np.clip(stylized[:,:,2].astype(np.float32)*1.08+8,0,255);stylized[:,:,0]=np.clip(stylized[:,:,0].astype(np.float32)*1.02+4,0,255)
            yy,xx=np.indices(stylized.shape[:2]);dots=((xx%5==0)&(yy%5==0));stylized[dots]=(stylized[dots].astype(np.float32)*.80).astype(np.uint8)
        blend=float(np.clip(intensity,0,1));blend*=.76 if self.cfg.preserve_identity else 1.0
        return cv2.addWeighted(original,1-blend,stylized,blend,0)

    def _procedural_character(self,frame:np.ndarray,x:int,floor_y:int,height:int,world:str,t:float,impact:float,action:str,index:int)->None:
        bob=int(math.sin(t*2.2+index)*height*.018)
        if action in {"dance","sway","sing","jump"}:bob+=int(math.sin(t*5+index)*height*.025*impact)
        y=floor_y+bob;head_r=max(5,int(height*.08));torso_h=int(height*.48);torso_w=int(height*.18)
        skin=(75,65,180) if world=="neon_graphic_grit" else (135,110,185);coat=(8,4,18) if world=="neon_graphic_grit" else (18,12,30);accent=(180,30,240) if world=="neon_graphic_grit" else (210,55,220)
        hx=x+int(math.sin(t*.8+index)*height*.015);hy=y-torso_h-int(height*.20);cv2.circle(frame,(hx,hy),head_r,skin,-1,cv2.LINE_AA)
        pts=[(hx-head_r,hy),(hx-int(head_r*.55),hy-head_r),(hx+head_r,hy-int(head_r*.6)),(hx+int(head_r*.65),hy+int(head_r*.45))];cv2.fillPoly(frame,[np.asarray(pts,np.int32)],coat,cv2.LINE_AA)
        body=[(x-torso_w,y-torso_h),(x+torso_w,y-torso_h),(x+int(torso_w*.72),y),(x-int(torso_w*.72),y)];cv2.fillPoly(frame,[np.asarray(body,np.int32)],coat,cv2.LINE_AA);cv2.polylines(frame,[np.asarray(body,np.int32)],True,accent,max(1,int(height*.006)),cv2.LINE_AA)
        arm_y=y-int(torso_h*.68);swing=math.sin(t*3+index)*height*.08 if action in {"walk","run","dance","fight_pose"} else 0
        cv2.line(frame,(x-torso_w,arm_y),(x-int(torso_w*1.4),int(arm_y+swing)),coat,max(2,int(height*.035)),cv2.LINE_AA);cv2.line(frame,(x+torso_w,arm_y),(x+int(torso_w*1.35),int(arm_y-swing)),coat,max(2,int(height*.035)),cv2.LINE_AA)

    def _camera_target(self,mode:str,t:float,local_t:float,energy:float,impact:float,shot_id:int)->np.ndarray:
        zoom=1.0;angle=0.0;tx=0.0;ty=0.0
        if mode=="closeup":zoom=1.12+impact*.04
        elif mode=="tracking":tx=math.sin(t*.38+shot_id)*self.iw*.045;zoom=1.04
        elif mode=="low_angle":ty=-self.ih*.038;angle=math.sin(t*.25)*1.2
        elif mode=="over_shoulder":tx=self.iw*(.04 if shot_id%2 else -.04);zoom=1.09
        elif mode=="crash_zoom":zoom=1.0+min(1.0,local_t/.35)*(.20+.09*impact)
        elif mode=="silhouette":zoom=1.02
        elif mode=="dolly":zoom=1.02+.09*self._ease(min(1.0,local_t/1.8));tx=math.sin(t*.22)*self.iw*.018
        elif mode=="handheld_graphic":zoom=1.045;tx=math.sin(t*8.1+shot_id)*self.iw*.008*energy;ty=math.cos(t*7.2)*self.ih*.007*energy;angle=math.sin(t*6.3)*.7*impact
        else:zoom=1.02+energy*.018
        return np.asarray([zoom,angle,tx,ty],np.float64)

    def _camera(self,frame:np.ndarray,mode:str,t:float,local_t:float,energy:float,impact:float,shot_id:int)->np.ndarray:
        target=self._camera_target(mode,t,local_t,energy,impact,shot_id)
        smooth=float(np.clip(self.cfg.camera_smoothing,0,1));alpha=max(.03,1.0-smooth**(30/max(1,self.cfg.fps)))
        self.camera_state=self.camera_state*(1-alpha)+target*alpha
        zoom,angle,tx,ty=self.camera_state;center=(self.iw*.5+tx,self.ih*.5+ty);m=cv2.getRotationMatrix2D(center,float(angle),float(zoom))
        return cv2.warpAffine(frame,m,(self.iw,self.ih),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REFLECT_101)

    def _caption_text(self,t:float)->str:
        for c in self.story.get("captions",[]):
            if float(c.get("start",0))<=t<=float(c.get("end",0)):return str(c.get("text",""))
        phrases=["SIGNAL / BODY","MEMORY IS A CITY","NO HUMAN STATIC","NIGHT PROTOCOL","WE MOVE IN CODE","AFTER THE DROP"]
        return phrases[int(t/5.5+self.cfg.seed)%len(phrases)]

    def _typography(self,frame:np.ndarray,shot:dict,t:float)->np.ndarray:
        if not self.cfg.typography or shot.get("typography_mode")=="none":return frame
        text=self._caption_text(t).upper();mode=shot.get("typography_mode","subtitle");out=frame.copy();h,w=out.shape[:2]
        if mode=="subtitle":
            scale=max(.48,h/1200);thick=max(1,int(scale*2));(tw,th),_=cv2.getTextSize(text,cv2.FONT_HERSHEY_SIMPLEX,scale,thick);cv2.rectangle(out,(int(w*.5-tw*.5-12),int(h*.88-th-12)),(int(w*.5+tw*.5+12),int(h*.88+10)),(5,3,14),-1);cv2.putText(out,text,(int(w*.5-tw*.5),int(h*.88)),cv2.FONT_HERSHEY_SIMPLEX,scale,(245,235,250),thick,cv2.LINE_AA)
        elif mode=="title_card":cv2.putText(out,text[:20],(int(w*.06),int(h*.22)),cv2.FONT_HERSHEY_DUPLEX,max(.75,h/650),(245,225,250),max(2,int(h/330)),cv2.LINE_AA)
        elif mode=="fragment":
            for i,word in enumerate(text.split()[:5]):
                scale=max(.45,h/1000)*(1+.18*((i+int(shot.get("shot",0)))%3));x=int(w*(.04+.18*i))%max(1,w-80);y=int(h*(.15+.16*(i%4)));cv2.putText(out,word,(x,y),cv2.FONT_HERSHEY_SIMPLEX,scale,(245,230,250),max(1,int(scale*2)),cv2.LINE_AA)
        else:cv2.putText(out,"> "+text,(int(w*.05),int(h*.10)),cv2.FONT_HERSHEY_PLAIN,max(.7,h/850),(160,240,225),1,cv2.LINE_AA)
        return out

    def _transition(self,frame:np.ndarray,shot:dict,local_t:float)->np.ndarray:
        dur=min(.42,max(.12,float(shot.get("duration",1))*.18));p=float(np.clip(local_t/max(.001,dur),0,1));kind=shot.get("transition","cut")
        if p>=1 or kind=="cut":return frame
        if kind=="flash":return cv2.addWeighted(frame,p,np.full_like(frame,245),1-p,0)
        if kind=="pixel":
            pix=max(1,int((1-p)*38+1));small=cv2.resize(frame,(max(1,self.iw//pix),max(1,self.ih//pix)));return cv2.resize(small,(self.iw,self.ih),interpolation=cv2.INTER_NEAREST)
        if kind=="luma":
            mask=(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)<p*255)[...,None];return np.where(mask,frame,self.last_frame).astype(np.uint8)
        if kind=="ink":
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY);thresh=np.percentile(gray,p*100);mask=(gray<=thresh)[...,None];return np.where(mask,frame,self.last_frame).astype(np.uint8)
        if kind=="hologram":
            out=cv2.addWeighted(frame,p,self.last_frame,1-p,0);step=max(2,int(8-6*p));out[::step]=(out[::step]*.45).astype(np.uint8);return out
        if kind=="motion_blur":return cv2.addWeighted(frame,.65,np.roll(frame,int((1-p)*self.iw*.08),axis=1),.35,0)
        if kind=="whip":
            shift=int((1-p)*self.iw*(.65 if int(shot.get("shot",0))%2 else -.65));a=np.roll(frame,shift,axis=1);b=np.roll(self.last_frame,shift-int(math.copysign(self.iw,shift or 1)),axis=1);return cv2.addWeighted(a,p,b,1-p,0)
        if kind=="silhouette_wipe":
            x=int(p*self.iw);mask=np.zeros((self.ih,self.iw,1),bool);mask[:,:x]=True;return np.where(mask,frame,self.last_frame).astype(np.uint8)
        if kind=="match_shape":
            radius=int(p*math.hypot(self.iw,self.ih));yy,xx=np.ogrid[:self.ih,:self.iw];mask=(((xx-self.iw//2)**2+(yy-self.ih//2)**2)<=radius**2)[...,None];return np.where(mask,frame,self.last_frame).astype(np.uint8)
        return frame

    def _foreground_fx(self,frame:np.ndarray,world:str,t:float,impact:float,flux:float)->np.ndarray:
        out=frame;rng=np.random.default_rng(self.cfg.seed+int(t*20));count=int((8+40*flux)*(self.iw/1280))
        for _ in range(count):
            x=int(rng.integers(0,self.iw));y=int(rng.integers(0,self.ih));r=max(1,int(rng.uniform(1,4)*(self.ih/720)));col=(220,70,235) if world=="neon_graphic_grit" else (210,95,230);cv2.circle(out,(x,y),r,col,-1,cv2.LINE_AA)
        if impact>.62 and world=="neon_graphic_grit":
            for _ in range(int(4+impact*8)):
                y=int(rng.integers(0,self.ih));hh=int(rng.integers(2,max(3,self.ih//40)));shift=int(rng.normal(0,self.iw*.025)*impact);out[y:y+hh]=np.roll(out[y:y+hh],shift,axis=1)
        return out

    def _character_height(self,camera:str,scale:float)->float:
        base=.70
        if camera=="closeup":base=1.03
        elif camera in {"wide","silhouette"}:base=.50
        elif camera=="low_angle":base=.82
        elif camera=="over_shoulder":base=.88
        return base*scale

    def frame(self,t:float)->np.ndarray:
        energy=self.features.value("energy",t);impact=max(self.features.value("impact",t),self.features.beat_pulse(t));bright=self.features.value("brightness",t);flux=self.features.value("flux",t);texture=self.features.value("texture",t)
        shot=self._shot(t);sid=int(shot.get("shot",0));start=float(shot.get("start",0));end=float(shot.get("end",start+1));local_t=max(0,t-start);duration=max(.001,end-start);phase=self._ease(local_t/duration)
        world=shot.get("world","neon_graphic_grit");location=shot.get("location","stage_riot")
        media=self.media.get(sid,t,speed=.55+energy,offset=sid*1.7,zoom=1.02+impact*.025,pan_x=math.sin(t*.25+sid),pan_y=math.cos(t*.22+sid))
        base,info=self.world.render(world,location,t*self.cfg.background_motion,energy,impact,bright,sid,media,self.cfg.crowd_density)
        visible=[int(i) for i in shot.get("visible_characters",[]) if 0<=int(i)<len(self.characters)]
        if self.characters and not visible:visible=[sid%len(self.characters)]
        blocking=shot.get("blocking",{})
        if self.characters:
            render_order=sorted(visible,key=lambda i:float(blocking.get(str(i),{}).get("depth",.5)),reverse=True)
            for char_idx in render_order:
                asset=self.characters[char_idx];block=blocking.get(str(char_idx),{});action=str(block.get("action",asset.spec.motion));x0=float(block.get("x_start",.5));x1=float(block.get("x_end",x0));x_norm=x0+(x1-x0)*phase
                scale=float(block.get("scale",1));depth=float(block.get("depth",asset.spec.depth));facing=int(block.get("facing",1));v_offset=float(block.get("vertical_offset",0));char_phase=float(block.get("phase",0))
                x=int(self.iw*x_norm);floor_y=info.floor_y+int(self.ih*v_offset)
                if action=="levitate":floor_y-=int(self.ih*(.08+.04*math.sin(t*1.5)))
                x+=int(math.sin(t*.23+char_idx*1.7)*self.iw*.025*self.cfg.parallax_strength*(1.15-depth))
                target_h=int(self.ih*self._character_height(str(shot.get("camera","medium")),scale)*self.cfg.character_scale*(asset.spec.scale/.72)*(1.05-.10*depth))
                img,alpha=asset.rendered(t,energy,impact,action,self.cfg.motion_strength*float(shot.get("character_intensity",.8)),target_h,self.cfg.character_outline,world,facing,self.cfg.secondary_motion,self.cfg.lip_sync,char_phase)
                img=self._stylize_character(img,world,.70)
                px=x-img.shape[1]//2;py=floor_y-img.shape[0]
                # Short identity-preserving echo trails for fast actions.
                trail=self.cfg.action_trails*(.35+.65*impact) if action in {"run","jump","dance","dramatic_turn","recoil","glitch"} else self.cfg.action_trails*.18
                if trail>.02:
                    direction=-1 if x1>=x0 else 1
                    for k in (2,1):
                        ghost_alpha=(alpha.astype(np.float32)*trail*(.14 if k==2 else .22)).astype(np.uint8);alpha_composite(base,img,ghost_alpha,px+direction*int(self.iw*.018*k),py)
                shadow=cv2.GaussianBlur(alpha,(0,0),max(3,self.ih/120));shadow=(shadow.astype(np.float32)*.38).astype(np.uint8);alpha_composite(base,np.zeros_like(img),shadow,px+int(self.iw*.012),py+int(self.ih*.012));alpha_composite(base,img,alpha,px,py)
        else:
            count=2 if shot.get("role") in {"drop","climax"} else 1
            xs=[.36,.66] if count==2 else [.5]
            for i,xn in enumerate(xs):self._procedural_character(base,int(self.iw*xn),info.floor_y,int(self.ih*.62),world,t,impact,["stare","walk","dance","sing","dramatic_turn"][int((sid+i)%5)],i)

        base=self._foreground_fx(base,world,t,impact,flux);base=self._typography(base,shot,t);base=self._camera(base,str(shot.get("camera","medium")),t,local_t,energy,impact,sid)
        self.packages.write(shot,base)
        clip=self.i2v.get(sid,local_t)
        if clip is not None:
            strength=float(np.clip(self.cfg.i2v_strength,0,1));base=cv2.addWeighted(base,1-strength,clip,strength,0)
        feedback_amount=.04+.09*texture;base=cv2.addWeighted(base,1-feedback_amount,self.feedback,feedback_amount,0);self.feedback=cv2.addWeighted(base,.74,self.feedback,.26,0)
        filter_name=self.cfg.filter_name if self.cfg.filter_name!="auto" else shot.get("filter","none");base=apply_filter(base,filter_name,self.cfg.filter_intensity,self.rng);base=self._transition(base,shot,local_t)
        strobe=min(max(self.cfg.strobe,0),.30 if self.cfg.safe_flashes else .45)
        if strobe>0 and impact>.92 and math.sin(t*34)>.90:base=cv2.addWeighted(base,1-strobe,np.full_like(base,250),strobe,0)
        self.last_frame=base.copy()
        if (self.iw,self.ih)!=(self.cfg.width,self.cfg.height):base=cv2.resize(base,(self.cfg.width,self.cfg.height),interpolation=cv2.INTER_CUBIC)
        return base

    def close(self)->None:
        self.media.close();self.i2v.close();self.packages.finalize()


def _available_encoders()->str:
    if not shutil.which("ffmpeg"):return ""
    try:return subprocess.check_output(["ffmpeg","-hide_banner","-encoders"],stderr=subprocess.DEVNULL,text=True,timeout=10)
    except Exception:return ""


def resolve_encoder(requested:str,output:Path)->str:
    if output.suffix.lower()==".avi":return "mpeg4"
    if requested!="auto":return requested
    enc=_available_encoders()
    if shutil.which("nvidia-smi") and "h264_nvenc" in enc:return "h264_nvenc"
    if platform.system()=="Windows" and "h264_qsv" in enc:return "h264_qsv"
    if platform.system()=="Windows" and "h264_amf" in enc:return "h264_amf"
    return "libx264"


def _ffmpeg_encoder_args(cfg:RenderConfig,output:Path)->list[str]:
    encoder=resolve_encoder(cfg.encoder,output)
    if output.suffix.lower()==".avi":return ["-c:v","mpeg4","-q:v","2","-c:a","libmp3lame","-b:a","320k"]
    if encoder in {"h264_nvenc","hevc_nvenc"}:return ["-c:v",encoder,"-preset","p5","-tune","hq","-rc","vbr","-cq",str(cfg.crf),"-b:v","0","-c:a","aac","-b:a","320k"]
    if encoder in {"h264_amf","hevc_amf"}:return ["-c:v",encoder,"-quality","quality","-qp_i",str(cfg.crf),"-qp_p",str(cfg.crf),"-c:a","aac","-b:a","320k"]
    if encoder in {"h264_qsv","hevc_qsv"}:return ["-c:v",encoder,"-preset","medium","-global_quality",str(cfg.crf),"-c:a","aac","-b:a","320k"]
    if encoder in {"libx265","libx264"}:return ["-c:v",encoder,"-preset",cfg.preset,"-crf",str(cfg.crf),"-c:a","aac","-b:a","320k"]
    return ["-c:v","libx264","-preset",cfg.preset,"-crf",str(cfg.crf),"-c:a","aac","-b:a","320k"]


def _audio_filter(mode:str)->list[str]:
    if mode in {"normalize","streaming"}:return ["-af","loudnorm=I=-14:TP=-1.0:LRA=11"]
    if mode=="cinema":return ["-af","highpass=f=20,lowpass=f=20000,loudnorm=I=-16:TP=-1.5:LRA=12"]
    if mode=="club":return ["-af","highpass=f=20,alimiter=limit=0.95,loudnorm=I=-10:TP=-0.8:LRA=8"]
    return []


def render_film(audio_path:str|Path,output_path:str|Path,features_path:str|Path,story_path:str|Path,config:RenderConfig,duration:float,
                character_specs:list[CharacterSpec]|None=None,media_paths:list[str]|None=None,progress:Callable[[int,int],None]|None=None)->None:
    if not shutil.which("ffmpeg"):raise RuntimeError("FFmpeg não foi encontrado no PATH.")
    output=Path(output_path);output.parent.mkdir(parents=True,exist_ok=True);total_frames=max(1,int(math.ceil(duration*config.fps)))
    cmd=["ffmpeg","-hide_banner","-loglevel","warning","-y","-f","rawvideo","-vcodec","rawvideo","-pix_fmt","bgr24","-s",f"{config.width}x{config.height}","-r",str(config.fps),"-i","-","-i",str(Path(audio_path)),"-map","0:v:0","-map","1:a:0",*_ffmpeg_encoder_args(config,output),*_audio_filter(config.audio_mode),"-pix_fmt","yuv420p","-movflags","+faststart","-t",f"{duration:.6f}","-shortest",str(output)]
    process=subprocess.Popen(cmd,stdin=subprocess.PIPE);renderer=CyberpunkRenderer(config,features_path,story_path,character_specs,media_paths)
    try:
        assert process.stdin is not None
        for frame_index in range(total_frames):
            t=min(duration,frame_index/config.fps);process.stdin.write(renderer.frame(t).tobytes())
            if progress and (frame_index%max(1,int(config.fps))==0 or frame_index==total_frames-1):progress(frame_index+1,total_frames)
        process.stdin.close();code=process.wait()
        if code!=0:raise RuntimeError(f"FFmpeg encerrou com código {code}.")
    except BrokenPipeError as exc:raise RuntimeError("FFmpeg interrompeu o render. Verifique codec, espaço em disco e formato de saída.") from exc
    finally:
        renderer.close()
        if process.poll() is None:process.terminate()
