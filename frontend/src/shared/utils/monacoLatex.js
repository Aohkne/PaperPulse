// Monaco has no built-in LaTeX language — register a minimal Monarch tokenizer
// for commands, comments, braces and math delimiters.
export const registerLatexLanguage = (monaco) => {
  if (monaco.languages.getLanguages().some((l) => l.id === 'latex')) return;

  monaco.languages.register({ id: 'latex' });

  monaco.languages.setMonarchTokensProvider('latex', {
    tokenizer: {
      root: [
        [/%.*$/, 'comment'],
        [/\\[a-zA-Z]+/, 'keyword'],
        [/\$\$/, { token: 'string', next: '@displaymath' }],
        [/\$/, { token: 'string', next: '@inlinemath' }],
        [/[{}]/, 'delimiter.bracket'],
        [/[[\]]/, 'delimiter.square'],
      ],
      inlinemath: [
        [/\$/, { token: 'string', next: '@pop' }],
        [/[^$]+/, 'string'],
      ],
      displaymath: [
        [/\$\$/, { token: 'string', next: '@pop' }],
        [/[^$]+/, 'string'],
      ],
    },
  });

  monaco.languages.setLanguageConfiguration('latex', {
    comments: { lineComment: '%' },
    brackets: [
      ['{', '}'],
      ['[', ']'],
      ['(', ')'],
    ],
    autoClosingPairs: [
      { open: '{', close: '}' },
      { open: '[', close: ']' },
      { open: '$', close: '$' },
    ],
  });
};
