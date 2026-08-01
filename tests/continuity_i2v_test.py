from pathlib import Path
import json
import sys

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from subterra_cyberpunk.i2v import I2VClipPool, ShotPackageWriter
from subterra_cyberpunk.narrative import build_story


def main():
    out=ROOT/"tests"/"_tmp"/"continuity_i2v";out.mkdir(parents=True,exist_ok=True)
    analysis={
        "source":"synthetic.wav","duration_seconds":12.0,"estimated_bpm":120.0,"estimated_key":"A minor","mood_tags":["dark","driving"],
        "sections":[
            {"index":0,"start":0.0,"end":4.0,"role":"intro","energy":.25},
            {"index":1,"start":4.0,"end":8.0,"role":"buildup","energy":.55},
            {"index":2,"start":8.0,"end":12.0,"role":"drop","energy":.88},
        ],
    }
    analysis_path=out/"analysis.json";analysis_path.write_text(json.dumps(analysis),encoding="utf-8")
    chars=[
        {"path":"hero.png","name":"Hero","role":"protagonist","motion":"auto","scale":.72,"depth":.5,"flip":False},
        {"path":"rival.png","name":"Rival","role":"antagonist","motion":"auto","scale":.72,"depth":.5,"flip":False},
    ]
    story_path=out/"story.json";story=build_story(analysis_path,12345,story_path,"hybrid_cyberpunk","none",[],.65,chars,.86)
    assert story["version"]=="0.2.0" and len(story["shots"])>=3
    assert len(story["character_arcs"])==2
    seen=False
    for shot in story["shots"]:
        for block in shot["blocking"].values():
            assert 0.08<=float(block["x_end"])<=.92
            assert block["action"]
            seen=True
    assert seen

    packages=out/"packages";writer=ShotPackageWriter(packages,story,320,180,12)
    keyframe=np.zeros((180,320,3),np.uint8);keyframe[:]=(120,20,180)
    writer.write(story["shots"][0],keyframe);writer.finalize()
    assert (packages/"shot_0000_keyframe.png").exists() and (packages/"shot_0000.json").exists() and (packages/"manifest.json").exists()

    clips=out/"clips";clips.mkdir(exist_ok=True);path=clips/"shot_0000.avi"
    vw=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"MJPG"),10,(320,180))
    for i in range(10):
        frame=np.zeros((180,320,3),np.uint8);frame[:]=(20+i*10,40,180);vw.write(frame)
    vw.release()
    pool=I2VClipPool(clips,320,180);frame=pool.get(0,.4);pool.close()
    assert frame is not None and frame.shape==(180,320,3) and float(frame.mean())>10
    print(f"OK: continuidade + ponte I2V · {out}")


if __name__=="__main__":main()
