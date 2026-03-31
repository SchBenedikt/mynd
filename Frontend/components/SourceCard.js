'use client';

/**
 * SourceCard component for displaying source references
 * Shows where the AI retrieved information from (files, calendar events, todos, etc.)
 */
export default function SourceCard({ source }) {
  const {
    source: sourceName,
    source_type,
    path,
    content_preview,
    similarity_score,
  } = source;

  // Determine icon based on source type
  const getIcon = () => {
    switch (source_type) {
      case 'calendar':
        return '📅';
      case 'todo':
        return '✓';
      case 'photo':
      case 'image':
        return '🖼️';
      case 'file':
      default:
        return '📄';
    }
  };

  // Generate link based on source type
  const getLink = () => {
    // For now, we'll keep links simple
    // In the future, these could link to Nextcloud or other external resources
    if (source_type === 'calendar') {
      return null; // Calendar events don't have direct links yet
    }
    if (source_type === 'todo') {
      return null; // Todo items don't have direct links yet
    }
    if (path && path !== 'calendar' && path !== 'todos') {
      // File path - could link to file in Nextcloud
      return null; // For now, just show the path
    }
    return null;
  };

  const link = getLink();
  const icon = getIcon();

  return (
    <div className="source-card">
      <div className="source-header">
        <span className="source-icon">{icon}</span>
        <div className="source-title-container">
          <span className="source-title">
            {link ? (
              <a href={link} target="_blank" rel="noopener noreferrer" className="source-link">
                {sourceName}
              </a>
            ) : (
              sourceName
            )}
          </span>
          {path && path !== 'calendar' && path !== 'todos' && (
            <span className="source-path">{path}</span>
          )}
        </div>
        {similarity_score > 0 && similarity_score < 1 && (
          <span className="source-score">
            {Math.round(similarity_score * 100)}%
          </span>
        )}
      </div>
      {content_preview && (
        <div className="source-preview">
          {content_preview}
        </div>
      )}
    </div>
  );
}
