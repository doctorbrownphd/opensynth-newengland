export default function Card({ children, style, pad = 18 }) {
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--line)',
      borderRadius: 'var(--radius)', boxShadow: 'var(--shadow-sm)',
      padding: pad, ...style,
    }}>
      {children}
    </div>
  );
}
