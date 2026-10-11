import { useState, useRef, useEffect } from 'react';

function clampN(v, a, b) { return Math.max(a, Math.min(b, v)); }

export default function LoadChart({ data, height = 300, showTemp = true, stacked = true, animKey }) {
  const wrapRef = useRef(null);
  const [w, setW] = useState(720);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver(es => setW(es[0].contentRect.width));
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  const pad = { l: 46, r: showTemp ? 44 : 16, t: 14, b: 28 };
  const iw = Math.max(120, w - pad.l - pad.r);
  const ih = height - pad.t - pad.b;
  const pts = data.points;
  const maxLoad = Math.max(2, ...pts.map(p => p.gross)) * 1.08;
  const minLoad = Math.min(0, ...pts.map(p => p.net)) * 1.15;
  const x = i => pad.l + (i / 95) * iw;
  const y = v => pad.t + ih - ((v - minLoad) / (maxLoad - minLoad)) * ih;
  const tMin = 0, tMax = 90;
  const yT = v => pad.t + ih - ((v - tMin) / (tMax - tMin)) * ih;

  const bands = [
    { key: 'base',  color: 'var(--d-base)',  label: 'Baseload' },
    { key: 'heat',  color: 'var(--d-heat)',  label: 'Heating' },
    { key: 'cool',  color: '#7FB0B5',        label: 'Cooling' },
    { key: 'ev',    color: 'var(--d-ev)',    label: 'EV' },
    { key: 'behav', color: 'var(--d-load)',  label: 'Appliance' },
  ];

  function bandPath(idx) {
    let lower = pts.map(() => 0);
    for (let k = 0; k < idx; k++) lower = lower.map((v, i) => v + pts[i][bands[k].key]);
    const upper = lower.map((v, i) => v + pts[i][bands[idx].key]);
    let d = `M ${x(0)} ${y(lower[0])}`;
    for (let i = 0; i < 96; i++) d += ` L ${x(i)} ${y(upper[i])}`;
    for (let i = 95; i >= 0; i--) d += ` L ${x(i)} ${y(lower[i])}`;
    return d + ' Z';
  }

  let solarPath = `M ${x(0)} ${y(0)}`;
  pts.forEach((p, i) => { solarPath += ` L ${x(i)} ${y(p.solar)}`; });
  solarPath += ` L ${x(95)} ${y(0)} Z`;

  let netPath = '';
  pts.forEach((p, i) => { netPath += (i ? ' L' : 'M') + ` ${x(i)} ${y(p.net)}`; });

  let tempPath = '';
  if (showTemp) pts.forEach((p, i) => { tempPath += (i ? ' L' : 'M') + ` ${x(i)} ${yT(data.summary.temp)}`; });

  const yTicks = 4;
  const handleMove = e => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - rect.left) * (w / rect.width);
    const i = Math.round(clampN((px - pad.l) / iw * 95, 0, 95));
    setHover(i);
  };
  const hp = hover != null ? pts[hover] : null;

  return (
    <div ref={wrapRef} style={{ width: '100%', position: 'relative' }}>
      <svg key={animKey} viewBox={`0 0 ${w} ${height}`} width="100%" height={height}
           onMouseMove={handleMove} onMouseLeave={() => setHover(null)}
           style={{ display: 'block', fontFamily: 'var(--font-mono)' }}>
        {Array.from({ length: yTicks + 1 }).map((_, k) => {
          const v = minLoad + (k / yTicks) * (maxLoad - minLoad);
          return (
            <g key={k}>
              <line x1={pad.l} x2={pad.l + iw} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeWidth="1" />
              <text x={pad.l - 8} y={y(v) + 3} textAnchor="end" fontSize="10" fill="var(--ink-3)">{v.toFixed(0)}</text>
            </g>
          );
        })}
        <line x1={pad.l} x2={pad.l + iw} y1={y(0)} y2={y(0)} stroke="var(--line-strong)" strokeWidth="1.5" />
        {[0, 4, 8, 12, 16, 20, 24].map(hr => (
          <text key={hr} x={x(hr / 24 * 95.9)} y={height - 8} textAnchor="middle" fontSize="10"
                fill="var(--ink-3)">{String(hr).padStart(2, '0')}</text>
        ))}
        {pts.some(p => p.solar < 0) &&
          <path d={solarPath} fill="var(--d-solar)" opacity="0.22" />}
        {stacked && bands.map((b, idx) => (
          <path key={b.key} d={bandPath(idx)} fill={b.color} opacity={idx === 4 ? 0.30 : 0.5} />
        ))}
        <path d={netPath} fill="none" stroke="var(--ink)" strokeWidth="2"
              strokeLinejoin="round" strokeLinecap="round" />
        {showTemp && <path d={tempPath} fill="none" stroke="var(--d-temp)" strokeWidth="1.5"
              strokeDasharray="3 3" opacity="0.8" />}
        {showTemp && <text x={pad.l + iw + 6} y={yT(data.summary.temp) + 3} fontSize="9" fill="var(--d-temp)">{data.summary.temp.toFixed(0)}°F</text>}
        {hp && <g>
          <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={pad.t + ih} stroke="var(--accent)" strokeWidth="1" />
          <circle cx={x(hover)} cy={y(hp.net)} r="3.5" fill="var(--accent)" stroke="var(--surface)" strokeWidth="1.5" />
        </g>}
      </svg>
      {hp && <div className="mono" style={{
        position: 'absolute', top: 6, left: clampN(x(hover) + 8, 8, w - 148),
        background: 'var(--ink)', color: 'var(--ink-inv)', padding: '6px 9px',
        borderRadius: 'var(--radius-sm)', fontSize: 11, pointerEvents: 'none',
        whiteSpace: 'nowrap', boxShadow: 'var(--shadow-md)',
      }}>
        <div style={{ opacity: .6, fontSize: 10 }}>
          {String(Math.floor(hp.hour)).padStart(2, '0')}:{String(Math.round((hp.hour % 1) * 60)).padStart(2, '0')}
        </div>
        <div style={{ fontWeight: 600 }}>{hp.net.toFixed(2)} kW net</div>
        {hp.solar < 0 && <div style={{ opacity: .7, color: 'var(--d-solar)' }}>solar {hp.solar.toFixed(2)}</div>}
      </div>}
    </div>
  );
}
