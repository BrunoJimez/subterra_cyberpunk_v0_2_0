from pathlib import Path
import sys

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from subterra_cyberpunk.worlds import CyberWorldRenderer, GRIT_SCENES, NOIR_SCENES


def main():
    out=ROOT/"tests"/"_tmp";out.mkdir(exist_ok=True)
    renderer=CyberWorldRenderer(320,180,1234)
    frames=[]
    for world,scenes in [("neon_graphic_grit",GRIT_SCENES),("future_noir_cel",NOIR_SCENES)]:
        for i,scene in enumerate(scenes):
            frame,_=renderer.render(world,scene,1.25,.6,.7,.5,i,None,.55)
            assert frame.shape==(180,320,3)
            assert frame.dtype==np.uint8
            assert float(frame.std())>3
            frames.append(cv2.resize(frame,(240,135)))
    rows=[]
    for i in range(0,len(frames),4): rows.append(cv2.hconcat(frames[i:i+4]))
    gallery=cv2.vconcat(rows)
    cv2.imwrite(str(out/"world_gallery.jpg"),gallery)
    print(f"OK: {len(frames)} cenários · {out/'world_gallery.jpg'}")


if __name__=="__main__":main()
