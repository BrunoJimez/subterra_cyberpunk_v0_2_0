# Ponte local image-to-video

## Objetivo

Permitir planos generativos curtos sem API paga e sem tornar a instalação principal dependente de um modelo específico.

## Etapa 1 — exportar

Escolha `package` ou `package_and_clips`. O render salva:

- `shot_XXXX_keyframe.png`;
- `shot_XXXX.json`;
- `manifest.json`.

## Etapa 2 — gerar localmente

Use o keyframe e o prompt JSON em sua ferramenta local. Mantenha a duração indicada e evite cortes internos.

## Etapa 3 — nomear

Salve o resultado como `shot_XXXX.mp4` na pasta de clipes.

## Etapa 4 — recompor

Escolha `clips` ou `package_and_clips`. O controle `i2v_strength` define quanto o clipe substitui o plano procedural.

## Compatibilidade

Contêineres aceitos: MP4, MKV, MOV, AVI e WEBM. O clipe é redimensionado para preencher o quadro e limitado à duração do plano.
