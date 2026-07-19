import React, {useMemo} from 'react';
import {
  AbsoluteFill,
  OffthreadVideo,
  Audio,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  random,
  Easing,
} from 'remotion';
import {Overlays} from './Overlays';
import {FONT_FACE_CSS} from './font';
import {makeDA, makeSplitLayout, splitVideoRect} from './theme';

type Word = {w: string; start: number; end: number};
// x/y (fractions 0..1 de l'ecran) = POINT FOCAL du zoom : zoomer SUR un element precis
// (compteur d'argent du HUD, objectif, item...) et pas betement au centre. Defaut: centre.
type Zoom = {start: number; end: number; scale?: number; punch?: boolean; progressive?: boolean;
             shake?: boolean; intensity?: number; x?: number; y?: number};
type Sfx = {t: number; sound: string; gain_db: number};

type Props = {
  video: string;
  fps: number;
  captions: Word[];
  zooms: Zoom[];
  sfx: Sfx[];
  overlays?: any[];
  config: any;
};

// Regroupe les mots en lignes courtes (style viral).
function buildLines(caps: Word[], maxWords: number): Word[][] {
  const lines: Word[][] = [];
  let cur: Word[] = [];
  for (let i = 0; i < caps.length; i++) {
    const w = caps[i];
    if (cur.length > 0) {
      const gap = w.start - cur[cur.length - 1].end;
      const endsSentence = /[.!?]$/.test(cur[cur.length - 1].w);
      if (cur.length >= maxWords || gap > 0.55 || endsSentence) {
        lines.push(cur);
        cur = [];
      }
    }
    cur.push(w);
  }
  if (cur.length) lines.push(cur);
  return lines;
}


export const Reel: React.FC<Props> = ({video, fps, captions, zooms, sfx, overlays = [], config}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const cap = config.captions || {};
  const mot = config.motion || {};
  const sc = config.sfx || {};

  const t = frame / fps;
  const lines = useMemo(
    () => buildLines(captions, cap.max_words_per_line || 4),
    [captions, cap.max_words_per_line]
  );

  // Zoom courant (max des cues actives). "progressive" = rampe lente et se maintient.
  // "shake": true = secousse d'impact (intensity 0..1 via z.intensity, defaut 0.5).
  let scale = 1;
  let shakeX = 0, shakeY = 0;
  // point focal du zoom dominant (celui qui donne la plus grande echelle a cet instant) ;
  // interpole doucement vers la cible pour eviter tout saut d'origine entre deux cues.
  let focalX = 0.5, focalY = 0.5;
  for (const z of zooms) {
    if (t >= z.start && t <= z.end) {
      let s;
      if (z.progressive) {
        s = interpolate(t, [z.start, z.end], [1, z.scale], {
          extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          easing: Easing.inOut(Easing.ease),
        });
      } else {
        const mid = (z.start + z.end) / 2;
        s = interpolate(t, [z.start, mid, z.end], [1, z.scale ?? 1.05, 1], {
          extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          easing: Easing.out(Easing.ease),
        });
      }
      if (s > scale && (z.x !== undefined || z.y !== undefined)) {
        // glisse du centre vers la cible au rythme du zoom (pousse camera naturelle)
        const p = interpolate(s, [1, Math.max(1.01, z.scale ?? 1.05)], [0, 1],
          {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        focalX = 0.5 + ((z.x ?? 0.5) - 0.5) * p;
        focalY = 0.5 + ((z.y ?? 0.5) - 0.5) * p;
      }
      scale = Math.max(scale, s);
      if (z.shake) {
        const decay = interpolate(t, [z.start, z.end], [1, 0],
          {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        const inten = (z.intensity ?? 0.5) * decay * width * 0.012;
        shakeX += (random(`shx${frame}`) - 0.5) * 2 * inten;
        shakeY += (random(`shy${frame}`) - 0.5) * 2 * inten;
        scale = Math.max(scale, 1 + (z.intensity ?? 0.5) * 0.02);
      }
    }
  }

  // Split-screen : progression 0..1 ANIMEE (le plan theyo "joue entre les dispositions" —
  // la video glisse en carte au lieu de sauter). Max sur tous les overlays split actifs.
  const da = makeDA(config.da);
  const lay = makeSplitLayout(config.layouts?.split, width, height);
  let splitP = 0;
  for (const o of overlays as any[]) {
    if (!o.split) continue;
    const s = o.start || 0;
    const e = s + (o.dur || 2);
    if (t < s - 0.01 || t > e + 0.01) continue;
    const T = Math.min(lay.transitionS, (e - s) / 2);
    const p = Math.min(
      interpolate(t, [s, s + T], [0, 1], {
        extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
        easing: Easing.inOut(Easing.ease),
      }),
      interpolate(t, [e - T, e], [1, 0], {
        extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
        easing: Easing.inOut(Easing.ease),
      })
    );
    splitP = Math.max(splitP, p);
  }

  // Ligne active
  const activeLine = lines.find((ln) => t >= ln[0].start - 0.08 && t <= ln[ln.length - 1].end + 0.15);

  const baseFont = (cap.font_size_ratio || 0.056) * height;
  const marginRatio = cap.safe_margin_ratio || 0.14;
  // Auto-ajustement : le mot le plus long de la ligne active doit tenir dans le cadre.
  const maxTextWidth = width * (1 - 2 * marginRatio);
  const longestChars = activeLine
    ? Math.max(...activeLine.map((w) => w.w.length), 1)
    : 1;
  const fitFont = maxTextWidth / (0.6 * longestChars);
  const fontSize = Math.min(baseFont, fitFont);
  const stroke = (cap.stroke_width_ratio || 0.006) * height;
  const margin = marginRatio * height;
  const linear = (db: number) => Math.pow(10, (db ?? -8) / 20);
  const sfxFile = (name: string) => {
    const f = (sc.set && sc.set[name]) || `${name}.wav`;
    return staticFile(`sfx/${f}`);
  };

  // Rect de la video : interpole entre plein cadre et carte split (UNE seule video montee,
  // pas de demontage/remontage au changement de disposition).
  const card = splitVideoRect(lay, width, height);
  const vx = interpolate(splitP, [0, 1], [0, card.x]);
  const vy = interpolate(splitP, [0, 1], [0, card.y]);
  const vw = interpolate(splitP, [0, 1], [width, card.w]);
  const vh = interpolate(splitP, [0, 1], [height, card.h]);
  const vr = interpolate(splitP, [0, 1], [0, width * lay.radius]);
  // le zoom d'accentuation s'attenue quand on passe en carte (il n'a de sens qu'en plein cadre)
  const effScale = 1 + (scale - 1) * (1 - splitP);

  return (
    <AbsoluteFill style={{backgroundColor: 'black'}}>
      <style>{FONT_FACE_CSS}</style>
      {splitP > 0 && <AbsoluteFill style={{background: da.bg, opacity: splitP}} />}
      <div
        style={{
          position: 'absolute', left: vx, top: vy, width: vw, height: vh,
          borderRadius: vr, overflow: 'hidden',
          boxShadow: splitP > 0.05 ? `0 30px 80px rgba(0,0,0,${0.6 * splitP})` : undefined,
        }}
      >
        <AbsoluteFill style={{
          transform: `translate(${shakeX * (1 - splitP)}px, ${shakeY * (1 - splitP)}px) scale(${effScale})`,
          transformOrigin: `${focalX * 100}% ${focalY * 100}%`,
        }}>
          <OffthreadVideo src={staticFile(video)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        </AbsoluteFill>
      </div>

      {/* Overlays : images, encarts, schemas, CTA (sous les sous-titres) */}
      {config.overlays?.enabled !== false && overlays.length > 0 && (
        <Overlays overlays={overlays} width={width} height={height} cta={config.cta || {}}
          da={da} layout={lay} />
      )}

      {/* Sous-titres */}
      {activeLine && (
        <AbsoluteFill
          style={{
            justifyContent: cap.position === 'bottom' ? 'flex-end' : 'center',
            alignItems: 'center',
            padding: margin,
            paddingBottom: cap.position === 'bottom' ? margin : undefined,
          }}
        >
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'center',
              gap: `${fontSize * 0.18}px`,
              maxWidth: '90%',
            }}
          >
            {activeLine.map((w, i) => {
              const isActive = t >= w.start - 0.02 && t <= w.end + 0.05;
              const appeared = t >= w.start - 0.02;
              const pop = isActive
                ? (interpolate(t, [w.start - 0.02, w.start + 0.08],
                    [Number(cap.pop_scale) || 1.14, 1], {
                    extrapolateLeft: 'clamp',
                    extrapolateRight: 'clamp',
                  }) as number)
                : 1;
              const boxed = isActive && cap.highlight_mode === 'box';
              // mode "glow" (style clean, ref. shorts pro) : mot actif blanc lumineux,
              // halo sombre doux au lieu du contour dur, pas de boite jaune.
              const glow = cap.highlight_mode === 'glow';
              return (
                <span
                  key={i}
                  style={{
                    fontFamily: 'CaptionFont, ' + (cap.font_family || 'sans-serif'),
                    fontWeight: cap.font_weight || 800,
                    fontSize,
                    lineHeight: 1.05,
                    textTransform: cap.uppercase ? 'uppercase' : 'none',
                    color: glow
                      ? (cap.text_color || da.text)
                      : boxed ? '#111' : isActive ? cap.highlight_color || da.accent : cap.text_color || da.text,
                    background: boxed ? cap.highlight_color || da.accent : 'transparent',
                    padding: boxed ? `0 ${fontSize * 0.12}px` : undefined,
                    borderRadius: boxed ? fontSize * 0.14 : undefined,
                    WebkitTextStroke: glow || boxed ? undefined : `${stroke}px ${cap.stroke_color || '#000'}`,
                    paintOrder: 'stroke fill',
                    textShadow: glow
                      ? `0 2px ${fontSize * 0.3}px rgba(0,0,0,0.95), 0 0 ${fontSize * 0.7}px rgba(0,0,0,0.75)` +
                        (isActive ? `, 0 0 ${fontSize * 0.5}px ${cap.highlight_color || 'rgba(255,255,255,0.55)'}` : '')
                      : cap.shadow ? `0 ${fontSize * 0.04}px ${fontSize * 0.08}px rgba(0,0,0,0.55)` : undefined,
                    transform: `scale(${glow && isActive ? Math.max(pop, 1.06) : pop})`,
                    opacity: appeared ? 1 : glow ? 0.85 : 0.5,
                    transformOrigin: 'center bottom',
                    display: 'inline-block',
                    whiteSpace: 'nowrap',
                    transition: 'none',
                  }}
                >
                  {w.w}
                </span>
              );
            })}
          </div>
        </AbsoluteFill>
      )}

      {/* Bruitages */}
      {sc.enabled &&
        sfx.map((s, i) => (
          <Sequence key={i} from={Math.max(0, Math.round(s.t * fps))} durationInFrames={Math.round(2 * fps)}>
            <Audio src={sfxFile(s.sound)} volume={linear(s.gain_db)} />
          </Sequence>
        ))}
    </AbsoluteFill>
  );
};
