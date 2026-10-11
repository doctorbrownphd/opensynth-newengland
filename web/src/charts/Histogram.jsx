export default function Histogram({ synth, target, height = 130 }) {
  const w = 100, n = synth.length;
  const maxV = Math.max(...synth, ...target);
  const bw = w / n;
  const h = height - 18;
  return (
    <svg viewBox={`0 0 ${w} ${height}`} width="100%" height={height} preserveAspectRatio="none"
         style={{ display: 'block' }}>
      {target.map((v, i) => (
        <rect key={'t' + i} x={i * bw + 0.4} width={bw - 0.8} y={h - (v / maxV) * h} height={(v / maxV) * h}
              fill="var(--ink-3)" opacity="0.28" />
      ))}
      {synth.map((v, i) => (
        <rect key={'s' + i} x={i * bw + 0.4} width={bw - 0.8} y={h - (v / maxV) * h} height={(v / maxV) * h}
              fill="var(--accent)" opacity="0.85" />
      ))}
    </svg>
  );
}
