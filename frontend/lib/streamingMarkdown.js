function _countDelim(line, delim) {
  return (line.split(delim).length - 1);
}

function _balancePair(line, delim) {
  if (_countDelim(line, delim) % 2 === 1) {
    return line.replace(delim, '');
  }
  return line;
}

function _balanceLastLine(line) {
  let s = line;
  s = _balancePair(s, '$$');
  s = _balancePair(s, '**');
  s = _balancePair(s, '__');
  s = _balancePair(s, '~~');
  s = _balancePair(s, '`');
  s = _balancePair(s, '$');
  if (!/^\s*[*_]\s/.test(s)) {
    s = _balancePair(s, '*');
    s = _balancePair(s, '_');
  }
  return s;
}

export function prepareStreamingMarkdown(text) {
  if (!text) return text;

  const lines = text.split('\n');
  let inFence = false;
  for (let i = 0; i < lines.length; i++) {
    if (/^\s*```/.test(lines[i])) inFence = !inFence;
  }

  let result = text;
  if (inFence) {
    result = result + '\n```';
  } else {
    const idx = result.lastIndexOf('\n');
    const before = idx >= 0 ? result.slice(0, idx + 1) : '';
    const lastLine = idx >= 0 ? result.slice(idx + 1) : result;
    result = before + (/^\s*```/.test(lastLine) ? lastLine : _balanceLastLine(lastLine));
  }
  return result;
}
