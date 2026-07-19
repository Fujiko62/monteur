import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, random, Easing} from 'remotion';

/**
 * BIBLIOTHEQUE D'EFFETS VISUELS generatifs — TOUT est parametrable via `params`.
 * Utilisation dans overlays.json :
 *   {"type":"fx","name":"rain","start":10,"dur":4,"params":{"count":200,"angle":18,...}}
 * Chaque effet liste ses parametres et defauts ci-dessous. Aucune valeur en dur
 * n'est imposee : params ecrase tout.
 */

const ease = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

function useLife(durF: number, inF: number, outF: number) {
  const f = useCurrentFrame();
  return Math.min(
    interpolate(f, [0, inF], [0, 1], ease),
    interpolate(f, [durF - outF, durF], [1, 0], ease)
  );
}

// ---------- PLUIE (moments tristes) ----------
// params: count(180) speed(1.0) angle(12deg) opacity(0.55) color(#bcd4ff) width(2.2)
//         length(0.05 = fraction hauteur) blur(0.6) fadeIn/fadeOut frames(12)
const Rain: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const life = useLife(durF, p.fadeIn ?? 12, p.fadeOut ?? 12);
  const n = p.count ?? 180;
  const ang = ((p.angle ?? 12) * Math.PI) / 180;
  const drops = Array.from({length: n}, (_, i) => {
    const seedX = random(`rx${i}`);
    const speed = (p.speed ?? 1.0) * (0.7 + random(`rs${i}`) * 0.6);
    const phase = random(`rp${i}`);
    const prog = ((f / fps) * speed * 0.9 + phase) % 1;
    const x = (seedX + prog * Math.tan(ang) * 0.3) % 1;
    return {x: x * width, y: prog * (height + 200) - 100,
            l: (p.length ?? 0.05) * height * (0.6 + random(`rl${i}`) * 0.8),
            o: 0.3 + random(`ro${i}`) * 0.7};
  });
  return (
    <AbsoluteFill style={{opacity: life * (p.opacity ?? 0.55), filter: `blur(${p.blur ?? 0.6}px)`}}>
      <svg width={width} height={height}>
        {drops.map((d, i) => (
          <line key={i} x1={d.x} y1={d.y} x2={d.x - Math.tan(ang) * d.l} y2={d.y + d.l}
                stroke={p.color ?? '#bcd4ff'} strokeWidth={p.width ?? 2.2} opacity={d.o}
                strokeLinecap="round" />
        ))}
      </svg>
    </AbsoluteFill>
  );
};

// ---------- NEIGE ----------
// params: count(120) speed(0.35) size(6) opacity(0.8) drift(0.15) color(#fff)
const Snow: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const life = useLife(durF, p.fadeIn ?? 15, p.fadeOut ?? 15);
  const n = p.count ?? 120;
  return (
    <AbsoluteFill style={{opacity: life * (p.opacity ?? 0.8)}}>
      {Array.from({length: n}, (_, i) => {
        const sp = (p.speed ?? 0.35) * (0.5 + random(`ss${i}`));
        const prog = ((f / fps) * sp * 0.5 + random(`sp${i}`)) % 1;
        const x = (random(`sx${i}`) + Math.sin((f / fps + i) * 1.3) * (p.drift ?? 0.15) * 0.1) % 1;
        const s = (p.size ?? 6) * (0.5 + random(`sz${i}`));
        return <div key={i} style={{position: 'absolute', left: x * width, top: prog * height,
          width: s, height: s, borderRadius: '50%', background: p.color ?? '#fff',
          opacity: 0.4 + random(`so${i}`) * 0.6, filter: 'blur(0.5px)'}} />;
      })}
    </AbsoluteFill>
  );
};

// ---------- CONFETTIS (win / celebration) ----------
// params: count(140) speed(0.5) size(12) colors([...]) spin(2) opacity(1)
const Confetti: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const life = useLife(durF, p.fadeIn ?? 6, p.fadeOut ?? 15);
  const colors = p.colors ?? ['#FFE500', '#FF2D55', '#00E5FF', '#7CFF4F', '#B26BFF', '#FF9F1C'];
  const n = p.count ?? 140;
  return (
    <AbsoluteFill style={{opacity: life * (p.opacity ?? 1)}}>
      {Array.from({length: n}, (_, i) => {
        const sp = (p.speed ?? 0.5) * (0.6 + random(`cs${i}`) * 0.8);
        const prog = ((f / fps) * sp * 0.6 + random(`cp${i}`)) % 1.1;
        const x = random(`cx${i}`) + Math.sin((prog * 6 + i) * 1.7) * 0.04;
        const s = (p.size ?? 12) * (0.5 + random(`cz${i}`));
        const rot = (f * (p.spin ?? 2) * (2 + random(`cr${i}`) * 4)) % 360;
        return <div key={i} style={{position: 'absolute', left: x * width, top: prog * height - 60,
          width: s, height: s * 0.45, background: colors[i % colors.length],
          transform: `rotate(${rot}deg)`, borderRadius: 2}} />;
      })}
    </AbsoluteFill>
  );
};

// ---------- ETINCELLES / braises qui montent ----------
// params: count(60) speed(0.4) size(5) color(#ffb347) opacity(0.9)
const Sparks: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const life = useLife(durF, p.fadeIn ?? 10, p.fadeOut ?? 12);
  return (
    <AbsoluteFill style={{opacity: life * (p.opacity ?? 0.9)}}>
      {Array.from({length: p.count ?? 60}, (_, i) => {
        const prog = ((f / fps) * (p.speed ?? 0.4) * (0.5 + random(`ks${i}`)) + random(`kp${i}`)) % 1;
        const x = random(`kx${i}`) + Math.sin((prog * 8 + i) * 2) * 0.02;
        const s = (p.size ?? 5) * (0.4 + random(`kz${i}`)) * (1 - prog * 0.6);
        return <div key={i} style={{position: 'absolute', left: x * width, top: (1 - prog) * height,
          width: s, height: s, borderRadius: '50%', background: p.color ?? '#ffb347',
          boxShadow: `0 0 ${s * 2}px ${p.color ?? '#ffb347'}`, opacity: 1 - prog}} />;
      })}
    </AbsoluteFill>
  );
};

// ---------- FLASH (transition punch) ----------
// params: color(#fff) strength(0.9) decay(8 frames)
const Flash: React.FC<any> = ({p}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, p.decay ?? 8], [p.strength ?? 0.9, 0], ease);
  return <AbsoluteFill style={{background: p.color ?? '#fff', opacity: o}} />;
};

// ---------- GLITCH (bug / erreur) ----------
// params: bars(7) intensity(1) rgb(true) opacity(0.9) flicker(0.5)
const Glitch: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const life = useLife(durF, 2, 4);
  const n = p.bars ?? 7;
  const inten = (p.intensity ?? 1) * width * 0.03;
  return (
    <AbsoluteFill style={{opacity: life * (p.opacity ?? 0.9), mixBlendMode: 'screen' as any}}>
      {Array.from({length: n}, (_, i) => {
        const on = random(`gf${i}-${Math.floor(f / 2)}`) > (p.flicker ?? 0.5);
        if (!on) return null;
        const y = random(`gy${i}-${Math.floor(f / 3)}`) * height;
        const h = 4 + random(`gh${i}`) * height * 0.03;
        const dx = (random(`gx${i}-${Math.floor(f / 2)}`) - 0.5) * 2 * inten;
        return (
          <React.Fragment key={i}>
            <div style={{position: 'absolute', top: y, left: dx, width, height: h,
              background: 'rgba(255,0,60,0.35)'}} />
            {p.rgb !== false && <div style={{position: 'absolute', top: y + 2, left: -dx, width,
              height: h, background: 'rgba(0,229,255,0.35)'}} />}
          </React.Fragment>
        );
      })}
    </AbsoluteFill>
  );
};

// ---------- VIGNETTE (dramatique) ----------
// params: strength(0.7) color(#000) size(0.55)
const Vignette: React.FC<any> = ({p, durF}) => {
  const life = useLife(durF, p.fadeIn ?? 10, p.fadeOut ?? 10);
  return <AbsoluteFill style={{opacity: life * (p.strength ?? 0.7), background:
    `radial-gradient(ellipse at center, transparent ${(p.size ?? 0.55) * 100}%, ${p.color ?? '#000'} 100%)`}} />;
};

// ---------- SPEEDLINES manga (vitesse / choc) ----------
// params: count(28) color(#fff) opacity(0.5) innerRadius(0.28) width(0.012)
const Speedlines: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const life = useLife(durF, 3, 6);
  const n = p.count ?? 28;
  const cx = width / 2, cy = height / 2;
  const R = Math.hypot(cx, cy);
  return (
    <AbsoluteFill style={{opacity: life * (p.opacity ?? 0.5)}}>
      <svg width={width} height={height}>
        {Array.from({length: n}, (_, i) => {
          const a = (i / n) * Math.PI * 2 + random(`la${i}`) * 0.2 + f * 0.01;
          const r0 = R * (p.innerRadius ?? 0.28) * (1 + random(`lr${i}`) * 0.3);
          const w = (p.width ?? 0.012) * width * (0.4 + random(`lw${i}`));
          const x0 = cx + Math.cos(a) * r0, y0 = cy + Math.sin(a) * r0;
          const x1 = cx + Math.cos(a) * R, y1 = cy + Math.sin(a) * R;
          return <line key={i} x1={x0} y1={y0} x2={x1} y2={y1}
            stroke={p.color ?? '#fff'} strokeWidth={w} strokeLinecap="round" />;
        })}
      </svg>
    </AbsoluteFill>
  );
};

// ---------- SPOTLIGHT (assombrir sauf une zone) ----------
// params: x(0.5) y(0.5) r(0.22) darken(0.72) feather(0.08)
const Spotlight: React.FC<any> = ({p, durF}) => {
  const life = useLife(durF, p.fadeIn ?? 8, p.fadeOut ?? 8);
  const {width} = useVideoConfig();
  const r = (p.r ?? 0.22) * width;
  const fe = (p.feather ?? 0.08) * width;
  return <AbsoluteFill style={{opacity: life, background:
    `radial-gradient(circle at ${(p.x ?? 0.5) * 100}% ${(p.y ?? 0.5) * 100}%,` +
    `transparent ${r}px, rgba(0,0,0,${p.darken ?? 0.72}) ${r + fe}px)`}} />;
};

// ---------- CERCLE marqueur qui se dessine (entourer un element) ----------
// params: x y r(0.12) color(#FF2D2D) width(0.008) wobble(0.06) glow(true)
const Circle: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const life = useLife(durF, 1, 6);
  const draw = interpolate(f, [0, p.drawFrames ?? 14], [0, 1], {...ease, easing: Easing.out(Easing.ease)});
  const cx = (p.x ?? 0.5) * width, cy = (p.y ?? 0.5) * height;
  const r = (p.r ?? 0.12) * width;
  const C = 2 * Math.PI * r * 1.05;
  return (
    <AbsoluteFill style={{opacity: life}}>
      <svg width={width} height={height}>
        <ellipse cx={cx} cy={cy} rx={r * (1 + (p.wobble ?? 0.06))} ry={r}
          transform={`rotate(-6 ${cx} ${cy})`}
          fill="none" stroke={p.color ?? '#FF2D2D'} strokeWidth={(p.width ?? 0.008) * width}
          strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C * (1 - draw)}
          style={p.glow !== false ? {filter: `drop-shadow(0 0 ${width * 0.008}px ${p.color ?? '#FF2D2D'})`} : undefined} />
      </svg>
    </AbsoluteFill>
  );
};

// ---------- PULSE RING (attirer l'oeil : bouton s'abonner etc.) ----------
// params: x y r(0.1) color(#FF2D2D) rings(3) period(1.2s) width(0.006)
const PulseRing: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const life = useLife(durF, 6, 8);
  const rings = p.rings ?? 3;
  const period = (p.period ?? 1.2) * fps;
  return (
    <AbsoluteFill style={{opacity: life}}>
      <svg width={width} height={height}>
        {Array.from({length: rings}, (_, i) => {
          const prog = ((f + (i * period) / rings) % period) / period;
          const r = (p.r ?? 0.1) * width * (0.6 + prog * 0.9);
          return <circle key={i} cx={(p.x ?? 0.5) * width} cy={(p.y ?? 0.5) * height} r={r}
            fill="none" stroke={p.color ?? '#FF2D2D'}
            strokeWidth={(p.width ?? 0.006) * width * (1 - prog)}
            opacity={(1 - prog) * 0.9} />;
        })}
      </svg>
    </AbsoluteFill>
  );
};

// ---------- LIGHT LEAK (transition chaude cinematique) ----------
// params: color1(#ff9a3c) color2(#ff4fa0) opacity(0.5) speed(0.5)
const LightLeak: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const life = useLife(durF, 8, 12);
  const t = (f / fps) * (p.speed ?? 0.5);
  const x = 30 + Math.sin(t * 2.1) * 40;
  const y = 30 + Math.cos(t * 1.7) * 30;
  return <AbsoluteFill style={{opacity: life * (p.opacity ?? 0.5), mixBlendMode: 'screen' as any,
    background: `radial-gradient(circle at ${x}% ${y}%, ${p.color1 ?? '#ff9a3c'} 0%, transparent 40%),` +
                `radial-gradient(circle at ${100 - x}% ${100 - y}%, ${p.color2 ?? '#ff4fa0'} 0%, transparent 45%)`}} />;
};

// ---------- GRAIN cinema ----------
// params: opacity(0.12) size(140)
const Grain: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const life = useLife(durF, 5, 5);
  const shift = Math.floor(random(`gr${f}`) * 100);
  return <AbsoluteFill style={{opacity: life * (p.opacity ?? 0.12),
    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='${p.size ?? 140}' height='${p.size ?? 140}'%3E%3Cfilter id='n'%3E%3CfeTurbulence baseFrequency='0.9' seed='${shift}'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
    mixBlendMode: 'overlay' as any}} />;
};

// ---------- TITLE CARD (intro pro) ----------
// params: text, sub, accent(#FFE500), bg(rgba(0,0,0,0.55)), size(0.09)
const TitleCard: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const life = useLife(durF, 8, 10);
  const slide = interpolate(f, [0, 12], [40, 0], {...ease, easing: Easing.out(Easing.ease)});
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', opacity: life,
      background: p.bg ?? 'rgba(0,0,0,0.55)'}}>
      <div style={{transform: `translateY(${slide}px)`, textAlign: 'center',
        fontFamily: 'CaptionFont, sans-serif'}}>
        <div style={{fontSize: (p.size ?? 0.09) * height * 1.6, fontWeight: 800, color: '#fff',
          textTransform: 'uppercase', lineHeight: 1.05,
          textShadow: '0 8px 40px rgba(0,0,0,0.9)'}}>
          {String(p.text ?? '').split(/(\*[^*]+\*)/g).filter(Boolean).map((w: string, i: number) =>
            w.startsWith('*')
              ? <span key={i} style={{color: p.accent ?? '#FFE500'}}>{w.slice(1, -1)}</span>
              : <span key={i}>{w}</span>)}
        </div>
        {p.sub ? <div style={{fontSize: (p.size ?? 0.09) * height * 0.55, color: '#ffffffcc',
          marginTop: height * 0.015, fontWeight: 700}}>{p.sub}</div> : null}
      </div>
    </AbsoluteFill>
  );
};

// ---------- PLUIE D'EMOJIS (gag : reactions qui tombent) ----------
// params: emojis(["😂"]) count(24) size(0.06 fraction largeur) speed(0.8) spin(1) opacity(1)
const EmojiRain: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const life = useLife(durF, p.fadeIn ?? 8, p.fadeOut ?? 10);
  const set: string[] = p.emojis ?? ['😂'];
  const n = p.count ?? 24;
  return (
    <AbsoluteFill style={{opacity: life * (p.opacity ?? 1)}}>
      {Array.from({length: n}, (_, i) => {
        const x = random(`ex${i}`) * width;
        const speed = (p.speed ?? 0.8) * (0.6 + random(`es${i}`) * 0.8);
        const prog = ((f / fps) * speed * 0.5 + random(`ep${i}`)) % 1;
        const size = width * (p.size ?? 0.06) * (0.7 + random(`ez${i}`) * 0.6);
        const rot = (f * (p.spin ?? 1) * 3 + random(`er${i}`) * 360) % 360;
        return (
          <div key={i} style={{position: 'absolute', left: x, top: prog * (height + size * 2) - size,
            fontSize: size, transform: `rotate(${rot}deg)`}}>
            {set[i % set.length]}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// ---------- ECRAN FISSURE (gros fail / impact) ----------
// params: x(0.5) y(0.5) cracks(9) length(0.4 fraction) color(#fff) width(2.5) opacity(0.8) grow(6 frames)
const ScreenCrack: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const life = useLife(durF, 1, p.fadeOut ?? 10);
  const grow = interpolate(f, [0, p.grow ?? 6], [0, 1], ease);
  const cx = width * (p.x ?? 0.5), cy = height * (p.y ?? 0.5);
  const n = p.cracks ?? 9;
  const paths = Array.from({length: n}, (_, i) => {
    const a0 = (i / n) * Math.PI * 2 + random(`ca${i}`) * 0.8;
    const len = width * (p.length ?? 0.4) * (0.5 + random(`cl${i}`) * 0.8) * grow;
    let d = `M ${cx} ${cy}`, x = cx, y = cy, a = a0;
    for (let s = 1; s <= 4; s++) {
      a += (random(`cs${i}-${s}`) - 0.5) * 0.9;
      x += Math.cos(a) * (len / 4); y += Math.sin(a) * (len / 4);
      d += ` L ${x} ${y}`;
    }
    return d;
  });
  return (
    <AbsoluteFill style={{opacity: life * (p.opacity ?? 0.8)}}>
      <svg width={width} height={height}>
        {paths.map((d, i) => (
          <path key={i} d={d} stroke={p.color ?? '#fff'} strokeWidth={p.width ?? 2.5}
                fill="none" strokeLinecap="round" opacity={0.5 + random(`co${i}`) * 0.5} />
        ))}
        <circle cx={cx} cy={cy} r={8 * grow} fill={p.color ?? '#fff'} opacity={0.9} />
      </svg>
    </AbsoluteFill>
  );
};

// ---------- ONDE DE CHOC (explosion / drop) ----------
// params: x(0.5) y(0.5) color(#fff) rings(2) maxR(0.6 fraction largeur) width(6) speed(1)
const Shockwave: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const cx = width * (p.x ?? 0.5), cy = height * (p.y ?? 0.5);
  const n = p.rings ?? 2;
  return (
    <AbsoluteFill>
      <svg width={width} height={height}>
        {Array.from({length: n}, (_, i) => {
          const prog = Math.min(1, Math.max(0, (f / durF) * (p.speed ?? 1) - i * 0.18));
          const r = prog * width * (p.maxR ?? 0.6);
          const o = (1 - prog) * 0.85;
          return r > 1 ? <circle key={i} cx={cx} cy={cy} r={r} fill="none"
            stroke={p.color ?? '#fff'} strokeWidth={(p.width ?? 6) * (1 - prog * 0.7)} opacity={o} /> : null;
        })}
      </svg>
    </AbsoluteFill>
  );
};

// ---------- LETTERBOX CINEMA (moment dramatique / epique) ----------
// params: size(0.11 fraction hauteur) color(#000) inFrames(10) label (texte optionnel en bas)
const Letterbox: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const inn = interpolate(f, [0, p.inFrames ?? 10], [0, 1], {...ease, easing: Easing.out(Easing.cubic)});
  const out = interpolate(f, [durF - (p.outFrames ?? 10), durF], [1, 0], ease);
  const h = height * (p.size ?? 0.11) * Math.min(inn, out);
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: h, background: p.color ?? '#000'}} />
      <div style={{position: 'absolute', bottom: 0, left: 0, right: 0, height: h, background: p.color ?? '#000',
        display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        {p.label ? <span style={{color: '#fff', fontFamily: 'CaptionFont, sans-serif',
          fontWeight: 700, fontSize: h * 0.45, letterSpacing: 4, opacity: 0.85}}>{p.label}</span> : null}
      </div>
    </AbsoluteFill>
  );
};

// ---------- BATTEMENT DE COEUR (stress / clutch) ----------
// params: bpm(110) strength(0.35) color(#7a0d0d) size(0.55)
const Heartbeat: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const life = useLife(durF, p.fadeIn ?? 10, p.fadeOut ?? 12);
  const beat = ((f / fps) * ((p.bpm ?? 110) / 60)) % 1;
  const pulse = Math.pow(Math.max(0, Math.sin(beat * Math.PI)), 6);
  const s = (p.strength ?? 0.35) * pulse * life;
  return (
    <AbsoluteFill style={{
      background: `radial-gradient(ellipse at center, transparent ${(p.size ?? 0.55) * 100}%, ${p.color ?? '#7a0d0d'} 130%)`,
      opacity: s,
    }} />
  );
};

// ---------- FOCUS ZOOM RADIAL (attention brutale, style anime) ----------
// params: x(0.5) y(0.5) lines(40) color(#111) opacity(0.75) inner(0.22) len(0.5)
const FocusLines: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const life = useLife(durF, 2, p.fadeOut ?? 6);
  const cx = width * (p.x ?? 0.5), cy = height * (p.y ?? 0.5);
  const n = p.lines ?? 40;
  const R = Math.hypot(width, height) / 2;
  return (
    <AbsoluteFill style={{opacity: life * (p.opacity ?? 0.75)}}>
      <svg width={width} height={height}>
        {Array.from({length: n}, (_, i) => {
          const a = (i / n) * Math.PI * 2 + random(`fl${i}`) * 0.1 + f * 0.01;
          const r0 = R * (p.inner ?? 0.22) * (1 + random(`fr${i}`) * 0.4);
          const r1 = r0 + R * (p.len ?? 0.5) * (0.5 + random(`fL${i}`) * 0.5);
          const w = 2 + random(`fw${i}`) * 10;
          return <polygon key={i} opacity={0.5 + random(`fo${i}`) * 0.5} fill={p.color ?? '#111'}
            points={`${cx + Math.cos(a - 0.004 * w) * r1},${cy + Math.sin(a - 0.004 * w) * r1} ${cx + Math.cos(a + 0.004 * w) * r1},${cy + Math.sin(a + 0.004 * w) * r1} ${cx + Math.cos(a) * r0},${cy + Math.sin(a) * r0}`} />;
        })}
      </svg>
    </AbsoluteFill>
  );
};

// ---------- GROS CHIFFRE ANIME (style theyo "95%") ----------
// params: value("95") suffix("%") countup(true) bar(true) fill(0..1) label sous le chiffre
//         x(0.78) y(0.42) size(0.16 fraction largeur) color(#fff) accent(#8b7cf8)
//         glow(true) inFrames(14)
const BigStat: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const inn = interpolate(f, [0, p.inFrames ?? 14], [0, 1], {...ease, easing: Easing.out(Easing.cubic)});
  const out = interpolate(f, [durF - 10, durF], [1, 0], ease);
  const target = parseFloat(String(p.value ?? '95').replace(/[^\d.]/g, '')) || 0;
  const isNum = /^[\d.]+$/.test(String(p.value ?? '').trim());
  const shown = (p.countup ?? true) && isNum
    ? Math.round(target * Math.min(1, interpolate(f, [0, (p.countFrames ?? 24)], [0, 1], ease)))
    : p.value ?? '95';
  const fs = width * (p.size ?? 0.16);
  const x = width * (p.x ?? 0.78), y = height * (p.y ?? 0.42);
  const accent = p.accent ?? '#8b7cf8';
  return (
    <AbsoluteFill style={{opacity: out}}>
      <div style={{position: 'absolute', left: x, top: y, transform: `translate(-50%,-50%) scale(${0.85 + inn * 0.15})`,
        textAlign: 'center', fontFamily: 'CaptionFont, sans-serif', opacity: inn}}>
        <div style={{fontSize: fs, fontWeight: 800, color: p.color ?? '#fff', lineHeight: 1,
          textShadow: (p.glow ?? true) ? `0 0 ${fs * 0.25}px rgba(255,255,255,0.35), 0 8px 40px rgba(0,0,0,0.7)` : '0 8px 40px rgba(0,0,0,0.7)'}}>
          {shown}<span style={{fontSize: fs * 0.5, color: accent}}>{p.suffix ?? ''}</span>
        </div>
        {(p.bar ?? true) ? (
          <div style={{width: fs * 2.2, height: Math.max(4, fs * 0.05), background: 'rgba(255,255,255,0.18)',
            borderRadius: 99, margin: `${fs * 0.18}px auto 0`, overflow: 'hidden'}}>
            <div style={{width: `${Math.min(1, (p.fill ?? target / 100)) * inn * 100}%`, height: '100%',
              background: accent, borderRadius: 99, boxShadow: `0 0 12px ${accent}`}} />
          </div>
        ) : null}
        {p.label ? <div style={{fontSize: fs * 0.22, color: '#fff', opacity: 0.85, marginTop: fs * 0.12,
          fontWeight: 700, letterSpacing: 1}}>{p.label}</div> : null}
      </div>
    </AbsoluteFill>
  );
};

// ---------- PANNEAU STAT ACCENTUE (style theyo "REECRIT *50M* DE LIGNES") ----------
// params: big("50M") lines("RÉÉCRIT *50M* DE LIGNES" — *mot* = couleur accent)
//         accent(#ff3b3b) bg(rgba(10,10,14,0.92)) x(0.22) y(0.5) w(0.34) size(0.2 du panneau)
//         ticker(true : petites lignes de "code" animees en bas)
const StatPanel: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const inn = interpolate(f, [0, p.inFrames ?? 12], [0, 1], {...ease, easing: Easing.out(Easing.cubic)});
  const out = interpolate(f, [durF - 10, durF], [1, 0], ease);
  const w = width * (p.w ?? 0.34);
  const x = width * (p.x ?? 0.22), y = height * (p.y ?? 0.5);
  const accent = p.accent ?? '#ff3b3b';
  const parts = String(p.lines ?? '').split(/(\*[^*]+\*)/g).filter(Boolean);
  return (
    <AbsoluteFill style={{opacity: out * inn}}>
      <div style={{position: 'absolute', left: x, top: y, width: w,
        transform: `translate(-50%,-50%) translateY(${(1 - inn) * 30}px)`,
        background: p.bg ?? 'rgba(10,10,14,0.92)', borderRadius: w * 0.05,
        border: '1px solid rgba(255,255,255,0.12)', boxShadow: '0 24px 70px rgba(0,0,0,0.6)',
        padding: `${w * 0.09}px ${w * 0.08}px`, textAlign: 'center',
        fontFamily: 'CaptionFont, sans-serif'}}>
        {p.big ? <div style={{fontSize: w * (p.size ?? 0.2), fontWeight: 800, color: '#fff', lineHeight: 1.05,
          textShadow: '0 6px 30px rgba(0,0,0,0.8)'}}>{p.big}</div> : null}
        {parts.length ? <div style={{fontSize: w * 0.055, fontWeight: 800, color: '#fff',
          marginTop: w * 0.05, letterSpacing: 1}}>
          {parts.map((s, i) => s.startsWith('*')
            ? <span key={i} style={{color: accent}}>{s.slice(1, -1)}</span>
            : <span key={i}>{s}</span>)}
        </div> : null}
        {(p.ticker ?? true) ? (
          <div style={{marginTop: w * 0.06}}>
            {Array.from({length: 3}, (_, i) => (
              <div key={i} style={{height: Math.max(3, w * 0.012), borderRadius: 99,
                width: `${30 + ((random(`tk${i}`) * 50 + f * (2 + i)) % 50)}%`,
                background: i === 0 ? accent : 'rgba(255,255,255,0.25)',
                margin: `${w * 0.018}px auto 0`, opacity: 0.8}} />
            ))}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

// ---------- VERROUILLAGE DE CIBLE (cree sur mesure pour la video Battlefield) ----------
// Reticule anime : balaie l'ecran, se verrouille sur (x,y), tourne + tirets + "LOCK".
// params: x(0.5) y(0.5) r(0.09 fraction largeur) color(#ff3b3b) sweepFrames(10)
//         label("LOCK") dashes(8) spin(1.2) thickness(3)
const TargetLock: React.FC<any> = ({p, durF}) => {
  const f = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const sweep = interpolate(f, [0, p.sweepFrames ?? 10], [0, 1], {...ease, easing: Easing.out(Easing.cubic)});
  const out = interpolate(f, [durF - 8, durF], [1, 0], ease);
  const locked = sweep >= 1;
  const tx = width * (p.x ?? 0.5), ty = height * (p.y ?? 0.5);
  const cx = width * 0.1 + (tx - width * 0.1) * sweep;
  const cy = height * 0.15 + (ty - height * 0.15) * sweep;
  const R = width * (p.r ?? 0.09) * (1.6 - sweep * 0.6);
  const color = p.color ?? '#ff3b3b';
  const th = p.thickness ?? 3;
  const n = p.dashes ?? 8;
  const rot = f * (p.spin ?? 1.2) * (locked ? 2 : 6);
  const pulse = locked ? 1 + Math.sin(f * 0.5) * 0.04 : 1;
  return (
    <AbsoluteFill style={{opacity: out}}>
      <svg width={width} height={height}>
        <g transform={`translate(${cx},${cy}) rotate(${rot}) scale(${pulse})`}>
          {Array.from({length: n}, (_, i) => {
            const a0 = (i / n) * 360, a1 = a0 + 360 / n * 0.55;
            const rad = (d: number) => (d * Math.PI) / 180;
            return <path key={i} fill="none" stroke={color} strokeWidth={th}
              d={`M ${Math.cos(rad(a0)) * R} ${Math.sin(rad(a0)) * R} A ${R} ${R} 0 0 1 ${Math.cos(rad(a1)) * R} ${Math.sin(rad(a1)) * R}`}
              opacity={locked ? 0.95 : 0.6} />;
          })}
          {[0, 90, 180, 270].map((a) => (
            <line key={a} x1={Math.cos((a * Math.PI) / 180) * R * 0.72} y1={Math.sin((a * Math.PI) / 180) * R * 0.72}
              x2={Math.cos((a * Math.PI) / 180) * R * 1.12} y2={Math.sin((a * Math.PI) / 180) * R * 1.12}
              stroke={color} strokeWidth={th} opacity={0.9} />
          ))}
          <circle r={Math.max(2, th)} fill={color} />
        </g>
        {locked && (p.label ?? 'LOCK') ? (
          <text x={cx} y={cy - R * 1.3} textAnchor="middle" fill={color}
            fontFamily="CaptionFont, sans-serif" fontWeight="800" fontSize={R * 0.42}
            style={{letterSpacing: 3}}>{p.label ?? 'LOCK'}</text>
        ) : null}
      </svg>
    </AbsoluteFill>
  );
};

const REGISTRY: Record<string, React.FC<any>> = {
  rain: Rain, snow: Snow, confetti: Confetti, sparks: Sparks, flash: Flash,
  glitch: Glitch, vignette: Vignette, speedlines: Speedlines, spotlight: Spotlight,
  circle: Circle, pulse_ring: PulseRing, light_leak: LightLeak, grain: Grain,
  title_card: TitleCard,
  emoji_rain: EmojiRain, screen_crack: ScreenCrack, shockwave: Shockwave,
  letterbox: Letterbox, heartbeat: Heartbeat, focus_lines: FocusLines,
  big_stat: BigStat, stat_panel: StatPanel, target_lock: TargetLock,
};

export const FX: React.FC<{name: string; params?: any; durF: number}> = ({name, params = {}, durF}) => {
  const C = REGISTRY[name];
  if (!C) return null;
  return <C p={params} durF={durF} />;
};

export const FX_LIST = Object.keys(REGISTRY);
