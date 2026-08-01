# SUBTERRA-CYBERPUNK v0.2.0 — Character Film Engine

Programa local para transformar música em **filme cyberpunk com personagens animados**, derivado da base validada do SUBTERRA-CYBERPUNK v0.1.0 e da infraestrutura de exportação do SUBTERRA Fase 0.2.

## Novidades da Fase 0.2

- continuidade de posição, lado de tela, direção do olhar e profundidade entre planos;
- roteiro plano a plano em `story.json`, com bloqueio de personagens e arcos narrativos;
- rig 2.5D heurístico salvo em `.rig.json`;
- movimentos adicionais: olhar lateral, aceno, alcance, recuo, agachamento, salto e pose de combate;
- movimento secundário de cabelo, casacos e bordas gráficas;
- sincronia labial gráfica para vocalistas e performers;
- rastros de ação e câmeras suavizadas;
- novas transições: whip, silhouette wipe e match shape;
- ponte local image-to-video por keyframes e clipes curtos, sem API paga;
- relatório HTML ampliado com arcos, continuidade e plano a plano.

## Dois mundos gráficos

### `neon_graphic_grit`

Preto, vermelho, magenta, tinta, halftone, hologramas, cabos, apartamentos, laboratórios, megacidade e multidões.

### `future_noir_cel`

Cel shading, formas angulares, terraços, becos, clubes, corredores, skyline violeta e luz laranja de pôr do sol.

Também existem:

- `hybrid_cyberpunk`: alterna os dois mundos;
- `auto_director`: escolhe o mundo pela estrutura e energia musical.

Os estilos são autorais e não reproduzem personagens, marcas ou cenários específicos das referências.

## Continuidade e coreografia

A Fase 0.2 gera uma lista de planos. Cada plano registra:

- personagens visíveis;
- posição inicial e final;
- escala e profundidade;
- direção do olhar;
- ação;
- entrada e saída;
- câmera, transição, cenário e filtro;
- prompt auxiliar para image-to-video local.

O controle **Continuidade entre planos** determina quanto o diretor preserva posições e relações espaciais. Valores entre `0.75` e `0.90` são recomendados para filmes narrativos.

## Character Lift 2.5D

Cada referência pode receber:

- papel: protagonista, apoio, antagonista, vocalista, performer, holograma, multidão, android ou criatura;
- movimento automático ou específico;
- nome e continuidade narrativa.

O motor utiliza transparência existente ou recorte automático, identifica o rosto quando possível e infere regiões de cabeça, tronco, laterais e parte inferior do corpo. Ele aplica respiração, inclinação, deslocamento, cabelo/roupa, piscada e boca gráfica.

Preparar e inspecionar um personagem:

```powershell
python cyberpunk.py prepare-character "personagem.jpg::protagonist::auto::Nome" personagem_recortado.png
```

São produzidos:

- `personagem_recortado.png`;
- `personagem_recortado.rig.json`.

PNG transparente com um único personagem continua sendo a entrada de maior qualidade.

## Ponte image-to-video local

O programa não obriga a instalação de um modelo generativo pesado. Em vez disso, oferece quatro modos:

- `off`: somente animação 2.5D;
- `package`: exporta keyframe e JSON para cada plano renderizado;
- `clips`: usa clipes locais prontos;
- `package_and_clips`: exporta pacotes e usa clipes que já existirem.

Cada pacote contém:

- `shot_0000_keyframe.png`;
- `shot_0000.json` com duração, câmera, mundo, personagens e prompt;
- `manifest.json`.

Depois de gerar o clipe em uma aplicação local de image-to-video, salve-o como:

```text
shot_0000.mp4
shot_0001.mp4
shot_0002.mp4
```

Selecione a pasta de clipes na aba **I2V local**. O SUBTERRA mistura o clipe com o plano procedural e mantém montagem, áudio, filtros e exportação.

Verificar quais clipes estão faltando:

```powershell
python cyberpunk.py i2v-status output\i2v_packages output\i2v_clips
```

## Instalação no Windows

1. Instale Python 3.11 ou 3.12.
2. Instale FFmpeg e adicione-o ao `PATH`.
3. Extraia o projeto em uma pasta própria.
4. Execute `INSTALAR_WINDOWS.bat`.
5. Execute `DIAGNOSTICO_WINDOWS.bat`.
6. Abra `ABRIR_CYBERPUNK.bat`.

## Primeiro teste recomendado

1. escolha uma música;
2. adicione uma ou duas imagens de personagens;
3. selecione `auto_director`;
4. mantenha continuidade em `0.82`;
5. use 640×360 ou 1280×720, escala interna 0.50;
6. clique em **Prévia de 15 s**;
7. depois use 1920×1080, escala 0.65–0.75 para o filme final.

## Exemplo de CLI

```powershell
python cyberpunk.py render musica.wav output\filme.mp4 `
  --character "heroina.png::protagonist::dramatic_turn::Heroina" `
  --character "vocalista.png::vocalist::sing::Vocalista" `
  --world auto_director `
  --continuity-strength 0.84 `
  --secondary-motion 0.70 `
  --lip-sync 0.65 `
  --width 1920 --height 1080 --render-scale 0.75
```

Exportar pacotes I2V:

```powershell
python cyberpunk.py render musica.wav output\preview.mp4 `
  --character "heroina.png::protagonist::auto::Heroina" `
  --i2v-mode package `
  --i2v-package-dir output\i2v_packages `
  --preview-seconds 15
```

Usar clipes gerados localmente:

```powershell
python cyberpunk.py render musica.wav output\filme_i2v.mp4 `
  --character "heroina.png::protagonist::auto::Heroina" `
  --i2v-mode clips `
  --i2v-clips-dir output\i2v_clips `
  --i2v-strength 0.82
```

## Saída

- MP4, MKV e AVI;
- H.264/H.265 e encoders de hardware detectados pelo FFmpeg;
- resolução digitável e presets 720p, 1080p, 2K, 4K, cinema, vertical, quadrado e ultrawide;
- duração correspondente ao áudio;
- áudio `preserve`, `streaming`, `cinema`, `club` ou `normalize`;
- seed, roteiro, personagens, rigs, análise e relatório salvos na pasta do projeto.

## Limites honestos

A animação principal continua sendo 2.5D: ela movimenta a referência e a integra ao mundo, mas não inventa com segurança partes ocultas ou novos ângulos anatômicos. A ponte I2V permite substituir planos curtos por vídeos produzidos localmente, mas o modelo gerador não é distribuído com este pacote. Isso mantém a instalação leve, gratuita e funcional mesmo sem IA generativa.

## Segurança visual

O limite de flashes permanece ativado por padrão. Revise produções com strobe, cortes rápidos e alto contraste antes da publicação.

## Licença

Código sob licença MIT. O usuário é responsável pelos direitos das músicas, imagens, vídeos, fontes, personagens e clipes importados.
