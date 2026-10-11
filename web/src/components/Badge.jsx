export default function Badge({ children, tone = 'neutral', mono = true }) {
  const tones = {
    ok:      { bg: 'var(--ok-bg)',      c: 'var(--ok)' },
    warn:    { bg: 'var(--warn-bg)',    c: 'var(--warn)' },
    bad:     { bg: 'var(--bad-bg)',     c: 'var(--bad)' },
    accent:  { bg: 'var(--accent-weak)', c: 'var(--accent)' },
    neutral: { bg: 'var(--surface-2)',  c: 'var(--ink-2)' },
  };
  const t = tones[tone];
  return (
    <span className={mono ? 'mono' : ''} style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: t.bg, color: t.c, fontSize: 10.5, fontWeight: 600,
      padding: '3px 8px', borderRadius: 99, letterSpacing: '0.02em', whiteSpace: 'nowrap',
    }}>
      {children}
    </span>
  );
}
