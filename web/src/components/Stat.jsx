export default function Stat({ label, value, unit, sub, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <div className="mono" style={{ fontSize: 10, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--ink-3)' }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
        <span className="tnum" style={{
          fontSize: 24, fontWeight: 600, letterSpacing: '-0.02em',
          color: color || 'var(--ink)', fontFamily: 'var(--font-mono)',
        }}>{value}</span>
        {unit && <span className="mono" style={{ fontSize: 12, color: 'var(--ink-3)' }}>{unit}</span>}
      </div>
      {sub && <div style={{ fontSize: 11.5, color: 'var(--ink-3)' }}>{sub}</div>}
    </div>
  );
}
