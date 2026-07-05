const ESCAPE_MAP = {
  '\\': '\\textbackslash{}',
  '&': '\\&',
  '%': '\\%',
  $: '\\$',
  '#': '\\#',
  _: '\\_',
  '{': '\\{',
  '}': '\\}',
  '~': '\\textasciitilde{}',
  '^': '\\textasciicircum{}',
};

export const escapeLatex = (text) =>
  (text ?? '')
    .split('')
    .map((ch) => ESCAPE_MAP[ch] ?? ch)
    .join('');
