// SF Symbols 风格内联 SVG 图标
// 所有尺寸统一: viewBox="0 0 24 24"，stroke 风格

export const ICONS = {
  folder: '<svg viewBox="0 0 24 24"><path d="M2 6a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6z"/></svg>',
  file: '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"/><path d="M14 2v6h6"/></svg>',
  python: '<svg viewBox="0 0 24 24"><path d="M12 2c-4 0-5 1.5-5 4v3h5v1H7c-2.5 0-4.5 1.5-4.5 5s1.5 5 4.5 5h2v-4c0-2.5 2-4.5 4.5-4.5h4c2.5 0 4.5-2 4.5-4.5V6c0-2.5-2-4-5-4zm-3 3c.8 0 1.5.7 1.5 1.5S9.8 8 9 8s-1.5-.7-1.5-1.5S8.2 5 9 5z"/><path d="M15 22c4 0 5-1.5 5-4v-3h-5v-1h7c2.5 0 4.5-1.5 4.5-5s-2-5-4.5-5h-2v4c0 2.5-2 4.5-4.5 4.5h-4C8.5 12 6.5 14 6.5 16.5V18c0 2.5 2 4 5 4zm3-3c-.8 0-1.5-.7-1.5-1.5S17.2 16 18 16s1.5.7 1.5 1.5S18.8 19 18 19z"/></svg>',
  markdown: '<svg viewBox="0 0 24 24"><path d="M3 5h18v14H3V5z"/><path d="M8 15V9l3 3 3-3v6"/></svg>',
  brain: '<svg viewBox="0 0 24 24"><path d="M12 4a4 4 0 0 1 4 4c0 1.1-.5 2.1-1.2 2.8.7.5 1.2 1.3 1.2 2.2a3 3 0 0 1-3 3"/><path d="M12 4a4 4 0 0 0-4 4c0 1.1.5 2.1 1.2 2.8-.7.5-1.2 1.3-1.2 2.2a3 3 0 0 0 3 3"/><path d="M8 15a3 3 0 0 0 3 3h2a3 3 0 0 0 3-3"/><path d="M9 10h6"/></svg>',
  shell: '<svg viewBox="0 0 24 24"><polyline points="4 7 10 12 4 17"/><line x1="13" y1="17" x2="20" y2="17"/></svg>',
  book: '<svg viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
  tag: '<svg viewBox="0 0 24 24"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>',
  play: '<svg viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
  save: '<svg viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>',
  chat: '<svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  close: '<svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
  chevron: '<svg viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"/></svg>',
  refresh: '<svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>',
  about: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
  folderOpen: '<svg viewBox="0 0 24 24"><path d="M2 6a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v2H2V6z"/><path d="M2 10h20l-3 8H5l-3-8z"/></svg>',
  settings: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
};

export function icon(name, cls = '') {
  return `<span class="sf ${cls}">${ICONS[name] || ''}</span>`;
}

export function iconFile(name) {
  if (!name) return icon('file');
  if (name.endsWith('.py')) return icon('python');
  if (name.endsWith('.md')) return icon('markdown');
  return icon('file');
}
