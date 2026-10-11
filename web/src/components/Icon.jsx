export default function Icon({ name, size = 16, sw = 1.7, style }) {
  const p = { fill: 'none', stroke: 'currentColor', strokeWidth: sw, strokeLinecap: 'round', strokeLinejoin: 'round' };
  const paths = {
    bolt: <path {...p} d="M13 3 4 14h7l-1 7 9-11h-7z" />,
    grid: <g {...p}><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></g>,
    shield: <g {...p}><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" /><path d="M9 12l2 2 4-4" /></g>,
    sun: <g {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19" /></g>,
    moon: <path {...p} d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" />,
    copy: <g {...p}><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h8" /></g>,
    download: <g {...p}><path d="M12 3v12M7 11l5 5 5-5" /><path d="M4 19h16" /></g>,
    refresh: <g {...p}><path d="M4 12a8 8 0 0 1 14-5.3L21 9" /><path d="M21 4v5h-5" /><path d="M20 12a8 8 0 0 1-14 5.3L3 15" /><path d="M3 20v-5h5" /></g>,
    play: <path {...p} d="M7 4v16l13-8z" />,
    chevron: <path {...p} d="M9 6l6 6-6 6" />,
    chevdown: <path {...p} d="M6 9l6 6 6-6" />,
    car: <g {...p}><path d="M5 16l1.5-5A2 2 0 0 1 8.4 9.5h7.2a2 2 0 0 1 1.9 1.5L19 16" /><path d="M3 16h18v3h-2v1h-2v-1H7v1H5v-1H3z" /><circle cx="7.5" cy="16.5" r="0" /></g>,
    solar: <g {...p}><circle cx="12" cy="12" r="3.5" /><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" /></g>,
    home: <path {...p} d="M4 11l8-7 8 7M6 10v9h12v-9" />,
    flame: <path {...p} d="M12 3c1 3-2 4-2 7a2 2 0 0 0 4 0c0-1 1 0 1 2a3.5 3.5 0 0 1-7 0c0-4 4-5 4-9z" />,
    battery: <g {...p}><rect x="3" y="8" width="16" height="9" rx="2" /><path d="M21 11v3" /><path d="M9 10l-1.5 3.5h2L8 16" /></g>,
    book: <g {...p}><path d="M5 4h11a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2z" /><path d="M5 18a2 2 0 0 1 2-2h11" /></g>,
    layers: <g {...p}><path d="M12 3l9 5-9 5-9-5z" /><path d="M3 13l9 5 9-5" /></g>,
    check: <path {...p} d="M5 12l4 4 10-10" />,
    x: <path {...p} d="M6 6l12 12M18 6L6 18" />,
    chip: <g {...p}><rect x="6" y="6" width="12" height="12" rx="2" /><path d="M9 1.5v3M15 1.5v3M9 19.5v3M15 19.5v3M1.5 9h3M1.5 15h3M19.5 9h3M19.5 15h3" /></g>,
    wave: <path {...p} d="M3 12c2 0 2-5 4-5s2 9 4 9 2-9 4-9 2 5 4 5" />,
    thermo: <g {...p}><path d="M14 14.5V5a2 2 0 0 0-4 0v9.5a3.5 3.5 0 1 0 4 0z" /></g>,
    arrow: <path {...p} d="M5 12h14M13 6l6 6-6 6" />,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" style={{ flexShrink: 0, ...style }}>{paths[name]}</svg>;
}
