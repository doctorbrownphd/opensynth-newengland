import { useState, useMemo } from 'react';
import { Icon, Btn, Badge, Card, Stat, Field, Select, Segmented, TogglePill, CodeBlock, SectionHead } from '../components';
import LoadChart from '../charts/LoadChart';
import SeasonalChart from '../charts/SeasonalChart';
import { useGenerateDay, useGenerateYear, useMetadata } from '../hooks/useApi';

// Fallbacks used until /api/metadata responds
const FALLBACK_ARCHETYPES = [
  { value: 'colonial', label: 'Colonial · 2,400 ft²' },
  { value: 'cape', label: 'Cape · 1,500 ft²' },
  { value: 'ranch', label: 'Ranch · 1,700 ft²' },
  { value: 'multifamily', label: 'Multi-family · 950 ft²' },
  { value: 'antique', label: 'Antique (pre-1900) · 2,100 ft²' },
  { value: 'splitlevel', label: 'Split-level · 1,900 ft²' },
  { value: 'contemporary', label: 'Contemporary · 2,600 ft²' },
  { value: 'mobilehome', label: 'Mobile home · 1,050 ft²' },
];
const FALLBACK_FUELS = [
  { value: 'oil', label: 'Oil heat' },
  { value: 'gas', label: 'Natural gas' },
  { value: 'electric', label: 'Electric resistance' },
  { value: 'heatpump', label: 'Heat pump' },
];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTH_TEMP = [22, 25, 34, 46, 58, 68, 74, 72, 64, 52, 40, 28];

function ConfigPanel({ cfg, set, onGenerate, generating, archetypes, fuels }) {
  const autoTemp = MONTH_TEMP[cfg.month];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <Field label="Housing archetype">
        <Select value={cfg.archetype} onChange={v => set({ archetype: v })}
                options={archetypes} />
      </Field>
      <Field label="Heating fuel">
        <Select value={cfg.fuel} onChange={v => set({ fuel: v })}
                options={fuels} />
      </Field>
      <Field label="Month" hint={`${autoTemp}°F avg`} accent>
        <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          {MONTHS.map((m, i) => (
            <button key={m} onClick={() => set({ month: i, tempF: null })} style={{
              flex: '1 1 0', minWidth: 30, padding: '5px 0', fontSize: 11,
              fontFamily: 'var(--font-mono)', cursor: 'pointer',
              border: `1px solid ${cfg.month === i ? 'var(--accent)' : 'var(--line)'}`,
              background: cfg.month === i ? 'var(--accent)' : 'var(--surface)',
              color: cfg.month === i ? 'var(--accent-ink)' : 'var(--ink-2)',
              borderRadius: 'var(--radius-sm)', fontWeight: cfg.month === i ? 600 : 400,
              transition: 'all .12s',
            }}>{m}</button>
          ))}
        </div>
      </Field>
      <Field label="Day type">
        <Segmented value={cfg.dayType} onChange={v => set({ dayType: v })}
                   options={[{ value: 'weekday', label: 'Weekday' }, { value: 'weekend', label: 'Weekend' }, { value: 'holiday', label: 'Holiday' }]}
                   size="sm" />
      </Field>
      <Field label="Temperature override" hint={`${cfg.tempF == null ? autoTemp : cfg.tempF}°F`} accent>
        <input type="range" min="-5" max="95"
               value={cfg.tempF == null ? autoTemp : cfg.tempF}
               onChange={e => set({ tempF: +e.target.value })}
               style={{ width: '100%', accentColor: 'var(--accent)', cursor: 'pointer' }} />
      </Field>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <label className="mono" style={{ fontSize: 10.5, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--ink-3)', fontWeight: 500 }}>
          Distributed energy resources
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <TogglePill icon="solar" label="Rooftop solar" value={cfg.solar} onChange={v => set({ solar: v })} color="var(--d-solar)" />
          <TogglePill icon="car" label="EV charging" value={cfg.ev} onChange={v => set({ ev: v })} color="var(--d-ev)" />
          <TogglePill icon="battery" label="Battery" value={cfg.battery} onChange={v => set({ battery: v })} />
          {cfg.ev && <TogglePill icon="bolt" label="Managed charging" value={cfg.evManaged} onChange={v => set({ evManaged: v })} />}
        </div>
      </div>
      <Field label="Sample size" hint="profiles">
        <Segmented value={cfg.n} onChange={v => set({ n: v })}
                   options={[{ value: 1, label: '1' }, { value: 100, label: '100' }, { value: 1000, label: '1k' }, { value: 10000, label: '10k' }]}
                   size="sm" />
      </Field>
      <Btn kind="primary" size="lg" icon={generating ? 'refresh' : 'play'} onClick={onGenerate}
           style={{ justifyContent: 'center', width: '100%', opacity: generating ? 0.7 : 1 }}>
        {generating ? 'Generating…' : `Generate ${cfg.n.toLocaleString()}`}
      </Btn>
    </div>
  );
}

function snippetTokens(cfg) {
  const C = { comment: 'var(--ink-3)', kw: 'var(--d-ev)', str: 'var(--d-heat)', num: 'var(--accent)' };
  const t = cfg.tempF == null ? MONTH_TEMP[cfg.month] : cfg.tempF;
  return [
    { text: '# pip install opensynth-newengland\n', color: C.comment },
    { text: 'from', color: C.kw }, ' opensynth_ne ', { text: 'import', color: C.kw }, ' generate\n\n',
    'df = generate(\n',
    '    n=', { text: String(cfg.n), color: C.num }, ',\n',
    '    archetype=', { text: `"${cfg.archetype}"`, color: C.str }, ',\n',
    '    fuel=', { text: `"${cfg.fuel}"`, color: C.str }, ',\n',
    '    month=', { text: String(cfg.month + 1), color: C.num }, ',\n',
    '    temp_f=', { text: String(t), color: C.num }, ',\n',
    '    has_ev=', { text: cfg.ev ? 'True' : 'False', color: C.kw }, ',\n',
    '    has_solar=', { text: cfg.solar ? 'True' : 'False', color: C.kw }, ',\n',
    '    has_battery=', { text: cfg.battery ? 'True' : 'False', color: C.kw }, ',\n',
    ')\n',
    { text: `# → DataFrame[${cfg.n.toLocaleString()} meters × 35,040 intervals]`, color: C.comment },
  ];
}

function ResultPanel({ dayData, yearData, cfg, animKey }) {
  if (!dayData) return null;
  const day = dayData;
  const arch = ARCHETYPES.find(a => a.value === cfg.archetype);
  const fuel = FUELS.find(f => f.value === cfg.fuel);

  const legend = [
    { c: 'var(--d-base)', l: 'Baseload' },
    { c: 'var(--d-heat)', l: 'Heating' },
    cfg.ev && { c: 'var(--d-ev)', l: 'EV' },
    cfg.solar && { c: 'var(--d-solar)', l: 'Solar' },
    { c: 'var(--ink)', l: 'Net load', line: true },
  ].filter(Boolean);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Card pad={0} style={{ overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Icon name="wave" size={18} style={{ color: 'var(--accent)' }} />
            <div>
              <div style={{ fontSize: 13.5, fontWeight: 600 }}>Representative day · {MONTHS[cfg.month]}</div>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-3)', whiteSpace: 'nowrap' }}>
                {arch?.label.split(' ·')[0]} · {fuel?.label} · 15-min · 96 pts
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {legend.map(x => (
              <span key={x.l} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--ink-2)', whiteSpace: 'nowrap' }}>
                <span style={{ width: x.line ? 14 : 9, height: x.line ? 2 : 9, borderRadius: x.line ? 0 : 2, background: x.c, display: 'inline-block' }} />
                {x.l}
              </span>
            ))}
          </div>
        </div>
        <div style={{ padding: '14px 12px 8px' }}>
          <LoadChart data={day} height={284} animKey={animKey} />
        </div>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12 }}>
        <Card pad={14}>
          <Stat label="Daily peak" value={day.summary.peak.toFixed(2)} unit="kW"
                sub={`at ${String(Math.floor(day.summary.peak_hour)).padStart(2, '0')}:${String(Math.round((day.summary.peak_hour % 1) * 60)).padStart(2, '0')}`}
                color="var(--accent)" />
        </Card>
        <Card pad={14}>
          <Stat label="Daily energy" value={day.summary.kwh.toFixed(1)} unit="kWh"
                sub={`${(day.summary.kwh * 365 / 1000).toFixed(1)} MWh / yr est.`} />
        </Card>
        <Card pad={14}>
          <Stat label="Min net load" value={day.summary.min.toFixed(2)} unit="kW"
                sub={day.summary.min < 0 ? 'net export' : 'always importing'}
                color={day.summary.min < 0 ? 'var(--d-solar)' : undefined} />
        </Card>
        <Card pad={14}>
          <Stat label="Load factor" value={(day.summary.kwh / 24 / day.summary.peak).toFixed(2)}
                sub="avg ÷ peak" />
        </Card>
      </div>

      {yearData && (
        <Card pad={0} style={{ overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid var(--line)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Icon name="thermo" size={17} style={{ color: 'var(--d-temp)' }} />
              <div style={{ fontSize: 13.5, fontWeight: 600 }}>Annual daily-peak envelope</div>
            </div>
            <span className="mono" style={{ fontSize: 10.5, color: 'var(--ink-3)' }}>365 days · peak kW vs temp °F</span>
          </div>
          <div style={{ padding: '10px 12px 6px' }}>
            <SeasonalChart year={yearData.days} height={170} />
          </div>
        </Card>
      )}
    </div>
  );
}

export function GeneratorScreen() {
  const { data: meta } = useMetadata();
  const ARCHETYPES = meta
    ? meta.archetypes.map(a => ({ value: a.id, label: `${a.label} · ${a.sqft.toLocaleString()} ft²` }))
    : FALLBACK_ARCHETYPES;
  const FUELS = meta
    ? meta.fuels.map(f => ({ value: f.id, label: f.label }))
    : FALLBACK_FUELS;

  const [cfg, setCfg] = useState({
    archetype: 'colonial', fuel: 'oil', month: 0, tempF: null, dayType: 'weekday',
    ev: false, evManaged: true, solar: false, battery: false, n: 100, seed: 7,
  });
  const [generating, setGenerating] = useState(false);
  const [animKey, setAnimKey] = useState(0);
  const set = patch => setCfg(c => ({ ...c, ...patch }));

  const dayParams = useMemo(() => ({
    archetype: cfg.archetype, fuel: cfg.fuel, month: cfg.month,
    temp_f: cfg.tempF, has_ev: cfg.ev, has_solar: cfg.solar,
    has_battery: cfg.battery, has_ev_managed: cfg.evManaged,
    day_type: cfg.dayType, seed: cfg.seed,
  }), [cfg.archetype, cfg.fuel, cfg.month, cfg.tempF, cfg.ev, cfg.solar, cfg.battery, cfg.evManaged, cfg.dayType, cfg.seed]);

  const yearParams = useMemo(() => ({
    archetype: cfg.archetype, fuel: cfg.fuel,
    has_ev: cfg.ev, has_solar: cfg.solar, has_battery: cfg.battery,
    has_ev_managed: cfg.evManaged,
  }), [cfg.archetype, cfg.fuel, cfg.ev, cfg.solar, cfg.battery, cfg.evManaged]);

  const { data: dayData } = useGenerateDay(dayParams);
  const { data: yearData } = useGenerateYear(yearParams);

  function handleGenerate() {
    setGenerating(true);
    setTimeout(() => { setGenerating(false); setAnimKey(k => k + 1); }, 620);
  }

  return (
    <div className="os-fade gen-layout" style={{ display: 'grid', gridTemplateColumns: '330px 1fr', gap: 18, alignItems: 'start' }}>
      <div style={{ position: 'sticky', top: 76 }}>
        <Card pad={18} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <Icon name="chip" size={17} style={{ color: 'var(--accent)' }} />
            <div style={{ fontSize: 13.5, fontWeight: 600 }}>Conditioning</div>
            <Badge tone="accent">CVAE v1.0</Badge>
          </div>
          <ConfigPanel cfg={cfg} set={set} onGenerate={handleGenerate} generating={generating}
                       archetypes={ARCHETYPES} fuels={FUELS} />
          <CodeBlock tokens={snippetTokens(cfg)} />
        </Card>
      </div>
      <ResultPanel dayData={dayData} yearData={yearData} cfg={cfg} animKey={animKey} />
    </div>
  );
}
