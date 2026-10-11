import { useState, useEffect } from 'react';
import { Icon, Logo, Btn } from './components';
import { GeneratorScreen } from './screens/GeneratorScreen';
import { ValidationScreen } from './screens/ValidationScreen';
import { DatasetScreen } from './screens/DatasetScreen';

const NAV = [
  { id: 'generate', label: 'Generator', icon: 'bolt' },
  { id: 'validate', label: 'Validation', icon: 'shield' },
  { id: 'dataset',  label: 'Dataset',    icon: 'grid' },
];

function TopBar({ tab, setTab, dark, setDark }) {
  return (
    <div style={{
      position: 'sticky', top: 0, zIndex: 50,
      background: 'color-mix(in srgb, var(--paper) 88%, transparent)',
      backdropFilter: 'blur(10px)', borderBottom: '1px solid var(--line)',
    }}>
      <div style={{
        maxWidth: 1320, margin: '0 auto', padding: '0 24px', height: 58,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 26 }}>
          <Logo />
          <nav style={{ display: 'flex', gap: 2 }}>
            {NAV.map(n => (
              <button key={n.id} onClick={() => setTab(n.id)} style={{
                display: 'inline-flex', alignItems: 'center', gap: 7,
                padding: '7px 13px', fontSize: 13, fontWeight: tab === n.id ? 600 : 500,
                cursor: 'pointer', fontFamily: 'var(--font-ui)', border: 'none',
                borderRadius: 'var(--radius-sm)',
                color: tab === n.id ? 'var(--ink)' : 'var(--ink-2)',
                background: tab === n.id ? 'var(--surface-2)' : 'transparent',
                transition: 'all .14s',
              }}>
                <Icon name={n.icon} size={15} style={{ color: tab === n.id ? 'var(--accent)' : 'var(--ink-3)' }} />
                {n.label}
              </button>
            ))}
          </nav>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 7, height: 7, borderRadius: 99, background: 'var(--ok)' }} />
            LF Energy · OpenSynth
          </span>
          <Btn kind="secondary" size="sm" icon="book">Docs</Btn>
          <button onClick={() => setDark(!dark)} title="Toggle theme" style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: 34, height: 34, cursor: 'pointer', border: '1px solid var(--line)',
            borderRadius: 'var(--radius-sm)', background: 'var(--surface)', color: 'var(--ink-2)',
          }}>
            <Icon name={dark ? 'sun' : 'moon'} size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

function PageHead({ tab }) {
  const meta = {
    generate: {
      t: 'Conditional generator',
      d: 'Synthesize realistic New England AMI load profiles on demand — conditioned on housing archetype, heating fuel, weather, and on-site DER.',
    },
    validate: {
      t: 'Validation suite',
      d: 'Every release is gated against independently verifiable regional statistics before it ships. Facts come from the data; the model only shapes the curve.',
    },
    dataset: {
      t: 'Dataset & export',
      d: 'The static v1.0 release: 10,000 synthetic meters across 96 archetype base types, openly licensed and ready for download.',
    },
  }[tab];
  return (
    <div style={{ marginBottom: 22, maxWidth: 760 }}>
      <div className="mono" style={{
        fontSize: 11, letterSpacing: '0.06em', color: 'var(--accent)',
        textTransform: 'uppercase', marginBottom: 9,
      }}>
        OpenSynth New England
      </div>
      <h1 style={{ fontSize: 27, fontWeight: 600, letterSpacing: '-0.025em', marginBottom: 9 }}>{meta.t}</h1>
      <p style={{ fontSize: 14, color: 'var(--ink-2)', lineHeight: 1.6, margin: 0, textWrap: 'pretty' }}>{meta.d}</p>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState('generate');
  const [dark, setDark] = useState(() => {
    const stored = localStorage.getItem('opensynth-dark');
    if (stored !== null) return stored === 'true';
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    localStorage.setItem('opensynth-dark', String(dark));
  }, [dark]);

  return (
    <div style={{ minHeight: '100vh' }}>
      <TopBar tab={tab} setTab={setTab} dark={dark} setDark={setDark} />
      <main style={{ maxWidth: 1320, margin: '0 auto', padding: '26px 24px 80px' }}>
        <PageHead tab={tab} />
        {tab === 'generate' && <GeneratorScreen />}
        {tab === 'validate' && <ValidationScreen />}
        {tab === 'dataset' && <DatasetScreen />}
      </main>
    </div>
  );
}
