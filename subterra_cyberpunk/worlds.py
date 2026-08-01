from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np


GRIT_SCENES = [
    "stage_riot", "neon_megacity", "hologram_plaza", "red_apartment",
    "surveillance_alley", "cyber_lab", "cable_cathedral", "underground_train",
]

NOIR_SCENES = [
    "rooftop_sunset", "future_club", "violet_alley", "skyline_transit",
    "intimate_room", "chase_corridor", "corporate_tower", "night_overlook",
]

ALL_SCENES = GRIT_SCENES + NOIR_SCENES


@dataclass(frozen=True)
class WorldFrameInfo:
    horizon: int
    floor_y: int
    light_center: tuple[int, int]


def _gradient(h: int, w: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> np.ndarray:
    a = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    t = np.asarray(top, np.float32)[None, None, :]
    b = np.asarray(bottom, np.float32)[None, None, :]
    return np.tile(np.clip(t * (1-a) + b*a, 0, 255).astype(np.uint8), (1, w, 1))


def _glow(frame: np.ndarray, mask: np.ndarray, color: tuple[int, int, int], strength: float) -> np.ndarray:
    if strength <= 0:
        return frame
    blur = cv2.GaussianBlur(mask, (0, 0), max(3.0, min(frame.shape[:2]) / 70.0))
    layer = np.zeros_like(frame); layer[:] = color
    a = (blur.astype(np.float32) / 255.0 * strength)[..., None]
    return np.clip(frame.astype(np.float32) * (1-a) + layer.astype(np.float32) * a, 0, 255).astype(np.uint8)


def _polygon(frame: np.ndarray, pts: list[tuple[int, int]], color: tuple[int, int, int], outline: tuple[int, int, int] | None = None, thick: int = 1) -> None:
    arr = np.asarray(pts, np.int32)
    cv2.fillPoly(frame, [arr], color, cv2.LINE_AA)
    if outline is not None:
        cv2.polylines(frame, [arr], True, outline, thick, cv2.LINE_AA)


def _crowd(frame: np.ndarray, rng: np.random.Generator, floor_y: int, density: float, color: tuple[int, int, int], pulse: float = 0.0) -> None:
    h, w = frame.shape[:2]
    count = max(4, int(w / 70 * (0.35 + density)))
    for i in range(count):
        x = int((i + .4 + rng.uniform(-.25, .25)) / count * w)
        scale = rng.uniform(.55, 1.1)
        body_h = int(h * .16 * scale)
        bob = int(math.sin(i * 1.7 + pulse * 5.0) * h * .008 * density)
        y = floor_y + bob
        head_r = max(2, int(body_h * .09))
        cv2.circle(frame, (x, y-body_h), head_r, color, -1, cv2.LINE_AA)
        shoulders = int(body_h * .19)
        _polygon(frame, [(x-shoulders, y-int(body_h*.72)), (x+shoulders, y-int(body_h*.72)),
                         (x+int(shoulders*.75), y), (x-int(shoulders*.75), y)], color)
        if density > .48 and i % 3 == 0:
            arm_y = y-int(body_h*.62)
            lift = int(body_h * (.30 + .25 * max(0.0, math.sin(pulse*7+i))))
            cv2.line(frame, (x-shoulders+2, arm_y), (x-int(shoulders*1.3), arm_y-lift), color, max(1, head_r), cv2.LINE_AA)


class CyberWorldRenderer:
    def __init__(self, width: int, height: int, seed: int):
        self.w = width; self.h = height; self.seed = int(seed)

    def render(self, world: str, scene_type: str, t: float, energy: float, impact: float,
               brightness: float, shot: int, media: np.ndarray | None = None,
               crowd_density: float = .55) -> tuple[np.ndarray, WorldFrameInfo]:
        if world == "future_noir_cel":
            return self._future_noir(scene_type, t, energy, impact, brightness, shot, media, crowd_density)
        return self._graphic_grit(scene_type, t, energy, impact, brightness, shot, media, crowd_density)

    def _graphic_grit(self, scene: str, t: float, e: float, impact: float, bright: float,
                      shot: int, media: np.ndarray | None, crowd_density: float) -> tuple[np.ndarray, WorldFrameInfo]:
        rng = np.random.default_rng(self.seed + shot * 104729 + int(t * 2))
        if scene == "red_apartment":
            frame = _gradient(self.h, self.w, (18, 5, 24), (18, 12, 80))
            cv2.rectangle(frame, (0, 0), (self.w, self.h), (15, 12, 65), -1)
            floor = int(self.h * .82)
            cv2.rectangle(frame, (0, floor), (self.w, self.h), (7, 5, 18), -1)
            for i in range(3):
                x0 = int(self.w * (.12 + i*.31)); y0 = int(self.h*.18)
                cv2.rectangle(frame, (x0, y0), (x0+int(self.w*.22), int(self.h*.72)), (20, 10, 55), -1)
                cv2.rectangle(frame, (x0+8, y0+8), (x0+int(self.w*.22)-8, int(self.h*.72)-8), (9, 6, 28), -1)
            # Black ink cloud.
            for _ in range(24):
                x = int(self.w*(.66+rng.normal(0,.08))); y=int(self.h*(.42+rng.normal(0,.12)))
                r=max(8,int(self.h*rng.uniform(.025,.09)))
                cv2.circle(frame,(x,y),r,(2,1,6),-1,cv2.LINE_AA)
            frame = self._grit(frame, .26)
            return frame, WorldFrameInfo(int(self.h*.48), floor, (int(self.w*.72), int(self.h*.38)))

        if scene == "cyber_lab":
            frame = _gradient(self.h, self.w, (42, 6, 52), (14, 4, 20))
            floor = int(self.h*.78)
            for i in range(7):
                x=int(self.w*(.06+i*.145)); cv2.line(frame,(x,int(self.h*.12)),(x-int(self.w*.06),floor),(145,25,180),2,cv2.LINE_AA)
            for y in np.linspace(self.h*.18,floor,7):
                cv2.line(frame,(0,int(y)),(self.w,int(y)),(90,15,125),1,cv2.LINE_AA)
            cx, cy=int(self.w*.72),int(self.h*.40)
            cv2.circle(frame,(cx,cy),int(self.h*.18),(210,55,240),2,cv2.LINE_AA)
            cv2.circle(frame,(cx,cy),int(self.h*.12),(255,150,245),1,cv2.LINE_AA)
            for a in np.linspace(0,math.tau,9,endpoint=False):
                x=int(cx+math.cos(a+t*.4)*self.h*.18); y=int(cy+math.sin(a+t*.4)*self.h*.18)
                cv2.line(frame,(cx,cy),(x,y),(150,45,210),1,cv2.LINE_AA)
            if media is not None:
                panel=cv2.resize(media,(int(self.w*.25),int(self.h*.34)))
                panel=cv2.addWeighted(panel,.35,np.full_like(panel,(120,20,160)),.65,0)
                frame[int(self.h*.18):int(self.h*.52),int(self.w*.08):int(self.w*.33)]=panel
            return self._grit(frame,.18), WorldFrameInfo(int(self.h*.43),floor,(cx,cy))

        if scene == "stage_riot":
            frame = _gradient(self.h,self.w,(10,6,18),(12,8,45))
            floor=int(self.h*.80)
            # Stage trusses and energy arcs.
            for i in range(8):
                x=int(i*self.w/7); cv2.line(frame,(x,0),(int(self.w*.5),int(self.h*.35)),(80,18,130),1,cv2.LINE_AA)
            for i in range(5):
                x=int(self.w*(.12+i*.19));
                cv2.rectangle(frame,(x,int(self.h*.08)),(x+int(self.w*.04),int(self.h*.48)),(20,8,68),-1)
                cv2.rectangle(frame,(x+3,int(self.h*.08)),(x+int(self.w*.04)-3,int(self.h*.48)),(80,22,170),1)
            mask=np.zeros((self.h,self.w),np.uint8)
            pts=[]
            for k in range(24):
                x=int(k/(23)*self.w); y=int(self.h*(.09+.04*math.sin(k*1.7+t*4)+.025*rng.normal()))
                pts.append((x,y))
            cv2.polylines(mask,[np.asarray(pts)],False,255,max(1,int(self.h*.006)),cv2.LINE_AA)
            frame=_glow(frame,mask,(255,160,255),.72+.25*impact)
            cv2.polylines(frame,[np.asarray(pts)],False,(255,245,255),max(1,int(self.h*.002)),cv2.LINE_AA)
            _crowd(frame,rng,floor,crowd_density,(3,2,9),t+impact)
            if impact>.55:
                cv2.circle(frame,(int(self.w*.5),int(self.h*.48)),int(self.h*(.05+.10*impact)),(255,225,255),-1,cv2.LINE_AA)
            return self._grit(frame,.28), WorldFrameInfo(int(self.h*.44),floor,(int(self.w*.5),int(self.h*.42)))

        if scene in {"hologram_plaza","neon_megacity"}:
            frame=_gradient(self.h,self.w,(70,4,82),(12,3,24))
            horizon=int(self.h*.58); floor=int(self.h*.88)
            for i in range(18):
                bw=int(self.w*rng.uniform(.035,.09)); x=int(i*self.w/17-bw*.5)
                bh=int(self.h*rng.uniform(.18,.55)); top=horizon-bh
                col=(int(rng.uniform(20,65)),int(rng.uniform(5,25)),int(rng.uniform(55,145)))
                cv2.rectangle(frame,(x,top),(x+bw,horizon),col,-1)
                for yy in range(top+8,horizon-5,max(8,int(self.h*.025))):
                    if rng.random()<.72:
                        cv2.line(frame,(x+4,yy),(x+bw-4,yy),(100,25,180),1)
            # Giant hologram silhouette/screen.
            cx=int(self.w*(.70 if shot%2 else .32)); cy=int(self.h*.30)
            rr=int(self.h*(.20+.03*math.sin(t*.7)))
            mask=np.zeros((self.h,self.w),np.uint8); cv2.circle(mask,(cx,cy),rr,180,-1,cv2.LINE_AA)
            cv2.rectangle(mask,(cx-int(rr*.55),cy), (cx+int(rr*.55),cy+int(rr*1.2)),145,-1)
            frame=_glow(frame,mask,(255,45,245),.68)
            if media is not None:
                panel=cv2.resize(media,(rr*2,rr*2))
                gray=cv2.cvtColor(panel,cv2.COLOR_BGR2GRAY); panel=cv2.applyColorMap(gray,cv2.COLORMAP_MAGMA)
                a=(mask[max(0,cy-rr):cy+rr,max(0,cx-rr):cx+rr].astype(np.float32)/255)[...,None]
                y0=max(0,cy-rr);x0=max(0,cx-rr); y1=min(self.h,y0+panel.shape[0]);x1=min(self.w,x0+panel.shape[1])
                ph,pw=y1-y0,x1-x0
                if ph>0 and pw>0:
                    frame[y0:y1,x0:x1]=np.clip(frame[y0:y1,x0:x1]*(1-a[:ph,:pw]*.55)+panel[:ph,:pw]*a[:ph,:pw]*.55,0,255).astype(np.uint8)
            cv2.rectangle(frame,(0,horizon),(self.w,self.h),(4,2,12),-1)
            for i in range(12):
                y=int(horizon+(i/12)**1.7*(self.h-horizon)); cv2.line(frame,(0,y),(self.w,y),(55,8,80),1)
            _crowd(frame,rng,floor,crowd_density*.75,(2,1,8),t)
            return self._grit(frame,.23), WorldFrameInfo(horizon,floor,(cx,cy))

        if scene == "surveillance_alley":
            frame=_gradient(self.h,self.w,(26,5,42),(5,3,15)); horizon=int(self.h*.48); floor=int(self.h*.90)
            _polygon(frame,[(0,0),(int(self.w*.32),0),(int(self.w*.44),floor),(0,self.h)],(8,4,24))
            _polygon(frame,[(self.w,0),(int(self.w*.69),0),(int(self.w*.56),floor),(self.w,self.h)],(12,4,27))
            for i in range(10):
                y=int(horizon+(i/10)**1.5*(floor-horizon)); cv2.line(frame,(int(self.w*.44),y),(int(self.w*.56),y),(120,20,145),1)
            # Surveillance camera.
            arm=(int(self.w*.78),int(self.h*.20)); head=(int(self.w*.67),int(self.h*.27))
            cv2.line(frame,arm,head,(120,105,150),max(3,int(self.h*.014)),cv2.LINE_AA)
            _polygon(frame,[(head[0]-int(self.w*.07),head[1]-int(self.h*.035)),(head[0]+int(self.w*.05),head[1]-int(self.h*.015)),
                            (head[0]+int(self.w*.04),head[1]+int(self.h*.045)),(head[0]-int(self.w*.08),head[1]+int(self.h*.035))],(45,35,65),(220,100,230),2)
            cone=np.zeros_like(frame); pts=np.asarray([head,(int(self.w*.30),floor),(int(self.w*.58),floor)],np.int32);cv2.fillPoly(cone,[pts],(120,30,160))
            frame=cv2.addWeighted(frame,1,cone,.18,0)
            self._rain(frame,t,.65)
            return self._grit(frame,.20),WorldFrameInfo(horizon,floor,head)

        if scene == "underground_train":
            frame=_gradient(self.h,self.w,(20,4,35),(8,2,15)); floor=int(self.h*.84); van=(int(self.w*.5),int(self.h*.32))
            for x in np.linspace(-self.w*.2,self.w*1.2,14): cv2.line(frame,(int(x),self.h),van,(100,12,120),1)
            for k in range(1,12):
                u=k/12; y=int(van[1]+(self.h-van[1])*(u**1.6)); cv2.line(frame,(0,y),(self.w,y),(60,8,80),1)
            for side in [-1,1]:
                x0=int(self.w*(.18 if side<0 else .82)); cv2.line(frame,(x0,0),(int(self.w*.5+side*self.w*.09),floor),(190,20,160),3)
            return self._grit(frame,.22),WorldFrameInfo(van[1],floor,van)

        # cable_cathedral fallback
        frame=_gradient(self.h,self.w,(12,4,25),(4,2,11)); floor=int(self.h*.86); center=(int(self.w*.5),int(self.h*.32))
        for i in range(28):
            a=i/28*math.tau+t*.035; r=self.w*(.18+.42*(i%5)/5)
            x=int(center[0]+math.cos(a)*r); y=int(center[1]+math.sin(a)*self.h*.42)
            cv2.line(frame,center,(x,y),(95,14,120),1,cv2.LINE_AA)
        for i in range(9):
            x=int(self.w*i/8); pts=[]
            for k in range(30):
                u=k/29; pts.append((int(x+(self.w*.5-x)*u),int(self.h*.06+self.h*.72*u+math.sin(u*math.pi)*self.h*.10)))
            cv2.polylines(frame,[np.asarray(pts)],False,(205,45,210),1,cv2.LINE_AA)
        return self._grit(frame,.25),WorldFrameInfo(center[1],floor,center)

    def _future_noir(self, scene: str, t: float, e: float, impact: float, bright: float,
                     shot: int, media: np.ndarray | None, crowd_density: float) -> tuple[np.ndarray, WorldFrameInfo]:
        rng=np.random.default_rng(self.seed+shot*65537+int(t))
        if scene == "rooftop_sunset":
            frame=_gradient(self.h,self.w,(85,35,180),(20,105,245)); horizon=int(self.h*.56); floor=int(self.h*.83)
            cv2.circle(frame,(int(self.w*.18),horizon),int(self.h*.09),(80,170,255),-1,cv2.LINE_AA)
            self._noir_skyline(frame,horizon,rng)
            cv2.rectangle(frame,(0,floor),(self.w,self.h),(18,10,30),-1)
            cv2.line(frame,(0,floor),(self.w,floor),(210,60,220),2)
            return frame,WorldFrameInfo(horizon,floor,(int(self.w*.18),horizon))

        if scene == "future_club":
            frame=_gradient(self.h,self.w,(48,10,72),(10,7,30)); floor=int(self.h*.84); center=(int(self.w*.63),int(self.h*.28))
            # Art-deco arches.
            for i in range(4):
                pad=int(self.w*(.06+i*.08)); cv2.ellipse(frame,center,(int(self.w*.42-pad),int(self.h*.46-pad*.4)),180,0,180,(135,45,210),max(2,int(self.h*.004)))
            for i in range(7):
                x=int(self.w*(.05+i*.15)); cv2.rectangle(frame,(x,int(self.h*.13)),(x+int(self.w*.045),floor),(35,15,82),-1)
                cv2.line(frame,(x+int(self.w*.02),int(self.h*.13)),(x+int(self.w*.02),floor),(210,45,235),2)
            cv2.rectangle(frame,(0,floor),(self.w,self.h),(13,8,28),-1)
            for i in range(8):
                x=int(i*self.w/8); cv2.line(frame,(x,floor),(int(self.w*.5),self.h),(70,25,105),1)
            _crowd(frame,rng,floor,crowd_density,(9,5,23),t+impact)
            return frame,WorldFrameInfo(int(self.h*.42),floor,center)

        if scene == "intimate_room":
            frame=_gradient(self.h,self.w,(35,18,60),(38,95,190)); floor=int(self.h*.82)
            cv2.rectangle(frame,(int(self.w*.08),int(self.h*.14)),(int(self.w*.92),floor),(22,12,38),-1)
            cv2.rectangle(frame,(int(self.w*.14),int(self.h*.21)),(int(self.w*.86),int(self.h*.66)),(45,70,115),-1)
            # Warm skyline window.
            y0,y1=int(self.h*.21),int(self.h*.65); x0,x1=int(self.w*.16),int(self.w*.84)
            window=_gradient(y1-y0,x1-x0,(75,55,180),(35,130,245))
            frame[y0:y1,x0:x1]=window
            for i in range(10):
                x=int(self.w*(.18+i*.065)); hh=int(self.h*rng.uniform(.08,.27)); cv2.rectangle(frame,(x,int(self.h*.65)-hh),(x+int(self.w*.035),int(self.h*.65)),(35,35,75),-1)
            cv2.rectangle(frame,(0,floor),(self.w,self.h),(16,9,27),-1)
            return frame,WorldFrameInfo(int(self.h*.48),floor,(int(self.w*.52),int(self.h*.32)))

        if scene in {"violet_alley","night_overlook"}:
            frame=_gradient(self.h,self.w,(30,8,55),(8,7,24)); horizon=int(self.h*.48);floor=int(self.h*.90)
            _polygon(frame,[(0,0),(int(self.w*.35),0),(int(self.w*.45),floor),(0,self.h)],(15,8,35))
            _polygon(frame,[(self.w,0),(int(self.w*.68),0),(int(self.w*.56),floor),(self.w,self.h)],(23,10,44))
            for side in [0,1]:
                x=int(self.w*(.19 if side==0 else .79)); cv2.rectangle(frame,(x,int(self.h*.15)),(x+int(self.w*.06),int(self.h*.68)),(55,18,85),-1)
                cv2.rectangle(frame,(x+4,int(self.h*.18)),(x+int(self.w*.06)-4,int(self.h*.64)),(210,50,205),2)
            for k in range(10):
                u=k/10; y=int(horizon+(floor-horizon)*(u**1.6)); cv2.line(frame,(int(self.w*.45),y),(int(self.w*.56),y),(75,30,100),1)
            self._rain(frame,t,.45)
            return frame,WorldFrameInfo(horizon,floor,(int(self.w*.5),horizon))

        if scene == "chase_corridor":
            frame=np.zeros((self.h,self.w,3),np.uint8); frame[:]=(18,8,35); van=(int(self.w*.5),int(self.h*.42)); floor=int(self.h*.90)
            for x in np.linspace(-self.w*.3,self.w*1.3,14): cv2.line(frame,(int(x),self.h),van,(85,28,130),2)
            for y in np.linspace(0,self.h,10): cv2.line(frame,(0,int(y)),van,(65,20,110),1)
            for i in range(6):
                u=(i/6+t*.6)%1; y=int(van[1]+(self.h-van[1])*(u**1.7)); cv2.line(frame,(0,y),(self.w,y),(180,55,220),max(1,int(3*u)))
            return frame,WorldFrameInfo(van[1],floor,van)

        if scene == "corporate_tower":
            frame=_gradient(self.h,self.w,(35,12,72),(9,8,25));floor=int(self.h*.86); cx=int(self.w*.5)
            _polygon(frame,[(cx-int(self.w*.18),floor),(cx-int(self.w*.10),int(self.h*.08)),(cx+int(self.w*.10),int(self.h*.08)),(cx+int(self.w*.18),floor)],(28,15,60),(120,40,180),2)
            for y in range(int(self.h*.14),floor,int(self.h*.045)):
                cv2.line(frame,(cx-int(self.w*.10),y),(cx+int(self.w*.10),y),(55,40,105),1)
            return frame,WorldFrameInfo(int(self.h*.44),floor,(cx,int(self.h*.24)))

        # skyline_transit fallback
        frame=_gradient(self.h,self.w,(58,22,110),(16,73,165));horizon=int(self.h*.60);floor=int(self.h*.88)
        self._noir_skyline(frame,horizon,rng)
        cv2.rectangle(frame,(0,int(self.h*.72)),(self.w,int(self.h*.78)),(20,10,42),-1)
        for i in range(9):
            x=int((i/8)*self.w+t*80)%self.w; cv2.rectangle(frame,(x,int(self.h*.70)),(min(self.w,x+int(self.w*.08)),int(self.h*.80)),(55,25,95),-1)
        return frame,WorldFrameInfo(horizon,floor,(int(self.w*.5),horizon))

    def _noir_skyline(self, frame: np.ndarray, horizon: int, rng: np.random.Generator) -> None:
        for i in range(18):
            x=int(i*self.w/17-self.w*.03); bw=int(self.w*rng.uniform(.035,.085)); bh=int(self.h*rng.uniform(.12,.48))
            col=(int(rng.uniform(25,60)),int(rng.uniform(15,45)),int(rng.uniform(40,85)))
            cv2.rectangle(frame,(x,horizon-bh),(x+bw,horizon),col,-1)
            if i%3==0:
                _polygon(frame,[(x,horizon-bh),(x+bw//2,horizon-bh-int(self.h*.08)),(x+bw,horizon-bh)],col)
            for yy in range(horizon-bh+8,horizon-4,max(8,int(self.h*.025))):
                if rng.random()>.35: cv2.line(frame,(x+4,yy),(x+bw-4,yy),(150,35,170),1)

    def _rain(self, frame: np.ndarray, t: float, density: float) -> None:
        rng=np.random.default_rng(self.seed+int(t*10))
        count=int(self.w/8*density)
        for _ in range(count):
            x=int(rng.integers(0,self.w)); y=int(rng.integers(-self.h,self.h)); length=int(rng.uniform(self.h*.015,self.h*.055))
            y=(y+int(t*170))%(self.h+length)-length
            cv2.line(frame,(x,y),(x-int(length*.25),y+length),(110,100,185),1,cv2.LINE_AA)

    def _grit(self, frame: np.ndarray, amount: float) -> np.ndarray:
        rng=np.random.default_rng(self.seed+frame.shape[0]+frame.shape[1])
        noise=rng.normal(0,255*amount*.16,frame.shape[:2]).astype(np.float32)
        out=np.clip(frame.astype(np.float32)+noise[...,None],0,255).astype(np.uint8)
        # Halftone/ink texture, intentionally subtle.
        yy,xx=np.indices(frame.shape[:2]); dots=((xx%5==0)&(yy%5==0))
        out[dots]=(out[dots].astype(np.float32)*(.78+amount*.12)).astype(np.uint8)
        return out
