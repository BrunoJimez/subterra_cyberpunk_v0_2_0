from __future__ import annotations

import html
import json
from pathlib import Path


def write_html_report(analysis_path: str | Path, story_path: str | Path, output_path: str | Path) -> None:
    analysis=json.loads(Path(analysis_path).read_text(encoding="utf-8"));story=json.loads(Path(story_path).read_text(encoding="utf-8"))
    rows="".join(f"<tr><td>{s['index']}</td><td>{s['start']:.2f}</td><td>{s['end']:.2f}</td><td>{html.escape(s['role'])}</td><td>{s['energy']:.2f}</td><td>{s.get('bass',0):.2f}</td></tr>" for s in analysis["sections"])
    shots="".join(
        f"<tr><td>{s.get('shot')}</td><td>{float(s.get('start',0)):.2f}</td><td>{float(s.get('end',0)):.2f}</td><td>{html.escape(str(s.get('world','')))}</td>"
        f"<td>{html.escape(str(s.get('location','')))}</td><td>{html.escape(str(s.get('camera','')))}</td><td>{html.escape(', '.join(map(str,s.get('visible_characters',[]))))}</td>"
        f"<td>{html.escape(str(s.get('filter','')))}</td><td>{html.escape(str(s.get('transition','')))}</td></tr>" for s in story.get("shots",[])
    )
    chars="".join(f"<tr><td>{i}</td><td>{html.escape(c.get('name',''))}</td><td>{html.escape(c.get('role',''))}</td><td>{html.escape(c.get('motion',''))}</td><td><code>{html.escape(c.get('path',''))}</code></td></tr>" for i,c in enumerate(story.get("characters",[]))) or "<tr><td colspan='5'>Nenhuma imagem de personagem; o renderizador usará personagens gráficos procedurais.</td></tr>"
    arcs="".join(f"<tr><td>{a.get('character')}</td><td>{html.escape(str(a.get('name','')))}</td><td>{html.escape(str(a.get('dramatic_goal','')))}</td><td>{html.escape(str(a.get('motif','')))}</td><td>{float(a.get('home_screen_x',.5)):.2f}</td></tr>" for a in story.get("character_arcs",[])) or "<tr><td colspan='5'>Arcos procedurais.</td></tr>"
    content=f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>SUBTERRA-CYBERPUNK report</title>
<style>body{{font-family:Arial,sans-serif;background:#09070d;color:#eee;max-width:1280px;margin:40px auto;padding:0 20px}}h1,h2{{color:#ff58c8}}table{{border-collapse:collapse;width:100%;margin-bottom:32px;font-size:14px}}td,th{{border:1px solid #39243f;padding:8px;text-align:left}}code{{color:#9df9e9}}.tag{{display:inline-block;background:#25152a;padding:5px 8px;margin:3px;border-radius:4px}}</style></head><body>
<h1>SUBTERRA-CYBERPUNK 0.2 — relatório do filme</h1><p><b>Áudio:</b> <code>{html.escape(analysis['source'])}</code></p>
<p><b>Duração:</b> {analysis['duration_seconds']:.2f}s · <b>BPM:</b> {analysis['estimated_bpm']:.2f} · <b>Tom:</b> {html.escape(analysis['estimated_key'])} · <b>Seed:</b> {story['seed']}</p>
<p>{''.join(f"<span class='tag'>{html.escape(t)}</span>" for t in analysis['mood_tags'])}</p>
<p><b>Direção de mundo:</b> {html.escape(story.get('world_mode','auto_director'))} · <b>Densidade de montagem:</b> {story.get('edit_density',0):.2f} · <b>Continuidade:</b> {story.get('continuity_strength',0):.2f} · <b>Planos:</b> {len(story.get('shots',[]))}</p>
<h2>Personagens</h2><table><tr><th>#</th><th>Nome</th><th>Papel</th><th>Movimento</th><th>Fonte</th></tr>{chars}</table>
<h2>Arcos e continuidade</h2><table><tr><th>#</th><th>Nome</th><th>Objetivo</th><th>Motivo</th><th>Lado-base da tela</th></tr>{arcs}</table>
<h2>Estrutura musical</h2><table><tr><th>#</th><th>Início</th><th>Fim</th><th>Função</th><th>Energia</th><th>Bass</th></tr>{rows}</table>
<h2>Plano a plano</h2><table><tr><th>#</th><th>Início</th><th>Fim</th><th>Mundo</th><th>Local</th><th>Câmera</th><th>Personagens</th><th>Filtro</th><th>Transição</th></tr>{shots}</table>
</body></html>"""
    Path(output_path).write_text(content,encoding="utf-8")
