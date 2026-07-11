'use client';

import { Component } from 'react';

const ERROR_STYLES = {
  container: {
    padding: '2rem',
    margin: '1rem',
    borderRadius: '12px',
    background: 'var(--surface-card, #1a1a2e)',
    border: '1px solid var(--border-color, #e11d48)',
    textAlign: 'center',
  },
  icon: { fontSize: '2.5rem', marginBottom: '0.5rem' },
  title: { fontSize: '1.2rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary, #eee)' },
  detail: { fontSize: '0.85rem', color: 'var(--text-secondary, #999)', marginBottom: '1rem', whiteSpace: 'pre-wrap' },
  button: {
    padding: '0.5rem 1.2rem',
    borderRadius: '8px',
    border: 'none',
    background: 'var(--accent-color, #e11d48)',
    color: '#fff',
    cursor: 'pointer',
    fontSize: '0.9rem',
  },
};

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div style={ERROR_STYLES} role="alert">
          <div style={ERROR_STYLES.icon}>⚠️</div>
          <div style={ERROR_STYLES.title}>Something went wrong</div>
          <div style={ERROR_STYLES.detail}>
            {this.state.error?.message || 'An unexpected error occurred.'}
          </div>
          <button style={ERROR_STYLES.button} onClick={this.handleReset}>
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}