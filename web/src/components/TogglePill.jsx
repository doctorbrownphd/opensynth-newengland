import Icon from './Icon';

export default function TogglePill({ icon, label, value, onChange, color }) {
  return (
    <button onClick={() => onChange(!value)} style={{
      display: 'flex', alignItems: 'center', gap: 9, width: '100%', padding: '9px 11px',
      cursor: 'pointer', background: value ? 'var(--accent-weak)' : 'var(--surface)', textAlign: 'left',
      border: `1px solid ${value ? 'var(--accent)' : 'var(--line)'}`, borderRadius: 'var(--radius-sm)',
      transition: 'all .14s ease', fontFamily: 'var(--font-ui)',
    }}>
      <span style={{ color: value ? (color || 'var(--accent)') : 'var(--ink-3)', display: 'flex' }}>
        <Icon name={icon} size={17} />
      </span>
      <span style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--ink)', flex: 1 }}>{label}</span>
      <span style={{
        width: 30, height: 17, borderRadius: 99,
        background: value ? 'var(--accent)' : 'var(--line-strong)',
        position: 'relative', transition: 'all .16s ease', flexShrink: 0,
      }}>
        <span style={{
          position: 'absolute', top: 2, left: value ? 15 : 2,
          width: 13, height: 13, borderRadius: 99, background: 'var(--surface)',
          transition: 'all .16s ease', boxShadow: '0 1px 2px rgba(0,0,0,.3)',
        }} />
      </span>
    </button>
  );
}
