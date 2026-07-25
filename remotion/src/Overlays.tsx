import React from 'react';
import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from 'remotion';

import {FX} from './FX';
import {DA, SplitLayout, makeDA, makeSplitLayout} from './theme';

// Media b-roll : image OU video (.mp4/.webm) -> OffthreadVideo.
const Media: React.FC<{src: string; style: any; scale?: number}> = ({src, style, scale}) => {
  const isVid = /\.(mp4|webm|mov)$/i.test(src);
  const s = staticFile(`media/${src}`);
  const st = scale ? {...style, transform: `scale(${scale})`} : style;
  return isVid ? <OffthreadVideo src={s} style={st} muted /> : <Img src={s} style={st} />;
};

type Item = any;

const ease = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// Entree/sortie generique (0->1->0)
function useLife(durF: number, inF = 8, outF = 8) {
  const f = useCurrentFrame();
  const appear = interpolate(f, [0, inF], [0, 1], ease);
  const disappear = interpolate(f, [durF - outF, durF], [1, 0], ease);
  return Math.min(appear, disappear);
}

const ImageOverlay: React.FC<{item: Item; width: number; height: number; durF: number}> = ({
  item, width, height, durF,
}) => {
  const f = useCurrentFrame();
  const life = useLife(durF, 10, 10);
  const kb = item.anim !== 'fade';
  const scale = kb ? interpolate(f, [0, durF], [1.06, 1.16], ease) : 1;
  const isFull = item.mode === 'fullscreen';
  if (isFull) {
    return (
      <AbsoluteFill style={{opacity: life}}>
        <AbsoluteFill style={{transform: `scale(${scale})`}}>
          <Media src={item.src} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        </AbsoluteFill>
      </AbsoluteFill>
    );
  }
  // mode "card" : insert flottant en haut
  const w = width * 0.82;
  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', paddingTop: height * 0.1}}>
      <div
        style={{
          width: w, height: w * 0.62, borderRadius: width * 0.03, overflow: 'hidden',
          opacity: life, transform: `translateY(${(1 - life) * -40}px) scale(${0.96 + life * 0.04})`,
          boxShadow: '0 20px 60px rgba(0,0,0,0.55)', border: `${width * 0.006}px solid #fff`,
        }}
      >
        <Media src={item.src} scale={scale} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      </div>
    </AbsoluteFill>
  );
};

const Callout: React.FC<{item: Item; width: number; height: number; durF: number; da: DA}> = ({
  item, width, height, durF, da,
}) => {
  const {fps} = useVideoConfig();
  const f = useCurrentFrame();
  const s = spring({frame: f, fps, config: {damping: 12, stiffness: 160}});
  const out = interpolate(f, [durF - 8, durF], [1, 0], ease);
  const top = item.pos === 'top';
  const fs = width * (item.size ?? 0.05); // params: size (fraction largeur), opacity
  return (
    <AbsoluteFill
      style={{
        justifyContent: top ? 'flex-start' : 'flex-end',
        alignItems: 'center',
        padding: height * 0.16,
      }}
    >
      <div
        style={{
          transform: `scale(${s}) translateY(${(1 - s) * 24}px)`,
          opacity: out * (item.opacity ?? 1),
          background: item.bg || da.surface,
          color: item.color || da.text,
          fontFamily: 'CaptionFont, sans-serif',
          fontWeight: 800,
          fontSize: fs,
          padding: `${fs * 0.4}px ${fs * 0.7}px`,
          borderRadius: fs * 0.6,
          border: `${width * 0.003}px solid rgba(255,255,255,0.15)`,
          boxShadow: '0 14px 40px rgba(0,0,0,0.5)',
          display: 'flex', gap: fs * 0.4, alignItems: 'center', maxWidth: '86%',
          textAlign: 'center',
        }}
      >
        {item.emoji ? <span style={{fontSize: fs * 1.2}}>{item.emoji}</span> : null}
        <span>{item.text}</span>
      </div>
    </AbsoluteFill>
  );
};

const Diagram: React.FC<{item: Item; width: number; height: number; durF: number; da: DA}> = ({
  item, width, height, durF, da,
}) => {
  const {fps} = useVideoConfig();
  const f = useCurrentFrame();
  const life = useLife(durF, 10, 12);
  const stagger = Math.round((item.stagger_s ?? 0.35) * fps);
  const nodes = item.nodes || [];
  const edges = item.edges || [];
  const idx = (id: string) => nodes.findIndex((n: Item) => n.id === id);
  const nodeAppear = (i: number) =>
    spring({frame: f - i * stagger, fps, config: {damping: 13, stiffness: 150}});
  const nodeW = width * (item.node_w || 0.34);
  const nodeH = height * (item.node_h || 0.09);

  return (
    <AbsoluteFill style={{opacity: life}}>
      {item.title ? (
        <div style={{
          position: 'absolute', top: height * 0.09, width: '100%', textAlign: 'center',
          color: '#fff', fontFamily: 'CaptionFont, sans-serif', fontWeight: 800,
          fontSize: width * 0.05, textShadow: '0 4px 16px rgba(0,0,0,0.6)',
        }}>{item.title}</div>
      ) : null}
      <svg width={width} height={height} style={{position: 'absolute', inset: 0}}>
        {edges.map((e: Item, k: number) => {
          const a = nodes[idx(e.from)]; const b = nodes[idx(e.to)];
          if (!a || !b) return null;
          const appearFrame = Math.max(idx(e.from), idx(e.to)) * stagger + 6;
          const p = interpolate(f, [appearFrame, appearFrame + 12], [0, 1], ease);
          const x1 = a.x * width, y1 = a.y * height, x2 = b.x * width, y2 = b.y * height;
          const mx = x1 + (x2 - x1) * p, my = y1 + (y2 - y1) * p;
          return (
            <g key={k}>
              <line x1={x1} y1={y1} x2={mx} y2={my} stroke={item.edge_color || da.accent}
                strokeWidth={width * 0.008} strokeLinecap="round" />
              {e.label && p > 0.9 ? (
                <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 8} fill="#fff"
                  fontFamily="CaptionFont, sans-serif" fontWeight={700} fontSize={width * 0.03}
                  textAnchor="middle">{e.label}</text>
              ) : null}
            </g>
          );
        })}
      </svg>
      {nodes.map((n: Item, i: number) => {
        const s = nodeAppear(i);
        return (
          <div key={n.id} style={{
            position: 'absolute',
            left: n.x * width - nodeW / 2, top: n.y * height - nodeH / 2,
            width: nodeW, height: nodeH,
            transform: `scale(${s})`, opacity: Math.min(1, s),
            background: n.bg || da.surface, color: n.color || da.text,
            border: `${width * 0.005}px solid ${n.border || da.accent}`,
            borderRadius: width * 0.02,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            textAlign: 'center', padding: width * 0.01,
            fontFamily: 'CaptionFont, sans-serif', fontWeight: 800, fontSize: width * 0.032,
            boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
          }}>
            {n.emoji ? <span style={{marginRight: 8, fontSize: width * 0.04}}>{n.emoji}</span> : null}
            {n.label}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// Panneau d'animation : en split il se place a l'OPPOSE de la video (selon le layout),
// sinon centre. Fond carte (da.surface) pour rester lisible sur n'importe quelle image.
const Panel: React.FC<{split?: boolean; width: number; height: number; life: number;
  da: DA; layout: SplitLayout; children: any}> = ({
  split, width, height, life, da, layout, children,
}) => {
  const stacked = layout.videoPos === 'top';
  const side = layout.videoPos === 'right' ? 'flex-start' : 'flex-end';
  return (
    <AbsoluteFill style={{
      justifyContent: split && stacked ? 'flex-end' : 'center',
      alignItems: split ? (stacked ? 'center' : side) : 'center',
      paddingRight: split && !stacked && side === 'flex-end' ? width * layout.margin : 0,
      paddingLeft: split && !stacked && side === 'flex-start' ? width * layout.margin : 0,
      paddingBottom: split && stacked ? height * layout.margin : 0,
    }}>
      <div style={{
        width: split ? (stacked ? width * 0.86 : width * 0.42) : width * 0.6,
        opacity: life, transform: `translateY(${(1 - life) * 30}px)`,
        color: da.text, fontFamily: 'CaptionFont, sans-serif',
        background: split ? 'transparent' : da.surface + 'E6',
        borderRadius: split ? 0 : width * 0.02,
        padding: split ? 0 : `${width * 0.03}px ${width * 0.035}px`,
        boxShadow: split ? undefined : '0 20px 60px rgba(0,0,0,0.45)',
      }}>
        {children}
      </div>
    </AbsoluteFill>
  );
};

// Fond plein cadre reutilisable ("un fond noir, un fond blanc" — plan theyo).
// {"type":"bg","preset":"dark|light|<nom>"} ou {"type":"bg","color":"#..."}.
const BgOverlay: React.FC<{item: Item; durF: number; da: DA}> = ({item, durF, da}) => {
  const life = useLife(durF, 8, 8);
  const color = item.color || da.backgrounds[item.preset || 'dark'] || da.bg;
  return <AbsoluteFill style={{background: color, opacity: life * (item.opacity ?? 1)}} />;
};

const StatCard: React.FC<{item: Item; width: number; height: number; durF: number; da: DA; layout: SplitLayout}> = ({
  item, width, height, durF, da, layout,
}) => {
  const {fps} = useVideoConfig();
  const f = useCurrentFrame();
  const life = useLife(durF, 10, 10);
  const p = interpolate(f, [6, Math.min(durF - 6, fps * 1.2)], [0, 1], ease);
  const target = parseFloat(String(item.value).replace(/[^\d.]/g, '')) || 0;
  const suffix = String(item.value).replace(/[\d.\s]/g, '') || '';
  const shown = Math.round(target * p);
  const accent = item.color || da.accent;
  return (
    <Panel split={item.split} width={width} height={height} life={life} da={da} layout={layout}>
      <div style={{fontSize: width * 0.11, fontWeight: 800, lineHeight: 1}}>
        {shown}<span style={{color: accent}}>{suffix}</span>
      </div>
      <div style={{height: height * 0.012, background: '#ffffff22', borderRadius: 999, marginTop: height * 0.02, overflow: 'hidden'}}>
        <div style={{width: `${p * (item.fill ?? target)}%`, height: '100%', background: accent, borderRadius: 999}} />
      </div>
      {item.label ? <div style={{fontSize: width * 0.028, opacity: 0.8, marginTop: height * 0.02}}>{item.label}</div> : null}
    </Panel>
  );
};

const BarChart: React.FC<{item: Item; width: number; height: number; durF: number; da: DA; layout: SplitLayout}> = ({
  item, width, height, durF, da, layout,
}) => {
  const {fps} = useVideoConfig();
  const f = useCurrentFrame();
  const life = useLife(durF, 10, 10);
  const bars = item.bars || [{h: 0.3}, {h: 0.5}, {h: 0.75}, {h: 1}];
  const maxH = height * 0.32;
  const accent = item.color || da.accent;
  return (
    <Panel split={item.split} width={width} height={height} life={life} da={da} layout={layout}>
      {item.title ? <div style={{fontSize: width * 0.03, opacity: 0.8, marginBottom: height * 0.02}}>{item.title}</div> : null}
      <div style={{display: 'flex', alignItems: 'flex-end', gap: width * 0.02, height: maxH}}>
        {bars.map((b: Item, i: number) => {
          const s = spring({frame: f - i * 6, fps, config: {damping: 14, stiffness: 120}});
          const hi = i === bars.length - 1;
          return (
            <div key={i} style={{flex: 1, height: `${(b.h || 0.5) * 100 * s}%`,
              background: hi ? accent : '#ffffff28', borderRadius: width * 0.008,
              boxShadow: hi ? `0 0 ${width * 0.02}px ${accent}` : undefined}} />
          );
        })}
      </div>
      {item.label ? <div style={{fontSize: width * 0.026, opacity: 0.7, marginTop: height * 0.015}}>{item.label}</div> : null}
    </Panel>
  );
};

const CalendarCard: React.FC<{item: Item; width: number; height: number; durF: number; da: DA; layout: SplitLayout}> = ({
  item, width, height, durF, da, layout,
}) => {
  const f = useCurrentFrame();
  const life = useLife(durF, 10, 10);
  const days = item.days || 30;
  const hl = item.highlight || 7;
  const accent = item.color || da.accent;
  const cell = (width * (item.split ? 0.42 : 0.6)) / 7 - width * 0.008;
  return (
    <Panel split={item.split} width={width} height={height} life={life} da={da} layout={layout}>
      <div style={{fontSize: width * 0.04, fontWeight: 800, marginBottom: height * 0.015}}>{item.month || 'MOIS'}</div>
      <div style={{display: 'flex', flexWrap: 'wrap', gap: width * 0.008}}>
        {Array.from({length: days}, (_, i) => {
          const on = i < hl;
          const app = interpolate(f, [i * 2, i * 2 + 8], [0, 1], ease);
          return (
            <div key={i} style={{
              width: cell, height: cell, borderRadius: width * 0.01,
              background: on ? accent : '#ffffff14',
              opacity: on ? app : 0.5,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: cell * 0.4, fontWeight: 700,
            }}>{i + 1}</div>
          );
        })}
      </div>
    </Panel>
  );
};

const Subscribe: React.FC<{item: Item; width: number; height: number; durF: number; cfg: any}> = ({
  item, width, height, durF, cfg,
}) => {
  const {fps} = useVideoConfig();
  const f = useCurrentFrame();
  const s = spring({frame: f, fps, config: {damping: 11, stiffness: 170}});
  const out = interpolate(f, [durF - 10, durF], [1, 0], ease);
  const color = item.color || cfg?.subscribe_color || '#FF0033';
  const name = item.channel || cfg?.channel_name || 'ABONNE-TOI';
  // curseur qui "tape"
  const tap = interpolate(f % Math.round(fps * 1.2), [0, fps * 0.5, fps * 0.6, fps * 0.7],
    [0, 0, 1, 0], ease);
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: height * 0.22}}>
      <div style={{transform: `scale(${s})`, opacity: out, position: 'relative'}}>
        <div style={{
          background: color, color: '#fff', fontFamily: 'CaptionFont, sans-serif', fontWeight: 800,
          fontSize: width * 0.052, padding: `${width * 0.025}px ${width * 0.06}px`,
          borderRadius: width * 0.5, boxShadow: `0 16px 46px ${color}77`,
          textTransform: 'uppercase', letterSpacing: 1,
        }}>▶ {name}</div>
        <div style={{
          position: 'absolute', right: -width * 0.02, bottom: -height * 0.02,
          fontSize: width * 0.08, transform: `translateY(${tap * -10}px) rotate(-15deg)`,
        }}>👆</div>
      </div>
    </AbsoluteFill>
  );
};

const LikeBurst: React.FC<{item: Item; width: number; height: number; durF: number}> = ({
  item, width, height, durF,
}) => {
  const {fps} = useVideoConfig();
  const f = useCurrentFrame();
  const s = spring({frame: f, fps, config: {damping: 10, stiffness: 180}});
  const out = interpolate(f, [durF - 10, durF], [1, 0], ease);
  const rise = interpolate(f, [0, durF], [0, -height * 0.12], ease);
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
      <div style={{transform: `translateY(${rise}px) scale(${s})`, opacity: out, fontSize: width * 0.16}}>👍</div>
    </AbsoluteFill>
  );
};

// Incrustation d'un EXTRAIT video (grab_clip.py) — petit ou grand, ou l'on veut.
// params : x,y (centre, fractions), w (largeur, fraction), label, label_pos ('bottom'
// defaut | 'top' — pour ne pas chevaucher les sous-titres), border, radius, muted,
// volume (0..1), shadow. Tout modifiable.
const ClipPiP: React.FC<{item: Item; width: number; height: number; durF: number}> = ({
  item, width, height, durF,
}) => {
  const {fps} = useVideoConfig();
  const f = useCurrentFrame();
  const p = item.params || {};
  const s = spring({frame: f, fps, config: {damping: 14, stiffness: 150}});
  const out = interpolate(f, [durF - 8, durF], [1, 0], ease);
  const w = width * (p.w ?? 0.4);
  const x = width * (p.x ?? 0.72), y = height * (p.y ?? 0.3);
  return (
    <AbsoluteFill>
      <div style={{
        position: 'absolute', left: x, top: y, width: w,
        transform: `translate(-50%,-50%) scale(${s})`, opacity: out,
        borderRadius: p.radius ?? 14, overflow: 'hidden',
        border: `${Math.max(2, width * 0.003)}px solid ${p.border ?? '#FFE500'}`,
        boxShadow: p.shadow === false ? undefined : '0 18px 50px rgba(0,0,0,0.55)',
      }}>
        <OffthreadVideo src={staticFile(`media/${item.src}`)} muted={p.muted ?? true}
          volume={p.volume ?? 1}
          style={{width: '100%', display: 'block'}} />
        {p.label ? <div style={{
          position: 'absolute', left: 0, right: 0, textAlign: 'center',
          ...(p.label_pos === 'top'
            ? {top: 0, background: 'linear-gradient(rgba(0,0,0,0.75), transparent)'}
            : {bottom: 0, background: 'linear-gradient(transparent, rgba(0,0,0,0.75))'}),
          fontFamily: 'CaptionFont, sans-serif', fontWeight: 800, color: '#fff',
          fontSize: w * 0.055, padding: `${w * 0.02}px 0`,
        }}>{p.label}</div> : null}
      </div>
    </AbsoluteFill>
  );
};

// CARTE visuelle codee (illustration a l'ecran) — ex : ecran noir "?" pour un truc inconnu.
// params : title, sub, emoji, bg, color, accent, x,y,w,h (fractions), size, border. Tout modifiable.
const Card: React.FC<{item: Item; width: number; height: number; durF: number}> = ({
  item, width, height, durF,
}) => {
  const {fps} = useVideoConfig();
  const f = useCurrentFrame();
  const p = item.params || {};
  const s = spring({frame: f, fps, config: {damping: 13, stiffness: 150}});
  const out = interpolate(f, [durF - 8, durF], [1, 0], ease);
  const w = width * (p.w ?? 0.34), h = height * (p.h ?? 0.42);
  const x = width * (p.x ?? 0.74), y = height * (p.y ?? 0.32);
  const fs = w * (p.size ?? 0.11);
  return (
    <AbsoluteFill>
      <div style={{
        position: 'absolute', left: x, top: y, width: w, height: h,
        transform: `translate(-50%,-50%) scale(${s})`, opacity: out,
        background: p.bg ?? '#0b0b0e', color: p.color ?? '#fff',
        borderRadius: 16, border: `${Math.max(2, width * 0.0025)}px solid ${p.border ?? 'rgba(255,255,255,0.2)'}`,
        boxShadow: '0 18px 50px rgba(0,0,0,0.55)',
        display: 'flex', flexDirection: 'column', justifyContent: 'center',
        alignItems: 'center', gap: h * 0.05, textAlign: 'center',
        fontFamily: 'CaptionFont, sans-serif', padding: w * 0.06,
      }}>
        {p.emoji ? <div style={{fontSize: fs * 2.2}}>{p.emoji}</div> : null}
        {p.title ? <div style={{fontSize: fs, fontWeight: 800, color: p.accent ?? '#FFE500'}}>{p.title}</div> : null}
        {p.sub ? <div style={{fontSize: fs * 0.55, opacity: 0.85}}>{p.sub}</div> : null}
      </div>
    </AbsoluteFill>
  );
};


export const Overlays: React.FC<{overlays: Item[]; width: number; height: number; cta: any;
  da?: DA; layout?: SplitLayout}> = ({
  overlays, width, height, cta, da: daIn, layout: layIn,
}) => {
  const {fps} = useVideoConfig();
  const da = daIn ?? makeDA({});
  const layout = layIn ?? makeSplitLayout({}, width, height);
  return (
    <>
      {overlays.map((item, i) => {
        const from = Math.max(0, Math.round((item.start || 0) * fps));
        const durF = Math.max(1, Math.round((item.dur || 2) * fps));
        const common = {item, width, height, durF};
        let node: React.ReactNode = null;
        if (item.type === 'fx') node = (
          <FX name={item.name} durF={durF}
            params={item.name === 'title_card' ? {accent: da.accent, ...(item.params || {})} : item.params} />
        );
        else if (item.type === 'vfx') node = (
          // video d'effet stock (pluie, fumee, confettis reels...) compositee par blend mode.
          // params : blend(screen|overlay|lighten|add...), opacity, tout modifiable.
          <AbsoluteFill style={{
            opacity: item.opacity ?? 0.75,
            mixBlendMode: (item.blend ?? 'screen') as any,
          }}>
            <Media src={item.src} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
          </AbsoluteFill>
        );
        else if (item.type === 'bg') node = <BgOverlay item={item} durF={durF} da={da} />;
        else if (item.type === 'image') node = <ImageOverlay {...common} />;
        else if (item.type === 'callout') node = <Callout {...common} da={da} />;
        else if (item.type === 'diagram') node = <Diagram {...common} da={da} />;
        else if (item.type === 'stat') node = <StatCard {...common} da={da} layout={layout} />;
        else if (item.type === 'bars') node = <BarChart {...common} da={da} layout={layout} />;
        else if (item.type === 'calendar') node = <CalendarCard {...common} da={da} layout={layout} />;
        else if (item.type === 'subscribe') node = <Subscribe {...common} cfg={cta} />;
        else if (item.type === 'like') node = <LikeBurst {...common} />;
        else if (item.type === 'clip') node = <ClipPiP {...common} />;
        else if (item.type === 'card') node = <Card {...common} />;
        else return null;
        return (
          <Sequence key={i} from={from} durationInFrames={durF} layout="none">
            {node}
          </Sequence>
        );
      })}
    </>
  );
};
