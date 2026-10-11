export default function Logo({ size = 26 }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <svg width={size} height={size} viewBox="0 0 32 32" style={{ flexShrink: 0 }}>
        <rect x="1" y="1" width="30" height="30" rx="7" fill="var(--accent)" />
        <path d="M5 21c2.5 0 2.5-10 5-10s2.5 16 5 16 2.5-19 5-19 2.5 11 5 11"
              fill="none" stroke="var(--accent-ink)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div style={{ lineHeight: 1 }}>
        <div style={{ fontWeight: 700, fontSize: 15, letterSpacing: '-0.02em' }}>
          OpenSynth<span style={{ color: 'var(--accent)' }}> NE</span>
        </div>
        <div className="mono" style={{ fontSize: 9.5, color: 'var(--ink-3)', letterSpacing: '0.04em', marginTop: 1 }}>
          SYNTHETIC AMI · NEW ENGLAND
        </div>
      </div>
    </div>
  );
}
