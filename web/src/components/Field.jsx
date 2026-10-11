export default function Field({ label, hint, children, accent }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
        <label className="mono" style={{
          fontSize: 10.5, letterSpacing: '0.045em', textTransform: 'uppercase',
          color: 'var(--ink-3)', fontWeight: 500, whiteSpace: 'nowrap',
        }}>{label}</label>
        {hint && <span className="mono" style={{ fontSize: 10.5, whiteSpace: 'nowrap', color: accent ? 'var(--accent)' : 'var(--ink-3)' }}>{hint}</span>}
      </div>
      {children}
    </div>
  );
}
