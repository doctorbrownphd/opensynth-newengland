import { useState } from 'react';
import Icon from './Icon';

export default function Btn({ children, kind = 'ghost', size = 'md', icon, onClick, active, style, title }) {
  const [hover, setHover] = useState(false);
  const sizes = { sm: { p: '5px 10px', f: 12, g: 6 }, md: { p: '8px 14px', f: 13, g: 7 }, lg: { p: '11px 18px', f: 14, g: 8 } };
  const s = sizes[size];
  const base = {
    display: 'inline-flex', alignItems: 'center', gap: s.g, padding: s.p, fontSize: s.f,
    fontFamily: 'var(--font-ui)', fontWeight: 500, border: '1px solid transparent',
    borderRadius: 'var(--radius-sm)', cursor: 'pointer', transition: 'all .14s ease',
    whiteSpace: 'nowrap', lineHeight: 1.2, ...style,
  };
  const kinds = {
    primary: { background: hover ? 'var(--accent-2)' : 'var(--accent)', color: 'var(--accent-ink)', boxShadow: 'var(--shadow-sm)' },
    secondary: { background: hover ? 'var(--surface-3)' : 'var(--surface-2)', color: 'var(--ink)', borderColor: 'var(--line)' },
    ghost: { background: hover || active ? 'var(--surface-2)' : 'transparent', color: active ? 'var(--ink)' : 'var(--ink-2)', borderColor: active ? 'var(--line)' : 'transparent' },
    outline: { background: hover ? 'var(--accent-weak)' : 'transparent', color: 'var(--accent)', borderColor: 'var(--accent)' },
  };
  return (
    <button title={title} onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
            style={{ ...base, ...kinds[kind] }}>
      {icon && <Icon name={icon} size={s.f + 2} />}{children}
    </button>
  );
}
