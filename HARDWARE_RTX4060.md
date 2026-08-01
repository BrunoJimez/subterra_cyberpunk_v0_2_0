# Perfil recomendado — RTX 4060 8 GB / 16 GB RAM

- Prévia: 640×360 ou 1280×720, 24/30 fps, escala interna 0.50.
- Filme 1080p: escala 0.65–0.75; `h264_nvenc` ou `auto`.
- Vertical 1080×1920: escala 0.55–0.70.
- 2K: escala 0.55–0.70.
- 4K: escala 0.35–0.50 e render final; evite 60 fps na primeira tentativa.
- Para imagens de personagens acima de 4K, reduza-as antes da importação para acelerar o recorte.

O motor 2.5D desta versão roda principalmente em CPU/OpenCV; o encoder NVENC reduz o custo da compressão final. A GPU será mais importante quando um backend generativo opcional for incorporado.
