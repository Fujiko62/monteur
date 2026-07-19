# Blueprint du montage automatisé (méthode theyo, distillée)

Source : vidéo "J'ai automatisé 97% du montage vidéo avec Claude" (theyo, 2026).
Ceci est la **théorie de référence** pour le Claude monteur. Objectif : rendu quasi
parfait, pas un rendu "80% générique".

## Philosophie
- Économie du "80%" : mieux vaut 10 vidéos à 80% qu'une à 100%. Mais 80% ici = déjà
  très bon, pas bâclé. On vise le quasi-parfait de façon reproductible.
- Le rendu générique (cuts à côté de la plaque, b-roll stock vus 1000 fois) est l'ennemi.
  Chaque choix (cut, zoom, animation, b-roll, son) doit être **justifié par le sens**.

## Étape 1 — Transcription qui GARDE les ratés (la plus incomprise)
Les outils de transcription classiques NETTOIENT (enlèvent silences, hésitations, ratés).
Pour le montage c'est l'INVERSE de ce qu'on veut : on a besoin des silences et ratés
**time-codés** pour couper précisément.
- Modèle qualité mots : ElevenLabs **Scribe v2** (comprend bien les noms propres type
  "Anthropic"). Important pour les sous-titres. (Implémenté : optionnel via
  ELEVENLABS_API_KEY, orthographe Scribe fusionnée sur les timings whisper.)
- Timing mot-à-mot + silences/erreurs conservés : **WhisperX** (ici : faster-whisper local
  sur GPU, word_timestamps, VAD désactivée pour garder les blancs).
- + un **détecteur de silence** (implémenté : ffmpeg silencedetect -> words.json["silences"] ;
  un gap whisper n'est coupé QUE s'il recouvre un vrai silence audio, bornes snappées).
- Calibrer l'agressivité : cut dès la fin du mot (agressif) vs. laisser respirer (naturel).
- Difficulté centrale : distinguer les silences à GARDER (rythme, respiration voulue) des
  silences à RETIRER (blancs, hésitations).

## Étape 2 — Montage animé (Remotion / HyperFrame + FFMPEG)
- **Remotion** : du code (React/HTML) → animations Motion Design. Transitions, layouts
  (moi seul / moi + animation), rendu vidéo programmatique.
- **FFMPEG** : coupe/concat/recadrage/couleur programmatiques, sans logiciel de montage.
- Règles d'or (le savoir-faire qui manque à la plupart) :
  - **Zoom sur les mots d'accentuation** (punchlines, chiffres, noms de marque). PAS de zoom
    sur les phrases neutres ("typiquement cette phrase, ça sert à rien" → pas de zoom).
  - **Animation quand ça illustre** : si je dis "Claude", montrer une animation/logo Claude.
    Si la phrase n'appelle rien de visuel, ne rien mettre.
  - Timing, layouts, animations = définis dans le skill (direction artistique claire).

## Étape 3 — B-roll (par ordre de qualité)
1. Simple : **Pexels** (API) — images/vidéos stock. Vite générique, à doser.
2. Mieux : générer images/vidéos avec IA (bon pour le storytelling).
3. Préféré de theyo : **MCP YouTube** — extraits d'illustration, transcript time-codé pour
   couper au bon moment. (Attention droits d'auteur.)
4. **Playwright / navigateur** : screenshots de pages web/articles.
5. **ClipCafé** : extraits de films.

## Étape 4 — Ta patte (Direction Artistique)
- Définir un **univers de montage** cohérent avec ton identité (theyo = sombre, violet, tech).
- Concevoir un **design system** (avec Claude/Claude Design) : couleurs, fonds, **polices**
  (crucial en vertical où du texte s'affiche à chaque seconde), tes propres b-roll.
- C'est ce qui différencie ton montage de celui des autres.

## Étape 5 — LES YEUX (phase centrale, peu comprise)
- Claude peut choper une frame précise mais n'a PAS la compréhension globale de la vidéo.
- **Gemini** a la compréhension vidéo globale → il analyse le rendu et fait des feedbacks
  directs à Claude, en **boucle continue** → montage ultra quali auto-corrigé.
- Intégrer Gemini dans le skill : dès qu'un rendu est prêt, l'envoyer à Gemini, recevoir le
  feedback, réappliquer. (Fallback ici : Claude échantillonne des frames + relit le rendu.)

## Étape 6 — Vérification (2 niveaux)
1. **Gemini** avec un rôle **prépondérant/décisionnel** (bien dire à Claude que le feedback
   Gemini prime, sinon Claude ignore et continue sa direction).
2. **Toi** à la fin (ça reste de l'IA, 97% pas 100%). S'améliore vidéo après vidéo.

## Étape 7 — Le son / bruitages
- **Epidemic Sound** (via MCP) : musiques + **sound effects** libres de droit, placés au bon
  moment. (Ici : pack SFX CC0 local + placement auto.)
- Piège : utiliser des SFX **coupés net au début/fin** (sinon un silence en tête décale le
  son sur la timeline). Normaliser/trimmer les SFX.

## Résumé pipeline
rush → transcription (garde ratés) → plan de coupe agressif → coupe+couleur (ffmpeg) →
captions mot-à-mot + zooms + animations + b-roll (Remotion) → bruitages placés →
review Gemini/Claude en boucle → vérif humaine → export prêt à poster.
