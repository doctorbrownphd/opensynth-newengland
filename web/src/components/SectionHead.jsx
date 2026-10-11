import Icon from './Icon';

export default function SectionHead({ icon, title, right }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '13px 16px', borderBottom: '1px solid var(--line)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Icon name={icon} size={17} style={{ color: 'var(--accent)' }} />
        <div style={{ fontSize: 13.5, fontWeight: 600, whiteSpace: 'nowrap' }}>{title}</div>
      </div>
      {right}
    </div>
  );
}
