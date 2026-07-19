# 🎬 MONTEUR — skill Claude Code de montage vidéo autonome

Transforme Claude Code en **chef monteur autonome** (méthode theyo) : tu déposes un rush
parlé (gameplay, face-cam, vlog), tu récupères une vidéo prête à publier — coupe écrite
à la main au contenu, sous-titres mot-à-mot, effets créés par code (Remotion), bruitages
et musiques libres téléchargés à la demande, zooms ciblés sur ce qui est dit, cold-open
de rétention, shorts verticaux ≤ 20 s avec hook, miniature (Canva / LM Arena), boucle de
review par IA (Gemini → Qwen-Omni → juge local), contrôle qualité mécanique final, et
publication YouTube assistée.

## Installation

1. **Cloner** ce dépôt, puis suivre [INSTALLATION.md](INSTALLATION.md) (Python, ffmpeg,
   Node, `npm install` dans `remotion/`).
2. **Installer le skill** : copier `SKILL.md` vers `~/.claude/skills/monteur/SKILL.md`.
3. **Première utilisation** : dire `monteur` (ou déposer une vidéo) dans Claude Code
   depuis le dossier du dépôt. Le skill détecte l'installation fraîche et **te demande
   lui-même tout ce qu'il faut** (clés API avec les liens pour les obtenir gratuitement,
   vérification des dépendances) puis écrit la configuration dans `.env` — un seul
   fichier, jamais commité.

Aucune clé API n'est incluse : `.env` est ignoré par git, le modèle vide est
[`.env.exemple`](.env.exemple).

## Utilisation

```
/monteur "C:\chemin\vers\ma_video.mkv"
```
ou simplement : « monte cette vidéo ». Le résultat arrive dans
`livraisons/<nom-parlant>/` : la vidéo, `miniature.png`, et `shorts/` s'il y en a.

## Ce qu'il y a dedans

- `SKILL.md` — le cerveau : principes, pipeline en 9 étapes, pièges documentés.
- `scripts/` — la table de montage : transcription (faster-whisper), coupe, rendu,
  bruitages/musiques, miniature, shorts, juges IA, QC final (`check_delivery.py`).
- `remotion/` — le compositeur : sous-titres animés, 23+ effets génératifs paramétrables,
  zooms à point focal, incrustations, miniatures.

Rodé sur de vraies vidéos (Battlefield, R.E.P.O.) — chaque piège du fichier SKILL.md a
été payé en heures de débug réelles. 🤖 Construit avec [Claude Code](https://claude.com/claude-code).
