'use client';

import { useState, useEffect } from 'react';
import { apiFetch, getApiBase } from '../lib/api';

const safeReadJson = async (response) => {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { success: false, error: text };
  }
};

// Default suggestions helper (declared at module scope so it's hoisted/available)
function getDefaultSuggestions(lang) {
  const defaults = {
    de: [
      'Was steht heute auf meinem Kalender?',
      'Zeige mir meine Aufgaben für heute',
      'Was ist neu in meinen Dateien?'
    ],
    en: [
      'What\'s on my calendar today?',
      'Show me my tasks for today',
      'What\'s new in my files?'
    ]
  };
  return defaults[lang] || defaults.en;
}

/**
 * SuggestionsPanel component displays AI-generated query suggestions
 * that adapt based on time of day and user behavior patterns.
 */
export default function SuggestionsPanel({
  language,
  username,
  chatHistory,
  onSuggestionClick,
  t
}) {
  // Start with sensible defaults so UI is immediately responsive
  const [suggestions, setSuggestions] = useState(getDefaultSuggestions(language || 'de'));
  const [loading, setLoading] = useState(false);
  const [timePeriod, setTimePeriod] = useState('morning');
  const [isPersonalized, setIsPersonalized] = useState(false);

  useEffect(() => {
    // Fetch fresh suggestions in background, but keep defaults shown for fast UX.
    fetchSuggestions();

    // Refresh suggestions every 30 minutes to adapt to time changes
    const interval = setInterval(fetchSuggestions, 30 * 60 * 1000);

    return () => clearInterval(interval);
  }, [language, chatHistory?.length]);

  const fetchSuggestions = async () => {
    // Perform fetch with 1s client-side timeout; keep defaults if slow/failing
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    try {
      setLoading(true);

      const response = await apiFetch('/api/suggestions/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: username || 'default',
          language: language || 'de',
          chatHistory: chatHistory || []
        }),
        signal: controller.signal
      });

      const data = await safeReadJson(response);

      if (response.ok && data.success && Array.isArray(data.suggestions)) {
        const filtered = filterSuggestions(data.suggestions, language || 'de');
        if (filtered.length > 0) {
          setSuggestions(filtered);
        }
        setTimePeriod(data.time_period || 'morning');
        setIsPersonalized(data.personalized || false);
      }
      // else: keep existing defaults
    } catch (error) {
      // network error or timeout - keep defaults
      console.debug('Suggestions fetch skipped (error/timeout):', error?.name || error);
    } finally {
      clearTimeout(timeout);
      setLoading(false);
    }
  };

  // Filter out casual/personal prompts we don't want suggested
  const filterSuggestions = (items, lang) => {
    if (!Array.isArray(items)) return [];
    const bannedPatterns = [
      // German
      /\b(hast du schon\s+pläne|was möchtest du|was machst du|willst du heute)\b/i,
      /\b(heute nachmittag|heute abend|was machst du heute)\b/i,
      /\b(hast du vor|hast du schon vor)\b/i,
      // English
      /\b(have you already|what are you planning|what are you doing today|this evening)\b/i
    ];

    return items.filter((s) => {
      if (!s || typeof s !== 'string') return false;
      for (const re of bannedPatterns) {
        if (re.test(s)) return false;
      }
      // discard extremely short or vague social prompts
      if (s.length < 10) return false;
      return true;
    });
  };

  

  const handleSuggestionClick = (suggestion) => {
    if (onSuggestionClick) {
      onSuggestionClick(suggestion);
    }
  };

  if (loading && suggestions.length === 0) {
    return (
      <div className="suggestions-panel loading">
        <div className="suggestions-shimmer"></div>
      </div>
    );
  }

  if (!suggestions || suggestions.length === 0) {
    return null;
  }

  return (
    <div className="suggestions-panel">
      <div className="suggestions-header">
        <i className="fas fa-lightbulb"></i>
        <span>{t('suggestions') || 'Vorschläge'}</span>
        {isPersonalized && (
          <span className="personalized-badge" title={t('personalizedSuggestions')}>
            <i className="fas fa-user"></i>
          </span>
        )}
      </div>
      <div className="suggestions-list">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            className="suggestion-chip"
            onClick={() => handleSuggestionClick(suggestion)}
            style={{ animationDelay: `${index * 0.1}s` }}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}
