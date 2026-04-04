'use client';

import { useState, useEffect } from 'react';

const safeReadJson = async (response) => {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { success: false, error: text };
  }
};

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
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [timePeriod, setTimePeriod] = useState('morning');
  const [isPersonalized, setIsPersonalized] = useState(false);

  useEffect(() => {
    fetchSuggestions();

    // Refresh suggestions every 30 minutes to adapt to time changes
    const interval = setInterval(fetchSuggestions, 30 * 60 * 1000);

    return () => clearInterval(interval);
  }, [language, chatHistory?.length]);

  const fetchSuggestions = async () => {
    try {
      setLoading(true);

      const response = await fetch('/api/suggestions/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: username || 'default',
          language: language || 'de',
          chatHistory: chatHistory || []
        }),
      });

      const data = await safeReadJson(response);

      if (response.ok && data.success && data.suggestions) {
        setSuggestions(data.suggestions);
        setTimePeriod(data.time_period || 'morning');
        setIsPersonalized(data.personalized || false);
      } else {
        // Fallback to default suggestions if API fails
        setSuggestions(getDefaultSuggestions(language));
      }
    } catch (error) {
      console.error('Error fetching suggestions:', error);
      setSuggestions(getDefaultSuggestions(language));
    } finally {
      setLoading(false);
    }
  };

  const getDefaultSuggestions = (lang) => {
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
