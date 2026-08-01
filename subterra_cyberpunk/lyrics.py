from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(frozen=True)
class Caption:
    start: float
    end: float
    text: str


def _timecode(value: str) -> float:
    value=value.strip().replace(',', '.')
    parts=value.split(':')
    try:
        if len(parts)==3:
            h,m,s=parts
            return int(h)*3600+int(m)*60+float(s)
        if len(parts)==2:
            m,s=parts
            return int(m)*60+float(s)
        return float(value)
    except ValueError:
        return 0.0


def parse_srt(text: str) -> list[Caption]:
    blocks=re.split(r'\n\s*\n',text.strip())
    result=[]
    for block in blocks:
        lines=[x.strip() for x in block.splitlines() if x.strip()]
        if not lines:
            continue
        timing=next((x for x in lines if '-->' in x),None)
        if not timing:
            continue
        idx=lines.index(timing)
        a,b=[x.strip().split(' ')[0] for x in timing.split('-->',1)]
        body=' '.join(lines[idx+1:]).strip()
        body=re.sub(r'<[^>]+>','',body)
        if body:
            result.append(Caption(_timecode(a),_timecode(b),body))
    return result


def parse_lrc(text: str) -> list[Caption]:
    points=[]
    for line in text.splitlines():
        matches=re.findall(r'\[(\d{1,3}:\d{1,2}(?:\.\d{1,3})?)\]',line)
        body=re.sub(r'\[[^\]]+\]','',line).strip()
        for code in matches:
            if body:
                points.append((_timecode(code),body))
    points.sort()
    result=[]
    for i,(start,body) in enumerate(points):
        end=points[i+1][0] if i+1<len(points) else start+5.0
        result.append(Caption(start,max(start+.25,end),body))
    return result


def parse_plain(text: str, duration: float) -> list[Caption]:
    lines=[re.sub(r'\s+',' ',x).strip() for x in text.splitlines() if x.strip()]
    if not lines:
        return []
    slot=max(1.0,duration/len(lines))
    return [Caption(i*slot,min(duration,(i+1)*slot),line) for i,line in enumerate(lines)]


def load_captions(path: str | Path | None, duration: float) -> list[Caption]:
    if not path:
        return []
    p=Path(path)
    if not p.exists():
        raise FileNotFoundError(f'Arquivo de letra/legenda não encontrado: {p}')
    text=p.read_text(encoding='utf-8-sig',errors='replace')
    ext=p.suffix.lower()
    if ext in {'.srt','.vtt'}:
        caps=parse_srt(text.replace('WEBVTT','',1))
    elif ext=='.lrc':
        caps=parse_lrc(text)
    else:
        caps=parse_plain(text,duration)
    return [c for c in caps if c.end>c.start and c.start<duration]


def captions_to_json(captions: list[Caption]) -> list[dict]:
    return [asdict(c) for c in captions]
