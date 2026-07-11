'use client';

export default function PhotoPreviewModal({ photoPreview, onClose }) {
  if (!photoPreview.open) return null;
  const externalUrl = photoPreview.sourceUrl || photoPreview.immichUrl || '';
  const externalLabel = photoPreview.immichUrl ? 'In Immich öffnen' : 'Quelle öffnen';
  return (
    <div className="image-modal-overlay" onClick={onClose}>
      <div className="image-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="image-modal-close" onClick={onClose} aria-label="Vorschau schließen">×</button>
        <div className="image-modal-title">{photoPreview.title || 'Vorschau'}</div>
        <img src={photoPreview.thumbnailUrl} alt={photoPreview.title || 'Vorschau'} className="image-modal-preview" loading="lazy" />
        <div className="image-modal-actions">
          {photoPreview.sourceUrl && (
            <a className="btn primary" href={photoPreview.sourceUrl} target="_blank" rel="noopener noreferrer">
              <i className="fas fa-external-link-alt" style={{marginRight:6}}></i>Bild in Immich anzeigen
            </a>
          )}
          {externalUrl && externalUrl !== photoPreview.sourceUrl && (
            <a className="btn" href={externalUrl} target="_blank" rel="noopener noreferrer">{externalLabel}</a>
          )}
        </div>
      </div>
    </div>
  );
}
