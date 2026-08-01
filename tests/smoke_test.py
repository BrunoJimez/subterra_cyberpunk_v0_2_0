from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np
import soundfile as sf

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    out=ROOT/"tests"/"_tmp";out.mkdir(exist_ok=True)
    sr=22050;t=np.arange(sr*2)/sr
    y=.20*np.sin(2*np.pi*55*t)+.08*np.sin(2*np.pi*220*t)
    y+=(np.mod(t,0.5)<.025)*.42*np.exp(-np.mod(t,0.5)*50)
    audio=out/"smoke.wav";sf.write(audio,y,sr)
    rgba=np.zeros((360,180,4),np.uint8)
    cv2.circle(rgba,(90,55),38,(105,90,200,255),-1,cv2.LINE_AA)
    cv2.fillPoly(rgba,[np.array([(45,100),(135,100),(160,340),(20,340)],np.int32)],(18,8,35,255),cv2.LINE_AA)
    char=out/"smoke_character.png";cv2.imwrite(str(char),rgba)
    video=out/"smoke.mp4"
    cmd=[sys.executable,str(ROOT/"cyberpunk.py"),"render",str(audio),str(video),"--width","320","--height","180","--fps","10","--render-scale","1.0","--preview-seconds","1.5","--world","hybrid_cyberpunk","--character",f"{char}::protagonist::dance::Smoke","--encoder","libx264","--ffmpeg-preset","ultrafast","--filter","none","--no-typography","--workdir",str(out/"project")]
    subprocess.run(cmd,cwd=ROOT,check=True)
    cap=cv2.VideoCapture(str(video));ok,frame=cap.read();cap.release()
    assert ok and frame.shape[:2]==(180,320)
    print(f"OK: smoke render · {video}")


if __name__=="__main__":main()
