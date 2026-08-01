from pathlib import Path
import sys

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from subterra_cyberpunk.character import CharacterAsset, CharacterSpec, alpha_composite


def main():
    out=ROOT/"tests"/"_tmp";out.mkdir(exist_ok=True)
    # Transparent synthetic character with an angular head and coat.
    rgba=np.zeros((420,240,4),np.uint8)
    cv2.circle(rgba,(120,72),48,(120,95,205,255),-1,cv2.LINE_AA)
    cv2.fillPoly(rgba,[np.array([(65,130),(175,130),(205,390),(35,390)],np.int32)],(22,12,38,255),cv2.LINE_AA)
    cv2.line(rgba,(65,160),(10,260),(22,12,38,255),26,cv2.LINE_AA)
    cv2.line(rgba,(175,160),(230,260),(22,12,38,255),26,cv2.LINE_AA)
    p=out/"synthetic_character.png";cv2.imwrite(str(p),rgba)
    asset=CharacterAsset(CharacterSpec(str(p),"Teste","protagonist","dance"))
    canvas=np.zeros((360,640,3),np.uint8);canvas[:]=(60,15,80)
    img,alpha=asset.rendered(1.2,.65,.8,"dance",.8,300,.6,"future_noir_cel")
    alpha_composite(canvas,img,alpha,320-img.shape[1]//2,345-img.shape[0])
    assert np.count_nonzero(alpha)>500
    cv2.imwrite(str(out/"character_lift.jpg"),canvas)
    print(f"OK: Character Lift · {out/'character_lift.jpg'}")


if __name__=="__main__":main()
