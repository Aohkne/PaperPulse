import { useEffect, useRef } from 'react';

/*
 * DotOrbitBackground
 *
 * Adapted from a public Framer code component ("DotOrbit"):
 *   https://framer.com/m/DotOrbit-Hr42.js@4qsg4Vw0IltefxxaFRCp
 * (Framer explicitly publishes these as embeddable/reusable asset URLs —
 * see https://www.framer.com/asset-urls — this is exactly the "grab the
 * code, use it outside Framer" use case they're meant for.)
 *
 * The original imports `addPropertyControls`, `ControlType`, `RenderTarget`
 * from the "framer" package, which only exists inside Framer's own site
 * editor/runtime — it is NOT an npm package and cannot resolve in a plain
 * Vite/React app. Those three things are stripped here:
 *   - `addPropertyControls(...)` only registers the Framer *design panel*
 *     UI for this component; it has zero effect on runtime rendering, so
 *     it's simply omitted. Props are passed as normal React props instead.
 *   - `RenderTarget.current() === RenderTarget.canvas` was just an "am I
 *     being previewed inside the Framer editor canvas?" check used to
 *     slightly cap speed there; irrelevant outside Framer, so `props.speed`
 *     is used directly.
 * The actual animation logic (canvas dot orbit/drift, mouse repel/attract,
 * proximity link-lines) is untouched — it's plain React + Canvas 2D, no
 * Framer runtime dependency at all.
 *
 * Colors: dotColor/lineColor/background accept literal CSS color strings
 * OR a CSS custom-property name (e.g. "--color-brand-500"), which gets
 * resolved via getComputedStyle on mount — so it can pull straight from
 * PaperPulse's paper/brand theme tokens instead of hardcoded hex.
 */

function resolveColor(value) {
  if (typeof value === 'string' && value.startsWith('--')) {
    const resolved = getComputedStyle(document.documentElement).getPropertyValue(value).trim();
    return resolved || value;
  }
  return value;
}

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

const toRgba = (input, alpha) => {
  const s = (input || '').trim();
  if (s.startsWith('rgba(') || s.startsWith('rgb(')) {
    const nums = s
      .replace(/rgba?\(/, '')
      .replace(')', '')
      .split(',')
      .map((v) => parseFloat(v.trim()));
    const [r = 0, g = 0, b = 0] = nums;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }
  const hx = s.replace('#', '').trim();
  const full =
    hx.length === 3
      ? hx
          .split('')
          .map((c) => c + c)
          .join('')
      : hx.slice(0, 6);
  const n = parseInt(full || '000000', 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

const DEFAULTS = {
  mode: 'drift',
  interaction: 'repel',
  tracking: 'global',
  density: 1,
  speed: 1,
  dotSize: 2,
  linkDistance: 140,
  background: 'rgba(0, 0, 0, 0)',
  dotColor: '#ffffff',
  lineColor: '#8a8a8a',
  opacity: 1,
  alpha: 1.4,
  interactionRadius: 140,
  interactionStrength: 18,
  cursorEase: 40,
};

export default function DotOrbitBackground(rawProps) {
  const props = { ...DEFAULTS, ...rawProps };
  const wrapRef = useRef(null);
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const mouseRef = useRef({ targetX: 0, targetY: 0, x: 0, y: 0, inside: false, hasInit: false });

  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return undefined;
    const ctx = canvas.getContext('2d');
    if (!ctx) return undefined;

    const background = resolveColor(props.background);
    const dotColor = resolveColor(props.dotColor);
    const lineColor = resolveColor(props.lineColor);

    const speed = props.speed;
    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const motionScale = prefersReducedMotion ? 0.45 : 1;

    let w = 1;
    let h = 1;

    const easeToLerp = (ease) => clamp((clamp(ease, 0, 100) / 100) * 0.3, 0, 0.3);

    const resize = () => {
      const r = wrap.getBoundingClientRect();
      w = Math.max(1, Math.floor(r.width));
      h = Math.max(1, Math.floor(r.height));
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const m = mouseRef.current;
      if (!m.hasInit) {
        m.targetX = w * 0.5;
        m.targetY = h * 0.5;
        m.x = m.targetX;
        m.y = m.targetY;
        m.hasInit = true;
      }
    };

    const ro = new ResizeObserver(resize);
    ro.observe(wrap);
    resize();

    const rebuildDots = () => {
      const count = clamp(Math.floor(((w * h) / 12000) * props.density), 20, 320);
      const cx = w * 0.5;
      const cy = h * 0.5;
      return Array.from({ length: count }).map((_, i) => {
        const r = Math.min(w, h) * (0.15 + Math.random() * 0.35);
        const a = Math.random() * Math.PI * 2;
        return {
          i,
          x: cx + Math.cos(a) * r,
          y: cy + Math.sin(a) * r,
          vx: (Math.random() - 0.5) * 0.6,
          vy: (Math.random() - 0.5) * 0.6,
          baseR: r,
          baseA: a,
          phase: Math.random() * Math.PI * 2,
        };
      });
    };

    let dots = rebuildDots();
    let lastArea = w * h;

    const onWindowPointerMove = (e) => {
      if (props.tracking !== 'global') return;
      const r = wrap.getBoundingClientRect();
      const x = e.clientX - r.left;
      const y = e.clientY - r.top;
      const inside = x >= 0 && x <= r.width && y >= 0 && y <= r.height;
      const m = mouseRef.current;
      m.targetX = x;
      m.targetY = y;
      m.inside = inside;
    };
    if (props.tracking === 'global') {
      window.addEventListener('pointermove', onWindowPointerMove, { passive: true });
    }

    const step = (tMs) => {
      const t = (tMs / 1000) * motionScale;
      const area = w * h;
      if (Math.abs(area - lastArea) / Math.max(1, lastArea) > 0.3) {
        dots = rebuildDots();
        lastArea = area;
      }

      const m = mouseRef.current;
      const lerp = easeToLerp(props.cursorEase);
      if (lerp > 0) {
        m.x += (m.targetX - m.x) * lerp;
        m.y += (m.targetY - m.y) * lerp;
      } else {
        m.x = m.targetX;
        m.y = m.targetY;
      }

      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = background;
      ctx.fillRect(0, 0, w, h);

      const cx = w * 0.5;
      const cy = h * 0.5;
      const interactionEnabled = props.interaction !== 'off' && props.tracking !== 'off';
      const ir = Math.max(10, props.interactionRadius);
      const ir2 = ir * ir;
      const strength = props.interactionStrength * motionScale;
      const alphaBoost = clamp(props.alpha, 0.2, 3);

      for (const d of dots) {
        if (props.mode === 'orbit') {
          const a = d.baseA + t * speed * 0.7 + Math.sin(t * 0.6 + d.phase) * 0.15;
          const rr = d.baseR * (0.92 + 0.08 * Math.sin(t * 1.2 + d.phase));
          d.x = cx + Math.cos(a) * rr;
          d.y = cy + Math.sin(a) * rr;
        } else {
          d.x += d.vx * speed * motionScale;
          d.y += d.vy * speed * motionScale;
          if (d.x < -20) d.x = w + 20;
          if (d.x > w + 20) d.x = -20;
          if (d.y < -20) d.y = h + 20;
          if (d.y > h + 20) d.y = -20;
        }
        if (interactionEnabled && m.inside) {
          const dx = d.x - m.x;
          const dy = d.y - m.y;
          const dist2 = dx * dx + dy * dy;
          if (dist2 < ir2) {
            const dist = Math.sqrt(dist2) || 1;
            const falloff = 1 - dist / ir;
            const dirx = dx / dist;
            const diry = dy / dist;
            const sign = props.interaction === 'repel' ? 1 : -1;
            const push = sign * falloff * falloff * strength;
            d.x += dirx * push;
            d.y += diry * push;
          }
        }
      }

      const maxD = Math.max(20, props.linkDistance);
      const maxD2 = maxD * maxD;
      ctx.lineWidth = 1;
      for (let i = 0; i < dots.length; i++) {
        for (let j = i + 1; j < dots.length; j++) {
          const a = dots[i];
          const b = dots[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < maxD2) {
            const d = Math.sqrt(d2);
            const alpha = (1 - d / maxD) * 0.55 * props.opacity * alphaBoost;
            ctx.strokeStyle = toRgba(lineColor, clamp(alpha, 0, 1));
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      for (const d of dots) {
        const pulse = 0.8 + 0.2 * Math.sin(t * 2 + d.phase);
        const r = Math.max(0.6, props.dotSize * pulse);
        const alpha = 0.95 * props.opacity * alphaBoost;
        ctx.fillStyle = toRgba(dotColor, clamp(alpha, 0, 1));
        ctx.beginPath();
        ctx.arc(d.x, d.y, r, 0, Math.PI * 2);
        ctx.fill();
      }

      rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      if (props.tracking === 'global') {
        window.removeEventListener('pointermove', onWindowPointerMove);
      }
    };
  }, [
    props.mode,
    props.interaction,
    props.tracking,
    props.density,
    props.speed,
    props.dotSize,
    props.linkDistance,
    props.background,
    props.dotColor,
    props.lineColor,
    props.opacity,
    props.alpha,
    props.interactionRadius,
    props.interactionStrength,
    props.cursorEase,
  ]);

  const onPointerMove = (e) => {
    if (props.tracking !== 'local') return;
    const el = wrapRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const m = mouseRef.current;
    m.targetX = e.clientX - r.left;
    m.targetY = e.clientY - r.top;
    m.inside = true;
  };
  const onPointerLeave = () => {
    if (props.tracking !== 'local') return;
    mouseRef.current.inside = false;
  };

  return (
    <div
      ref={wrapRef}
      onPointerMove={props.tracking === 'local' ? onPointerMove : undefined}
      onPointerLeave={props.tracking === 'local' ? onPointerLeave : undefined}
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        overflow: 'hidden',
        pointerEvents: props.tracking === 'global' ? 'none' : 'auto',
        touchAction: props.tracking === 'local' ? 'none' : 'auto',
        ...props.style,
      }}
    >
      <canvas
        ref={canvasRef}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', display: 'block' }}
      />
    </div>
  );
}
