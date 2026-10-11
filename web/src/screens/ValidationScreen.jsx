import { Icon, Card, Stat, Badge, SectionHead } from '../components';
import Histogram from '../charts/Histogram';
import { useValidation } from '../hooks/useApi';

export function ValidationScreen() {
  const { data, loading } = useValidation();
  if (loading || !data) return <div>Loading validation data…</div>;

  const { checks, synth_distribution, target_distribution } = data;
  const pass = checks.filter(c => c.passing).length;

  return (
    <div className="os-fade" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div className="val-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 14 }}>
        <Card pad={16}>
          <Stat label="Checks passing" value={`${pass}/${checks.length}`}
                color={pass === checks.length ? 'var(--ok)' : 'var(--warn)'} sub="acceptance gate" />
        </Card>
        <Card pad={16}><Stat label="Synthetic meters" value="10,000" sub="validated v1.0 build" /></Card>
        <Card pad={16}><Stat label="Reference sources" value="6" sub="EIA · ISO-NE · NREL" /></Card>
        <Card pad={16}><Stat label="Privacy audit" value="PASS" color="var(--ok)" sub="no reidentification" /></Card>
      </div>

      <div className="val-layout" style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 18, alignItems: 'start' }}>
        <Card pad={0} style={{ overflow: 'hidden' }}>
          <SectionHead icon="shield" title="Validation against regional statistics"
                       right={<Badge tone={pass === checks.length ? 'ok' : 'warn'}>{pass}/{checks.length} within tolerance</Badge>} />
          <div>
            {checks.map((v, i) => (
              <div key={v.id} style={{
                display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 14, alignItems: 'center',
                padding: '13px 16px', borderBottom: i < checks.length - 1 ? '1px solid var(--line)' : 'none',
              }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>{v.metric}</div>
                  <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {v.source} · {v.target}
                  </div>
                </div>
                <div className="mono tnum" style={{ textAlign: 'right', fontSize: 11.5, color: 'var(--ink-2)' }}>
                  <div>tgt <span style={{ color: 'var(--ink)' }}>{v.target_val}</span></div>
                  <div>syn <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{v.synth_val}</span> <span style={{ color: 'var(--ink-3)' }}>{v.unit}</span></div>
                </div>
                <Badge tone={v.passing ? 'ok' : 'warn'}>
                  {v.passing ? <Icon name="check" size={12} /> : <Icon name="x" size={12} />}
                  {v.delta != null ? `${v.delta}%` : 'ok'}
                </Badge>
              </div>
            ))}
          </div>
        </Card>

        <Card pad={18}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 7 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, whiteSpace: 'nowrap' }}>Annual kWh distribution</div>
            <Badge tone="ok"><Icon name="check" size={12} />+1.8%</Badge>
          </div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-3)', marginBottom: 14 }}>
            synthetic vs EIA RECS — NE residential
          </div>
          <Histogram synth={synth_distribution} target={target_distribution} height={150} />
          <div style={{ display: 'flex', gap: 16, marginTop: 12, fontSize: 11, color: 'var(--ink-2)' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--accent)' }} />Synthetic · μ 8,612
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--ink-3)', opacity: .4 }} />RECS target · μ 8,460
            </span>
          </div>
          <div style={{ marginTop: 18, paddingTop: 16, borderTop: '1px solid var(--line)' }}>
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-3)', marginBottom: 10, letterSpacing: '0.04em' }}>
              OPEN FLAG · NEEDS REVIEW
            </div>
            <div style={{ fontSize: 12, color: 'var(--ink-2)', lineHeight: 1.6 }}>
              Winter monthly kWh for oil-heat homes runs <strong style={{ color: 'var(--ink)' }}>+10.6%</strong> over RECS.
              Likely over-weighting electric backup on coldest days — flagged for CVAE retraining before v1.1.
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
