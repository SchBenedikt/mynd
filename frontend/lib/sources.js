export function parseSourceList(content) {
  const lines = content.split('\n');
  const sourceLines = [];
  const bodyLines = [];
  let inSources = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (/^\(\d+\)\s*\[.*?\]\(.*?\)/.test(trimmed)) {
      inSources = true;
      sourceLines.push(trimmed);
    } else if (inSources && trimmed === '') {
      continue;
    } else {
      if (!inSources) {
        bodyLines.push(line);
      } else {
        bodyLines.push(line);
        inSources = false;
      }
    }
  }

  const sources = sourceLines.map(line => {
    const match = line.match(/^\((\d+)\)\s*\[(.*?)\]\((.*?)\)/);
    if (!match) return null;
    const [, num, domain, url] = match;
    return { number: parseInt(num), domain, url };
  }).filter(Boolean);

  return { sources };
}

export function embedCitations(content, sources) {
  if (!sources || sources.length === 0) return content;

  const byNumber = {};
  sources.forEach((s) => { byNumber[s.number] = s; });

  // Ersetze (N) im Text nur, wenn die Original-Nummer N in der Quellenliste
  // existiert. Wir nummerieren hier NICHT um, damit die Zitate im Text mit den
  // angezeigten Quellennummern übereinstimmen.
  return content.replace(/\((\d+)\)/g, (match, num) => {
    const n = parseInt(num);
    const src = byNumber[n];
    if (src) {
      return `[(${n})](${src.url || ''})`;
    }
    return match;
  });
}

export function stripSourceList(content) {
  const lines = content.split('\n');
  const bodyLines = [];
  let inSources = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (/^\(\d+\)\s*\[.*?\]\(.*?\)/.test(trimmed)) {
      inSources = true;
      continue;
    }
    if (inSources && trimmed === '') continue;
    bodyLines.push(line);
    inSources = false;
  }

  return bodyLines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

export function renumberSources(sources) {
  return sources.map((s, i) => ({ ...s, number: i + 1 }));
}
