'use client';

export default function GeneratedFileCard({ file }) {
  const ext = (file.ext || '').toLowerCase();
  const icon = {
    '.xlsx': 'fa-file-excel', '.xls': 'fa-file-excel',
    '.docx': 'fa-file-word', '.doc': 'fa-file-word',
    '.pptx': 'fa-file-powerpoint', '.ppt': 'fa-file-powerpoint',
    '.pdf': 'fa-file-pdf',
    '.html': 'fa-code', '.htm': 'fa-code',
    '.png': 'fa-file-image', '.jpg': 'fa-file-image', '.jpeg': 'fa-file-image', '.gif': 'fa-file-image', '.svg': 'fa-file-image',
    '.csv': 'fa-file-csv',
    '.json': 'fa-file-code',
    '.txt': 'fa-file-alt',
    '.md': 'fa-file-alt',
    '.py': 'fa-file-code',
    '.js': 'fa-file-code',
    '.css': 'fa-file-code',
  }[ext] || 'fa-file';

  const label = {
    '.xlsx': 'Excel', '.xls': 'Excel',
    '.docx': 'Word', '.doc': 'Word',
    '.pptx': 'PowerPoint', '.ppt': 'PowerPoint',
    '.pdf': 'PDF',
    '.html': 'HTML', '.htm': 'HTML',
    '.png': 'Bild', '.jpg': 'Bild', '.jpeg': 'Bild', '.gif': 'Bild', '.svg': 'Bild',
    '.csv': 'CSV',
    '.json': 'JSON',
    '.txt': 'Text',
    '.md': 'Markdown',
    '.py': 'Python',
    '.js': 'JavaScript',
    '.css': 'CSS',
  }[ext] || 'Datei';

  const isImagePreview = ['.png', '.jpg', '.jpeg', '.gif', '.svg'].includes(ext);
  const isHtmlPreview = ext === '.html' || ext === '.htm';
  const previewUrl = file.url;

  return (
    <div className="generated-file-card">
      <div className="generated-file-icon">
        <i className={`fas ${icon}`}></i>
      </div>
      <div className="generated-file-info">
        <span className="generated-file-name">{file.name}</span>
        <span className="generated-file-meta">{label} &middot; {file.size > 1024 ? `${(file.size / 1024).toFixed(1)} KB` : `${file.size} B`}</span>
      </div>
      <div className="generated-file-actions">
        <a href={previewUrl} className="btn primary btn-sm" download={file.name}>
          <i className="fas fa-download"></i>
        </a>
      </div>
      {isImagePreview && (
        <img src={previewUrl} alt={file.name} className="generated-file-preview" />
      )}
      {isHtmlPreview && (
        <iframe src={previewUrl} className="generated-file-iframe" title={file.name} sandbox="allow-scripts" />
      )}
    </div>
  );
}
