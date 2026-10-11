import Icon from './Icon';

export default function Segmented({ options, value, onChange, size = 'md' }) {
  const fs = size === 'sm' ? 11.5 : 12.5;
  return (
    <div style={{
      display: 'inline-flex', background: 'var(--surface-2)', border: '1px solid var(--line)',
      borderRadius: 'var(--radius-sm)', padding: 2, gap: 2,
    }}>
      {options.map(o => {
        const val = typeof o === 'object' ? o.value : o;
        const lab = typeof o === 'object' ? o.label : o;
        const ic = typeof o === 'object' ? o.icon : null;
        const on = val === value;
        return (
          <button key={val} onClick={() => onChange(val)} style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: size === 'sm' ? '4px 9px' : '5px 11px',
            fontSize: fs, fontFamily: 'var(--font-ui)', fontWeight: on ? 600 : 500, cursor: 'pointer',
            border: 'none', borderRadius: 'calc(var(--radius-sm) - 1px)',
            background: on ? 'var(--surface)' : 'transparent', color: on ? 'var(--ink)' : 'var(--ink-2)',
            boxShadow: on ? 'var(--shadow-sm)' : 'none', transition: 'all .14s ease',
          }}>
            {ic && <Icon name={ic} size={fs + 1} />}{lab}
          </button>
        );
      })}
    </div>
  );
}
