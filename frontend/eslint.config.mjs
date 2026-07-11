const eslintConfig = [
  {
    rules: {
      'no-unused-vars': 'warn',
      'no-console': 'off',
      'react/no-unescaped-entities': 'off',
      '@next/next/no-img-element': 'off',
    },
    ignores: ['.next/**', 'node_modules/**'],
  },
];

export default eslintConfig;
