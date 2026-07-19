import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {FONT_FACE_CSS} from './font';

/**
 * Miniature YouTube 1280x720 : image plein cadre traitee + GROS titre lisible.
 * props:
 *  image: fichier dans public/media/  |  title: "..."  (mots en *etoiles* = accent)
 *  accent: couleur (defaut jaune) | emoji: sticker optionnel | badge: petit texte haut-droite
 *  zoom: 1.0-1.6 recadrage dans l'image | offsetX/offsetY: recentrage (-1..1)
 *  circle: {x,y,r} cercle rouge optionnel (0..1 normalises)
 */
export const Thumbnail: React.FC<any> = ({
  image, title = '', accent = '#FFE500', emoji, badge, zoom = 1.08,
  offsetX = 0, offsetY = 0, circle, darken = 0.25,
}) => {
  const W = 1280, H = 720;
  // *mot* -> accent
  const parts = String(title).split(/(\*[^*]+\*)/g).filter(Boolean);
  const words = parts.map((p) =>
    p.startsWith('*') ? {t: p.slice(1, -1), accent: true} : {t: p, accent: false});

  return (
    <AbsoluteFill style={{background: '#000'}}>
      <style>{FONT_FACE_CSS}</style>
      <AbsoluteFill style={{
        transform: `scale(${zoom}) translate(${offsetX * 8}%, ${offsetY * 8}%)`,
      }}>
        <Img src={staticFile(`media/${image}`)}
             style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      </AbsoluteFill>

      {/* traitement : vignette + degrade bas pour la lisibilite du titre */}
      <AbsoluteFill style={{
        background: `radial-gradient(ellipse at 50% 35%, transparent 45%, rgba(0,0,0,${darken + 0.25}) 100%),` +
                    `linear-gradient(to top, rgba(0,0,0,${darken + 0.45}) 0%, transparent 45%)`,
      }} />

      {/* cercle rouge optionnel (pointer un detail) */}
      {circle ? (
        <div style={{
          position: 'absolute',
          left: circle.x * W - circle.r * W, top: circle.y * H - circle.r * W,
          width: circle.r * W * 2, height: circle.r * W * 2,
          border: `${W * 0.008}px solid #FF2D2D`, borderRadius: '50%',
          boxShadow: '0 0 30px rgba(255,45,45,0.8), inset 0 0 20px rgba(255,45,45,0.4)',
        }} />
      ) : null}

      {/* badge haut-droite */}
      {badge ? (
        <div style={{
          position: 'absolute', top: H * 0.05, right: W * 0.04,
          background: '#FF2D2D', color: '#fff', fontFamily: 'CaptionFont, sans-serif',
          fontWeight: 800, fontSize: H * 0.065, padding: `${H * 0.012}px ${W * 0.018}px`,
          borderRadius: 14, transform: 'rotate(3deg)',
          boxShadow: '0 10px 30px rgba(0,0,0,0.6)', textTransform: 'uppercase',
        }}>{badge}</div>
      ) : null}

      {/* emoji sticker */}
      {emoji ? (
        <div style={{
          position: 'absolute', right: W * 0.055, bottom: H * 0.30,
          fontSize: H * 0.24, transform: 'rotate(-8deg)',
          filter: 'drop-shadow(0 12px 24px rgba(0,0,0,0.7))',
        }}>{emoji}</div>
      ) : null}

      {/* TITRE bas-gauche, enorme, contour noir epais */}
      <div style={{
        position: 'absolute', left: W * 0.045, bottom: H * 0.055, width: W * 0.9,
        fontFamily: 'CaptionFont, sans-serif', fontWeight: 800,
        fontSize: H * 0.155, lineHeight: 1.02, textTransform: 'uppercase',
        color: '#fff',
        WebkitTextStroke: `${H * 0.012}px #000`,
        paintOrder: 'stroke fill',
        textShadow: '0 10px 34px rgba(0,0,0,0.85)',
        letterSpacing: -1,
      }}>
        {words.map((w, i) => (
          <span key={i} style={{color: w.accent ? accent : '#fff'}}>{w.t}</span>
        ))}
      </div>
    </AbsoluteFill>
  );
};
