# Arquitetura — SUBTERRA-CYBERPUNK 0.2

## Fluxo principal

1. `audio_analysis.py` extrai BPM, batidas, energia, impacto, brilho, textura, fluxo e seções.
2. `narrative.py` transforma as seções em cenas, planos, arcos de personagem e bloqueio espacial.
3. `character.py` recorta a referência, infere um rig 2.5D e produz atuação gráfica.
4. `worlds.py` cria os dois universos procedurais.
5. `renderer.py` compõe personagens, mundo, mídia, câmera, tipografia, filtros e áudio.
6. `i2v.py` exporta keyframes/JSON e importa clipes locais opcionais.
7. FFmpeg codifica MP4, MKV ou AVI.

## Continuidade

O roteiro registra `x_start`, `x_end`, escala, profundidade, direção do olhar e ação para cada personagem em cada plano. O parâmetro `continuity_strength` mistura o alvo novo com o estado anterior. Isso reduz saltos de lado de tela e mantém relações espaciais reconhecíveis.

## Rig 2.5D

O rig é heurístico e não depende de serviço externo. Ele usa transparência, máscara, rosto quando detectado e regiões normalizadas de cabeça, tronco, laterais e parte inferior. O arquivo `.rig.json` registra os pontos inferidos para inspeção e futuras edições.

## Ponte I2V

A ponte não executa um modelo específico. Ela padroniza a troca com qualquer sistema local:

- saída: keyframe PNG + JSON por plano;
- entrada: `shot_XXXX.mp4`;
- composição: mistura controlável com o plano procedural.

Isso evita dependência de APIs pagas e mantém o programa funcional sem IA generativa.
