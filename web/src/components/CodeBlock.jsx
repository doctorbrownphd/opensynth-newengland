import { useState } from 'react';
import Btn from './Btn';

/**
 * CodeBlock accepts an array of tokens for safe rendering.
 * Each token is either a string (plain text) or { text, color } for colored spans.
 * No dangerouslySetInnerHTML — all content is rendered as safe React elements.
 */
export default function CodeBlock({ tokens, plainText, lang = 'python' }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    const text = plainText || (tokens || []).map(t => typeof t === 'string' ? t : t.text).join('');
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    });
  }

  return (
    <div style={{
      position: 'relative', background: 'var(--surface-2)', border: '1px solid var(--line)',
      borderRadius: 'var(--radius)', overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '7px 10px 7px 13px', borderBottom: '1px solid var(--line)', background: 'var(--surface-3)',
      }}>
        <span className="mono" style={{ fontSize: 10.5, color: 'var(--ink-3)', letterSpacing: '0.04em' }}>{lang}</span>
        <Btn kind="ghost" size="sm" icon={copied ? 'check' : 'copy'} onClick={copy}>{copied ? 'Copied' : 'Copy'}</Btn>
      </div>
      <pre className="mono" style={{
        margin: 0, padding: '13px 15px', fontSize: 12.5, lineHeight: 1.65,
        color: 'var(--ink)', overflowX: 'auto',
      }}>
        <code>
          {(tokens || []).map((t, i) =>
            typeof t === 'string'
              ? <span key={i}>{t}</span>
              : <span key={i} style={{ color: t.color }}>{t.text}</span>
          )}
        </code>
      </pre>
    </div>
  );
}
