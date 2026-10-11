export default function Sparkline({ pts, width = 84, height = 26, color = 'var(--d-load)' }) {
  const max = Math.max(...pts), min = Math.min(0, ...pts);
  const x = i => (i / (pts.length - 1)) * width;
  const y = v => height - 3 - ((v - min) / (max - min || 1)) * (height - 6);
  let d = '';
  pts.forEach((v, i) => d += (i ? ' L' : 'M') + ` ${x(i).toFixed(1)} ${y(v).toFixed(1)}`);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} style={{ display: 'block' }}>
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
