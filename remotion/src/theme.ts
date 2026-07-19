// DESIGN SYSTEM central (etape "LA PATTE" du plan theyo) : UNE identite visuelle,
// definie dans config.json section "da", consommee par TOUS les composants.
// Chaque item d'overlay peut toujours surcharger ponctuellement via son propre champ
// (item.color, item.bg...), mais le DEFAUT vient d'ici — plus aucun hex en dur eparpille.

export type DA = {
  accent: string;      // LA couleur identitaire (mot actif, barres, aretes, chiffres)
  text: string;        // texte principal
  muted: string;       // texte secondaire
  bg: string;          // fond plein cadre (split-screen, overlay "bg" dark)
  surface: string;     // fond des cartes/panneaux/nodes
  border: string;      // bordures discretes
  backgrounds: Record<string, string>; // fonds nommes reutilisables ("un fond noir, un fond blanc")
};

export const makeDA = (da: any = {}): DA => ({
  accent: da.accent ?? '#FFE500',
  text: da.text ?? '#FFFFFF',
  muted: da.muted ?? 'rgba(255,255,255,0.75)',
  bg: da.bg ?? '#0b0b12',
  surface: da.surface ?? '#1b1e28',
  border: da.border ?? 'rgba(255,255,255,0.15)',
  backgrounds: {dark: da.bg ?? '#0b0b12', light: '#F5F5F2', ...(da.backgrounds ?? {})},
});

// Geometrie du layout split ("moi + animation"), configurable via config.json "layouts".
export type SplitLayout = {
  videoPos: 'left' | 'right' | 'top';
  videoW: number;   // fraction largeur (left/right) ou fraction hauteur si top
  videoH: number;
  margin: number;   // marge en fraction du plus petit cote
  radius: number;   // rayon de carte en fraction largeur
  transitionS: number; // duree de la transition animee plein cadre <-> split
};

export const makeSplitLayout = (lay: any = {}, width = 16, height = 9): SplitLayout => {
  const vertical = height > width;
  const pos = lay.video_pos && lay.video_pos !== 'auto'
    ? lay.video_pos
    : vertical ? 'top' : 'left'; // 9:16 : empiler (une carte gauche rendrait la face-cam minuscule)
  return {
    videoPos: pos,
    videoW: lay.video_w ?? (pos === 'top' ? 0.9 : 0.46),
    videoH: lay.video_h ?? (pos === 'top' ? 0.42 : 0.62),
    margin: lay.margin ?? 0.05,
    radius: lay.radius ?? 0.02,
    transitionS: lay.transition_s ?? 0.4,
  };
};

// Rect de la carte video en mode split (pixels).
export const splitVideoRect = (l: SplitLayout, width: number, height: number) => {
  if (l.videoPos === 'top') {
    const w = width * l.videoW;
    const h = height * l.videoH;
    return {x: (width - w) / 2, y: height * l.margin, w, h};
  }
  const w = width * l.videoW;
  const h = height * l.videoH;
  const x = l.videoPos === 'right' ? width * (1 - l.margin) - w : width * l.margin;
  return {x, y: (height - h) / 2, w, h};
};
