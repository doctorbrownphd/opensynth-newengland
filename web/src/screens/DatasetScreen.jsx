import { useState, useMemo } from 'react';
import { Icon, Card, Stat, Badge, Btn, Select, SectionHead } from '../components';
import Sparkline from '../charts/Sparkline';
import { useCatalog, useMetadata } from '../hooks/useApi';


const FORMATS = [
  { id: 'parquet', label: 'Parquet', sub: 'primary · columnar', size: '2.1 GB' },
  { id: 'csv', label: 'CSV', sub: 'secondary · portable', size: '9.4 GB' },
  { id: 'greenbutton', label: 'Green Button XML', sub: 'ESPI · optional', size: '14 GB' },
];

function fuelIcon(fuel) {
  if (fuel === 'heatpump') return 'refresh';
  if (fuel === 'electric') return 'bolt';
  return 'flame';
}

export function DatasetScreen() {
  const { data, loading } = useCatalog();
  const { data: meta } = useMetadata();
  const [fArch, setFArch] = useState('all');
  const [fFuel, setFFuel] = useState('all');
  const [fDer, setFDer] = useState('all');
  const [fmt, setFmt] = useState('parquet');

  const ARCHETYPES = useMemo(() => [
    { value: 'all', label: 'All archetypes' },
    ...(meta ? meta.archetypes.map(a => ({ value: a.id, label: a.label })) : []),
  ], [meta]);
  const FUELS = useMemo(() => [
    { value: 'all', label: 'All fuels' },
    ...(meta ? meta.fuels.map(f => ({ value: f.id, label: f.label })) : []),
  ], [meta]);
  const DERS = useMemo(() => [
    { value: 'all', label: 'All DER' },
    ...(meta ? meta.der_configs.map(d => ({ value: d.id, label: d.label })) : []),
  ], [meta]);

  if (loading || !data) return <div>Loading catalog…</div>;

  const catalog = data.catalog;
  const rows = catalog.filter(r =>
    (fArch === 'all' || r.archetype === fArch) &&
    (fFuel === 'all' || r.fuel === fFuel) &&
    (fDer === 'all' || r.der === fDer)
  );
  const total = rows.reduce((s, r) => s + r.count, 0);

  return (
    <div className="os-fade ds-layout" style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 18, alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Card pad={0} style={{ overflow: 'hidden' }}>
          <SectionHead icon="grid" title="Archetype catalog"
                       right={<span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)', whiteSpace: 'nowrap' }}>{rows.length} / 96 types · {total.toLocaleString()} meters</span>} />
          <div style={{ display: 'flex', gap: 10, padding: '12px 16px', flexWrap: 'wrap', borderBottom: '1px solid var(--line)', background: 'var(--surface-2)' }}>
            <Select value={fArch} onChange={setFArch} options={ARCHETYPES} />
            <Select value={fFuel} onChange={setFFuel} options={FUELS} />
            <Select value={fDer} onChange={setFDer} options={DERS} />
          </div>
          <div style={{ maxHeight: 520, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
              <thead>
                <tr style={{ position: 'sticky', top: 0, background: 'var(--surface)', boxShadow: '0 1px 0 var(--line)' }}>
                  {['Archetype', 'Fuel', 'DER', 'Winter shape', 'Meters'].map((h, i) => (
                    <th key={h} className="mono" style={{
                      textAlign: i >= 3 ? 'right' : 'left', padding: '9px 16px', fontSize: 10,
                      letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--ink-3)', fontWeight: 500,
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 60).map(r => (
                  <tr key={r.id} style={{ borderTop: '1px solid var(--line)' }}>
                    <td style={{ padding: '8px 16px', fontWeight: 500 }}>{r.archetype_label}</td>
                    <td style={{ padding: '8px 16px', color: 'var(--ink-2)', whiteSpace: 'nowrap' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                        <Icon name={fuelIcon(r.fuel)} size={13} style={{ color: 'var(--d-heat)', opacity: .8 }} />
                        {r.fuel_label}
                      </span>
                    </td>
                    <td style={{ padding: '8px 16px' }}>
                      <span style={{ display: 'inline-flex', gap: 4 }}>
                        {r.solar && <Badge tone="neutral"><Icon name="solar" size={11} />PV</Badge>}
                        {r.ev && <Badge tone="neutral"><Icon name="car" size={11} />EV</Badge>}
                        {r.der === 'none' && <span style={{ color: 'var(--ink-3)', fontSize: 11 }}>—</span>}
                      </span>
                    </td>
                    <td style={{ padding: '6px 16px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <Sparkline pts={r.sparkline} />
                      </div>
                    </td>
                    <td className="mono tnum" style={{ padding: '8px 16px', textAlign: 'right', color: 'var(--ink)' }}>{r.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length > 60 && (
              <div className="mono" style={{ padding: '10px 16px', fontSize: 11, color: 'var(--ink-3)', textAlign: 'center', borderTop: '1px solid var(--line)' }}>
                + {rows.length - 60} more types
              </div>
            )}
          </div>
        </Card>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, position: 'sticky', top: 76 }}>
        <Card pad={18}>
          <div style={{ fontSize: 13.5, fontWeight: 600, marginBottom: 4 }}>OpenSynth NE · v1.0</div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-3)', marginBottom: 16 }}>static dataset release</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 18 }}>
            <Stat label="Meters" value="10,000" />
            <Stat label="Intervals" value="35,040" sub="per meter / yr" />
            <Stat label="Resolution" value="15" unit="min" />
            <Stat label="Base types" value="96" />
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
            <Badge tone="accent">CC-BY 4.0</Badge>
            <Badge tone="neutral">NH·MA·CT·RI·VT·ME</Badge>
            <Badge tone="neutral">Res 90% · C&I 10%</Badge>
          </div>
        </Card>

        <Card pad={18}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icon name="download" size={16} style={{ color: 'var(--accent)' }} />Export format
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 14 }}>
            {FORMATS.map(f => (
              <button key={f.id} onClick={() => setFmt(f.id)} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '10px 12px', cursor: 'pointer', textAlign: 'left',
                border: `1px solid ${fmt === f.id ? 'var(--accent)' : 'var(--line)'}`,
                borderRadius: 'var(--radius-sm)',
                background: fmt === f.id ? 'var(--accent-weak)' : 'var(--surface)',
                transition: 'all .14s', fontFamily: 'var(--font-ui)',
              }}>
                <div>
                  <div style={{ fontSize: 12.5, fontWeight: 600 }}>{f.label}</div>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--ink-3)', whiteSpace: 'nowrap' }}>{f.sub}</div>
                </div>
                <span className="mono tnum" style={{ fontSize: 11, color: fmt === f.id ? 'var(--accent)' : 'var(--ink-3)' }}>{f.size}</span>
              </button>
            ))}
          </div>
          <Btn kind="primary" size="lg" icon="download" style={{ width: '100%', justifyContent: 'center' }}>Download dataset</Btn>
          <Btn kind="secondary" size="md" icon="book" style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}>Hugging Face · model weights</Btn>
        </Card>
      </div>
    </div>
  );
}
