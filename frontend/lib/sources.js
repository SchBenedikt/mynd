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

  const origToNew = {};
  sources.forEach((s, i) => { origToNew[s.number] = i + 1; });

  return content.replace(/\((\d+)\)/g, (match, num) => {
    const n = origToNew[parseInt(num)];
    if (n) {
      return `[(${n})](${sources.find(s => s.number === parseInt(num))?.url || ''})`;
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
