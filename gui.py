from __future__ import annotations

import random
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from subterra_cyberpunk.config import CHARACTER_ROLES, I2V_MODES, MOTION_CHOICES, RESOLUTION_PRESETS, WORLD_CHOICES
from subterra_cyberpunk.filters import FILTER_NAMES

ROOT=Path(__file__).resolve().parent


class App(tk.Tk):
    def __init__(self):
        super().__init__();self.title("SUBTERRA-CYBERPUNK 0.2 — Character Film Engine");self.geometry("1220x920");self.minsize(1040,780)
        self.audio=tk.StringVar();self.output=tk.StringVar(value=str(ROOT/"output"/"cyberpunk_film.mp4"));self.lyrics=tk.StringVar()
        self.world=tk.StringVar(value="auto_director");self.filter_name=tk.StringVar(value="auto");self.filter_intensity=tk.DoubleVar(value=.72);self.edit_density=tk.DoubleVar(value=.68)
        self.motion_strength=tk.DoubleVar(value=.72);self.secondary_motion=tk.DoubleVar(value=.68);self.lip_sync=tk.DoubleVar(value=.65);self.action_trails=tk.DoubleVar(value=.32);self.continuity_strength=tk.DoubleVar(value=.82);self.camera_smoothing=tk.DoubleVar(value=.76)
        self.character_scale=tk.DoubleVar(value=.72);self.character_outline=tk.DoubleVar(value=.55);self.crowd_density=tk.DoubleVar(value=.55);self.background_motion=tk.DoubleVar(value=.65);self.strobe=tk.DoubleVar(value=.12)
        self.typography=tk.BooleanVar(value=True);self.preserve_identity=tk.BooleanVar(value=True);self.subject_extraction=tk.StringVar(value="auto")
        self.resolution=tk.StringVar(value="1080p");self.width=tk.StringVar(value="1920");self.height=tk.StringVar(value="1080");self.fps=tk.StringVar(value="30");self.seed=tk.StringVar(value=str(random.randint(1,2_147_483_647)))
        self.render_scale=tk.StringVar(value="0.75");self.audio_mode=tk.StringVar(value="preserve");self.encoder=tk.StringVar(value="auto");self.preview_seconds=tk.StringVar(value="")
        self.character_role=tk.StringVar(value="protagonist");self.character_motion=tk.StringVar(value="auto");self.character_name=tk.StringVar(value="")
        self.i2v_mode=tk.StringVar(value="off");self.i2v_package_dir=tk.StringVar(value=str(ROOT/"output"/"i2v_packages"));self.i2v_clips_dir=tk.StringVar(value=str(ROOT/"output"/"i2v_clips"));self.i2v_strength=tk.DoubleVar(value=.82)
        self.characters:list[dict[str,str]]=[];self.media:list[str]=[];self._build()

    def _build(self):
        outer=ttk.Frame(self);outer.pack(fill="both",expand=True,padx=14,pady=12)
        ttk.Label(outer,text="SUBTERRA-CYBERPUNK 0.2",font=("Arial",22,"bold")).pack(anchor="w")
        ttk.Label(outer,text="Continuidade entre planos · rig 2.5D em camadas · atuação ampliada · ponte image-to-video local").pack(anchor="w",pady=(0,8))
        notebook=ttk.Notebook(outer);notebook.pack(fill="both",expand=True)
        tabs=[ttk.Frame(notebook) for _ in range(7)]
        for tab,name in zip(tabs,["Projeto","Personagens","Mundo","Animação","Direção visual","I2V local","Exportação"]):notebook.add(tab,text=name)
        self._build_project(tabs[0]);self._build_characters(tabs[1]);self._build_world(tabs[2]);self._build_animation(tabs[3]);self._build_visual(tabs[4]);self._build_i2v(tabs[5]);self._build_export(tabs[6])
        bottom=ttk.Frame(outer);bottom.pack(fill="x",pady=(10,0));ttk.Button(bottom,text="Diagnóstico do PC",command=self.run_diagnose).pack(side="left");ttk.Button(bottom,text="Prévia de 15 s",command=lambda:self.run_render(preview=15)).pack(side="left",padx=8);ttk.Button(bottom,text="Renderizar filme",command=self.run_render).pack(side="left")
        self.log=tk.Text(outer,height=11,bg="#0d0911",fg="#f0eaf4",insertbackground="white");self.log.pack(fill="both",expand=True,pady=(10,0))

    def _row(self,parent,row,label,var,button=None,button_text="Selecionar",width=76):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky="w",padx=10,pady=8);ttk.Entry(parent,textvariable=var,width=width).grid(row=row,column=1,sticky="ew",padx=10,pady=8)
        if button:ttk.Button(parent,text=button_text,command=button).grid(row=row,column=2,padx=10,pady=8)

    def _slider(self,f,row,label,var,from_=0,to=1):
        ttk.Label(f,text=label).grid(row=row,column=0,sticky="w",padx=10,pady=8);ttk.Scale(f,from_=from_,to=to,variable=var,orient="horizontal",length=500).grid(row=row,column=1,sticky="w",padx=10,pady=8);ttk.Label(f,textvariable=var,width=8).grid(row=row,column=2,sticky="w")

    def _build_project(self,f):
        self._row(f,0,"Áudio",self.audio,self.pick_audio);self._row(f,1,"Saída",self.output,self.pick_output,"Salvar como");self._row(f,2,"Letra/legenda (opcional)",self.lyrics,self.pick_lyrics)
        mf=ttk.Frame(f);mf.grid(row=3,column=0,columnspan=3,sticky="ew",padx=10,pady=8);ttk.Button(mf,text="Adicionar imagens/vídeos de cenário",command=self.pick_media).pack(side="left");ttk.Button(mf,text="Limpar cenários",command=self.clear_media).pack(side="left",padx=8);self.media_label=ttk.Label(mf,text="Nenhuma mídia de cenário");self.media_label.pack(side="left",padx=10)
        ttk.Label(f,text="As imagens da aba Personagens tornam-se atores do filme. As mídias desta aba entram em telas, hologramas e cenários.",wraplength=930).grid(row=4,column=0,columnspan=3,sticky="w",padx=10,pady=8);f.columnconfigure(1,weight=1)

    def _build_characters(self,f):
        form=ttk.LabelFrame(f,text="Adicionar personagem");form.pack(fill="x",padx=10,pady=10)
        ttk.Label(form,text="Papel").grid(row=0,column=0,padx=8,pady=8);ttk.Combobox(form,textvariable=self.character_role,values=CHARACTER_ROLES,state="readonly",width=18).grid(row=0,column=1,padx=8,pady=8)
        ttk.Label(form,text="Movimento").grid(row=0,column=2,padx=8,pady=8);ttk.Combobox(form,textvariable=self.character_motion,values=MOTION_CHOICES,state="readonly",width=18).grid(row=0,column=3,padx=8,pady=8)
        ttk.Label(form,text="Nome").grid(row=0,column=4,padx=8,pady=8);ttk.Entry(form,textvariable=self.character_name,width=22).grid(row=0,column=5,padx=8,pady=8);ttk.Button(form,text="Escolher imagem e adicionar",command=self.add_character).grid(row=0,column=6,padx=8,pady=8)
        self.char_tree=ttk.Treeview(f,columns=("name","role","motion","path"),show="headings",height=12)
        for col,label,width in [("name","Nome",160),("role","Papel",130),("motion","Movimento",150),("path","Arquivo",620)]:self.char_tree.heading(col,text=label);self.char_tree.column(col,width=width,anchor="w")
        self.char_tree.pack(fill="both",expand=True,padx=10,pady=6);bf=ttk.Frame(f);bf.pack(fill="x",padx=10,pady=6);ttk.Button(bf,text="Testar recorte + rig",command=self.preview_character_cutout).pack(side="left");ttk.Button(bf,text="Remover selecionado",command=self.remove_character).pack(side="left",padx=8);ttk.Button(bf,text="Limpar personagens",command=self.clear_characters).pack(side="left")
        ttk.Label(f,text="A Fase 0.2 salva PNG transparente e arquivo .rig.json. PNG transparente continua oferecendo o melhor resultado.",wraplength=950).pack(anchor="w",padx=10,pady=8)

    def _build_world(self,f):
        ttk.Label(f,text="Modelo de mundo").grid(row=0,column=0,sticky="w",padx=10,pady=10);ttk.Combobox(f,textvariable=self.world,values=WORLD_CHOICES,state="readonly",width=30).grid(row=0,column=1,sticky="w",padx=10,pady=10)
        text=("neon_graphic_grit: tinta, preto, vermelho, magenta, multidão e montagem agressiva.\n\nfuture_noir_cel: cel shading angular, violeta, azul, terraços, clubes e skylines.\n\nhybrid_cyberpunk: alterna os mundos.\n\nauto_director: escolhe por energia e função musical.")
        ttk.Label(f,text=text,wraplength=900,justify="left").grid(row=1,column=0,columnspan=3,sticky="w",padx=10,pady=12);ttk.Label(f,text="Extração do personagem").grid(row=2,column=0,sticky="w",padx=10,pady=8);ttk.Combobox(f,textvariable=self.subject_extraction,values=["auto","none"],state="readonly",width=20).grid(row=2,column=1,sticky="w",padx=10,pady=8);ttk.Checkbutton(f,text="Preservar identidade visual da referência",variable=self.preserve_identity).grid(row=3,column=1,sticky="w",padx=10,pady=8)

    def _build_animation(self,f):
        self._slider(f,0,"Força da atuação principal",self.motion_strength);self._slider(f,1,"Movimento secundário (cabelo/roupa)",self.secondary_motion);self._slider(f,2,"Sincronia labial gráfica",self.lip_sync);self._slider(f,3,"Rastros de ação",self.action_trails);self._slider(f,4,"Continuidade entre planos",self.continuity_strength);self._slider(f,5,"Suavização da câmera",self.camera_smoothing);self._slider(f,6,"Escala dos personagens",self.character_scale,.4,1.15);self._slider(f,7,"Contorno gráfico",self.character_outline)
        ttk.Label(f,text="A continuidade mantém lado de tela, direção do olhar, profundidade e posição aproximada dos personagens de um plano para o seguinte.",wraplength=930).grid(row=8,column=0,columnspan=3,sticky="w",padx=10,pady=14)

    def _build_visual(self,f):
        ttk.Label(f,text="Filtro de pós-produção").grid(row=0,column=0,sticky="w",padx=10,pady=8);ttk.Combobox(f,textvariable=self.filter_name,values=FILTER_NAMES,state="readonly",width=32).grid(row=0,column=1,sticky="w",padx=10,pady=8)
        self._slider(f,1,"Intensidade do filtro",self.filter_intensity);self._slider(f,2,"Densidade de montagem",self.edit_density);self._slider(f,3,"Densidade de multidão",self.crowd_density);self._slider(f,4,"Movimento do cenário",self.background_motion);self._slider(f,5,"Flashes / strobe seguro",self.strobe,0,.30)
        ttk.Checkbutton(f,text="Usar tipografia, letra e frases procedurais",variable=self.typography).grid(row=6,column=1,sticky="w",padx=10,pady=8);ttk.Label(f,text="Seed").grid(row=7,column=0,sticky="w",padx=10,pady=8);sf=ttk.Frame(f);sf.grid(row=7,column=1,sticky="w",padx=10,pady=8);ttk.Entry(sf,textvariable=self.seed,width=20).pack(side="left");ttk.Button(sf,text="Nova história",command=lambda:self.seed.set(str(random.randint(1,2_147_483_647)))).pack(side="left",padx=8)

    def _build_i2v(self,f):
        ttk.Label(f,text="Modo da ponte local").grid(row=0,column=0,sticky="w",padx=10,pady=10);ttk.Combobox(f,textvariable=self.i2v_mode,values=I2V_MODES,state="readonly",width=24).grid(row=0,column=1,sticky="w",padx=10,pady=10)
        self._row(f,1,"Pasta para pacotes/keyframes",self.i2v_package_dir,self.pick_i2v_package,"Escolher pasta",58);self._row(f,2,"Pasta de clipes gerados",self.i2v_clips_dir,self.pick_i2v_clips,"Escolher pasta",58);self._slider(f,3,"Mistura do clipe I2V",self.i2v_strength)
        text=("off: render 2.5D normal.\npackage: exporta um keyframe e JSON para cada plano.\nclips: substitui/mistura clipes locais chamados shot_0000.mp4, shot_0001.mp4 etc.\npackage_and_clips: exporta os pacotes e também usa clipes já existentes.\n\nNenhuma API paga é usada e nenhum modelo pesado é obrigatório. Os clipes podem ser produzidos em qualquer aplicação local de image-to-video.")
        ttk.Label(f,text=text,wraplength=930,justify="left").grid(row=4,column=0,columnspan=3,sticky="w",padx=10,pady=14);f.columnconfigure(1,weight=1)

    def _build_export(self,f):
        ttk.Label(f,text="Preset de resolução").grid(row=0,column=0,sticky="w",padx=10,pady=8);combo=ttk.Combobox(f,textvariable=self.resolution,values=[*RESOLUTION_PRESETS,"personalizada"],state="readonly",width=24);combo.grid(row=0,column=1,sticky="w",padx=10,pady=8);combo.bind("<<ComboboxSelected>>",self.apply_resolution)
        ttk.Label(f,text="Largura digitável").grid(row=1,column=0,sticky="w",padx=10,pady=8);ttk.Entry(f,textvariable=self.width,width=14).grid(row=1,column=1,sticky="w",padx=10,pady=8);ttk.Label(f,text="Altura digitável").grid(row=2,column=0,sticky="w",padx=10,pady=8);ttk.Entry(f,textvariable=self.height,width=14).grid(row=2,column=1,sticky="w",padx=10,pady=8)
        ttk.Label(f,text="FPS").grid(row=3,column=0,sticky="w",padx=10,pady=8);ttk.Combobox(f,textvariable=self.fps,values=["24","25","30","50","60"],width=12).grid(row=3,column=1,sticky="w",padx=10,pady=8);ttk.Label(f,text="Escala interna").grid(row=4,column=0,sticky="w",padx=10,pady=8);ttk.Combobox(f,textvariable=self.render_scale,values=["0.35","0.5","0.65","0.75","0.85","1.0"],width=12).grid(row=4,column=1,sticky="w",padx=10,pady=8)
        ttk.Label(f,text="Encoder").grid(row=5,column=0,sticky="w",padx=10,pady=8);ttk.Combobox(f,textvariable=self.encoder,values=["auto","h264_nvenc","hevc_nvenc","libx264","libx265"],state="readonly",width=20).grid(row=5,column=1,sticky="w",padx=10,pady=8);ttk.Label(f,text="Tratamento do áudio").grid(row=6,column=0,sticky="w",padx=10,pady=8);ttk.Combobox(f,textvariable=self.audio_mode,values=["preserve","streaming","cinema","club","normalize"],state="readonly",width=20).grid(row=6,column=1,sticky="w",padx=10,pady=8)
        ttk.Label(f,text="Limite opcional de prévia (s)").grid(row=7,column=0,sticky="w",padx=10,pady=8);ttk.Entry(f,textvariable=self.preview_seconds,width=14).grid(row=7,column=1,sticky="w",padx=10,pady=8);ttk.Label(f,text="RTX 4060 8 GB: 1080p em 0.75; 2K em 0.65–0.75; 4K em 0.5. Largura e altura continuam livres.",wraplength=900).grid(row=8,column=0,columnspan=3,sticky="w",padx=10,pady=12)

    def apply_resolution(self,event=None):
        if self.resolution.get() in RESOLUTION_PRESETS:w,h=RESOLUTION_PRESETS[self.resolution.get()];self.width.set(str(w));self.height.set(str(h))
    def pick_audio(self):
        p=filedialog.askopenfilename(filetypes=[("Áudio","*.wav *.flac *.mp3 *.m4a *.aac *.ogg"),("Todos","*.*")]);self.audio.set(p or self.audio.get())
    def pick_output(self):
        p=filedialog.asksaveasfilename(defaultextension=".mp4",filetypes=[("MP4","*.mp4"),("MKV","*.mkv"),("AVI","*.avi")]);self.output.set(p or self.output.get())
    def pick_lyrics(self):
        p=filedialog.askopenfilename(filetypes=[("Letra/legenda","*.srt *.vtt *.lrc *.txt"),("Todos","*.*")]);self.lyrics.set(p or self.lyrics.get())
    def pick_media(self):
        files=filedialog.askopenfilenames(filetypes=[("Mídia","*.jpg *.jpeg *.png *.webp *.mp4 *.mov *.mkv *.avi *.webm"),("Todos","*.*")]);
        if files:self.media=list(files);self.media_label.config(text=f"{len(self.media)} arquivo(s)")
    def clear_media(self):self.media=[];self.media_label.config(text="Nenhuma mídia de cenário")
    def pick_i2v_package(self):
        p=filedialog.askdirectory();self.i2v_package_dir.set(p or self.i2v_package_dir.get())
    def pick_i2v_clips(self):
        p=filedialog.askdirectory();self.i2v_clips_dir.set(p or self.i2v_clips_dir.get())

    def add_character(self):
        path=filedialog.askopenfilename(filetypes=[("Imagem de personagem","*.png *.jpg *.jpeg *.webp *.bmp"),("Todos","*.*")])
        if not path:return
        name=self.character_name.get().strip() or Path(path).stem;item={"path":path,"name":name,"role":self.character_role.get(),"motion":self.character_motion.get()};self.characters.append(item);self.char_tree.insert("","end",values=(name,item["role"],item["motion"],path));self.character_name.set("")
    def remove_character(self):
        selected=self.char_tree.selection();indices=sorted([self.char_tree.index(i) for i in selected],reverse=True)
        for idx in indices:del self.characters[idx]
        for item in selected:self.char_tree.delete(item)
    def clear_characters(self):
        self.characters=[]
        for item in self.char_tree.get_children():self.char_tree.delete(item)

    def preview_character_cutout(self):
        selected=self.char_tree.selection()
        if not selected:messagebox.showinfo("SUBTERRA-CYBERPUNK","Selecione um personagem na tabela.");return
        idx=self.char_tree.index(selected[0]);c=self.characters[idx];out=ROOT/"output"/"character_previews"/(Path(c["path"]).stem+"_cutout.png");out.parent.mkdir(parents=True,exist_ok=True);raw=f"{c['path']}::{c['role']}::{c['motion']}::{c['name']}";self._run([sys.executable,"cyberpunk.py","prepare-character",raw,str(out),"--extraction",self.subject_extraction.get()])

    def _run(self,cmd:list[str]):
        self.log.delete("1.0","end");self.log.insert("end","$ "+" ".join(cmd)+"\n\n")
        def worker():
            try:
                proc=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1);assert proc.stdout
                for line in proc.stdout:self.after(0,self.log.insert,"end",line);self.after(0,self.log.see,"end")
                code=proc.wait();self.after(0,lambda:messagebox.showinfo("SUBTERRA-CYBERPUNK","Concluído." if code==0 else f"Processo terminou com código {code}."))
            except Exception as exc:self.after(0,lambda:messagebox.showerror("SUBTERRA-CYBERPUNK",str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def run_diagnose(self):self._run([sys.executable,"cyberpunk.py","diagnose","--output",str(ROOT/"hardware_report.json")])

    def run_render(self,preview:int|None=None):
        if not self.audio.get():messagebox.showwarning("SUBTERRA-CYBERPUNK","Selecione um arquivo de áudio.");return
        try:
            w=int(self.width.get());h=int(self.height.get());fps=float(self.fps.get());scale=float(self.render_scale.get())
            if w<320 or h<180 or fps<=0 or not .3<=scale<=1:raise ValueError
        except ValueError:messagebox.showerror("SUBTERRA-CYBERPUNK","Revise largura, altura, FPS e escala interna.");return
        output=Path(self.output.get());output=output.with_name(output.stem+"_preview"+output.suffix) if preview else output;output.parent.mkdir(parents=True,exist_ok=True)
        cmd=[sys.executable,"cyberpunk.py","render",self.audio.get(),str(output),"--width",str(w),"--height",str(h),"--fps",str(fps),"--seed",self.seed.get(),"--world",self.world.get(),"--filter",self.filter_name.get(),"--filter-intensity",f"{self.filter_intensity.get():.3f}","--edit-density",f"{self.edit_density.get():.3f}","--motion-strength",f"{self.motion_strength.get():.3f}","--secondary-motion",f"{self.secondary_motion.get():.3f}","--lip-sync",f"{self.lip_sync.get():.3f}","--action-trails",f"{self.action_trails.get():.3f}","--continuity-strength",f"{self.continuity_strength.get():.3f}","--camera-smoothing",f"{self.camera_smoothing.get():.3f}","--character-scale",f"{self.character_scale.get():.3f}","--character-outline",f"{self.character_outline.get():.3f}","--crowd-density",f"{self.crowd_density.get():.3f}","--background-motion",f"{self.background_motion.get():.3f}","--subject-extraction",self.subject_extraction.get(),"--render-scale",str(scale),"--audio-mode",self.audio_mode.get(),"--encoder",self.encoder.get(),"--strobe",f"{self.strobe.get():.3f}","--i2v-mode",self.i2v_mode.get(),"--i2v-strength",f"{self.i2v_strength.get():.3f}"]
        if self.i2v_package_dir.get():cmd.extend(["--i2v-package-dir",self.i2v_package_dir.get()])
        if self.i2v_clips_dir.get():cmd.extend(["--i2v-clips-dir",self.i2v_clips_dir.get()])
        if not self.typography.get():cmd.append("--no-typography")
        if not self.preserve_identity.get():cmd.append("--no-preserve-identity")
        if self.lyrics.get():cmd.extend(["--lyrics",self.lyrics.get()])
        seconds=preview or (float(self.preview_seconds.get()) if self.preview_seconds.get().strip() else None)
        if seconds:cmd.extend(["--preview-seconds",str(seconds)])
        for c in self.characters:cmd.extend(["--character",f"{c['path']}::{c['role']}::{c['motion']}::{c['name']}"])
        for p in self.media:cmd.extend(["--media",p])
        self._run(cmd)


if __name__=="__main__":App().mainloop()
