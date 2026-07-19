# Installer le skill MONTEUR sur un nouveau PC (Windows)

## 1. Copier le dossier
Copier le dossier `monteur/` de la clef USB ou tu veux, par exemple :
`C:\Users\<toi>\Documents\monteur\`

## 2. Prerequis (une seule fois)
- **Python 3.11+** : https://python.org (cocher "Add to PATH"), puis :
  `pip install faster-whisper google-genai requests pillow`
- **ffmpeg** : `winget install Gyan.FFmpeg` (ou https://ffmpeg.org), verifier `ffmpeg -version`
- **Node.js 18+** : https://nodejs.org, puis dans le dossier :
  `cd monteur\remotion` et `npm install`
- **(Optionnel, juge local gratuit illimite)** Ollama : https://ollama.com puis
  `ollama pull qwen2.5vl:7b`
- **(Optionnel, transcription GPU rapide)** carte NVIDIA + CUDA — sinon faster-whisper
  tourne sur CPU, juste plus lent.

## 3. Les cles API — UN SEUL fichier
Ouvrir `monteur\.env` avec le bloc-notes et remplir les cles (les 2 IA y sont) :
- `GEMINI_API_KEY` (obligatoire) — gratuite sur https://aistudio.google.com/apikey
- `DASHSCOPE_API_KEY` (secours) — gratuite sur Alibaba Model Studio (region Singapour)
Tous les scripts lisent automatiquement ce fichier. Rien d'autre a configurer.

## 4. Installer le skill dans Claude Code
Copier le fichier `monteur\SKILL.md` vers :
`C:\Users\<toi>\.claude\skills\monteur\SKILL.md`
(creer les dossiers si besoin). Il apparait alors dans le panneau Skills.

## 5. Utiliser
Dans Claude Code, ouvrir le dossier `monteur` et taper :
`/monteur "C:\chemin\vers\ma_video.mkv"`
ou simplement dire « monte cette video ».

## Notes
- Les dossiers `work/`, `livraisons/`, `out/` se remplissent tout seuls (prevoir du
  disque : ~2-5 GB par video montee). Sur un petit SSD, les deplacer sur un autre
  disque et les remplacer par des jonctions (`mklink /J`).
- Les musiques et b-roll se telechargent a la demande (rien a preinstaller).
- Canva / LM Arena pour les miniatures passent par le navigateur ou le connecteur
  MCP de Claude — se connecter une fois dans l'interface Claude.
