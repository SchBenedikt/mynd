import nextVitals from 'eslint-config-next/core-web-vitals';

const eslintConfig = [
  {
    ignores: ['.next/**', 'out/**', 'node_modules/**'],
  },
  ...nextVitals,
  {
    rules: {
      'no-unused-vars': ['error', {
        args: 'none',
        caughtErrors: 'none',
        destructuredArrayIgnorePattern: '^_',
      }],
      'no-undef': 'error',
      'react-hooks/exhaustive-deps': 'error',
      'no-console': 'off',
      'react/no-unescaped-entities': 'off',
      '@next/next/no-img-element': 'off',
      // These React Compiler rules require broader state-management refactors.
      // Keep the established hooks correctness rules enabled in the meantime.
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/purity': 'off',
      'react-hooks/immutability': 'off',
    },
  },
];

export default eslintConfig;
