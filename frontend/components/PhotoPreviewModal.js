'use client';

export default function PhotoPreviewModal({ photoPreview, onClose }) {
  if (!photoPreview.open) return null;
  const isImmichSource = photoPreview.sourceUrl?.startsWith('/api/immich/');
  const immichWebUrl = photoPreview.immichUrl || '';
  return (
    <div className="image-modal-overlay" onClick={onClose}>
      <div className="image-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="image-modal-close" onClick={onClose} aria-label="Vorschau schließen">×</button>
        <div className="image-modal-title">{photoPreview.title || 'Vorschau'}</div>
        <img src={photoPreview.thumbnailUrl} alt={photoPreview.title || 'Vorschau'} className="image-modal-preview" loading="lazy" />
        <div className="image-modal-actions">
          {photoPreview.sourceUrl && (
            <a className="btn primary" href={photoPreview.sourceUrl} target="_blank" rel="noopener noreferrer">
              <i className="fas fa-external-link-alt" style={{marginRight:6}}></i>
              {isImmichSource ? 'Original öffnen' : 'Quelle öffnen'}
            </a>
          )}
          {immichWebUrl && immichWebUrl !== photoPreview.sourceUrl && (
            <a className="btn" href={immichWebUrl} target="_blank" rel="noopener noreferrer">
              <i className="fas fa-images" style={{marginRight:6}}></i>In Immich öffnen
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
