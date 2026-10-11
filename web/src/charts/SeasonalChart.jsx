import { useState, useRef, useEffect } from 'react';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const monthStart = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];

export default function SeasonalChart({ year, height = 220 }) {
  const wrapRef = useRef(null);
  const [w, setW] = useState(720);

  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver(es => setW(es[0].contentRect.width));
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  const pad = { l: 40, r: 40, t: 12, b: 24 };
  const iw = w - pad.l - pad.r, ih = height - pad.t - pad.b;
  const maxP = Math.max(...year.map(d => d.peak)) * 1.08;
  const x = d => pad.l + (d / 364) * iw;
  const y = v => pad.t + ih - (v / maxP) * ih;
  const yT = v => pad.t + ih - ((v + 10) / 100) * ih;

  let peakArea = `M ${x(0)} ${y(0)}`;
  year.forEach(d => peakArea += ` L ${x(d.d)} ${y(d.peak)}`);
  peakArea += ` L ${x(364)} ${y(0)} Z`;

  let tempLine = '';
  year.forEach(d => tempLine += (d.d ? ' L' : 'M') + ` ${x(d.d)} ${yT(d.temp)}`);

  let peakLine = '';
  year.forEach(d => peakLine += (d.d ? ' L' : 'M') + ` ${x(d.d)} ${y(d.peak)}`);

  return (
    <div ref={wrapRef} style={{ width: '100%' }}>
      <svg viewBox={`0 0 ${w} ${height}`} width="100%" height={height}
           style={{ display: 'block', fontFamily: 'var(--font-mono)' }}>
        {monthStart.map((d, i) => (
          <text key={i} x={x(d + 14)} y={height - 7} textAnchor="middle" fontSize="9.5" fill="var(--ink-3)">
            {MONTHS[i]}
          </text>
        ))}
        <path d={peakArea} fill="var(--accent)" opacity="0.16" />
        <path d={peakLine} fill="none" stroke="var(--accent)" strokeWidth="1.5" />
        <path d={tempLine} fill="none" stroke="var(--d-temp)" strokeWidth="1.3" strokeDasharray="3 3" opacity="0.85" />
      </svg>
    </div>
  );
}
