import Icon from './Icon';

export default function Select({ value, onChange, options }) {
  return (
    <div style={{ position: 'relative' }}>
      <select value={value} onChange={e => onChange(e.target.value)} style={{
        appearance: 'none', width: '100%', padding: '8px 30px 8px 11px', fontSize: 13,
        fontFamily: 'var(--font-ui)', background: 'var(--surface)', color: 'var(--ink)',
        border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
      }}>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <div style={{ position: 'absolute', right: 9, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: 'var(--ink-3)' }}>
        <Icon name="chevdown" size={15} />
      </div>
    </div>
  );
}
