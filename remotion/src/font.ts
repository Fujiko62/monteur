// Police via @font-face data-URI, SANS delayRender (qui timeout de facon aleatoire au rendu).
// font-display:block + data-URI (aucun reseau) => le texte s'affiche avec la bonne police,
// et le rendu ne peut plus echouer sur un timeout de police.
import {FONT_DATA} from './fontData';

export const CAPTION_FONT = 'CaptionFont';

export const FONT_FACE_CSS =
  `@font-face{font-family:'CaptionFont';` +
  `src:url(${FONT_DATA}) format('truetype');` +
  `font-weight:100 900;font-style:normal;font-display:block;}`;
