import { useRef, useState } from 'react';
import { Icon } from '@iconify/react';

const ACCEPT = '.pdf,.tex,.zip';

const PDFUploadZone = ({ onFile }) => {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFiles = (files) => {
    const file = files?.[0];
    if (file) onFile(file);
  };

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
      onClick={() => inputRef.current?.click()}
      style={{
        flex: 1,
        margin: '32px',
        border: `2px dashed ${dragOver ? 'var(--color-paper-mid)' : 'var(--color-paper-light)'}`,
        borderRadius: '10px',
        background: dragOver ? 'var(--color-paper-surface)' : 'transparent',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '14px',
        cursor: 'pointer',
        transition: 'all 0.15s',
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        style={{ display: 'none' }}
        onChange={(e) => handleFiles(e.target.files)}
      />
      <Icon icon="mdi:file-upload-outline" style={{ width: 48, height: 48, color: 'var(--color-paper-light)' }} />
      <div style={{ fontFamily: 'Georgia, serif', fontSize: '16px', color: 'var(--color-paper-dark)', fontWeight: 600 }}>
        Drag and drop a file here, or click to select
      </div>
      <div style={{ fontFamily: 'Georgia, serif', fontSize: '13px', color: 'var(--color-paper-mid)' }}>
        Supports .pdf, .tex, .zip (Overleaf project export) — up to 20MB
      </div>
    </div>
  );
};

export default PDFUploadZone;
