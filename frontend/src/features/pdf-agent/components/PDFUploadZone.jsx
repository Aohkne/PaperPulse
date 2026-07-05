import { useRef, useState } from 'react';
import { Icon } from '@iconify/react';

const ACCEPT = '.pdf,.tex,.zip';

const PDFUploadZone = ({ onFile, disabled = false }) => {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFiles = (files) => {
    if (disabled) return;
    const file = files?.[0];
    if (file) onFile(file);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
      onClick={() => {
        if (!disabled) inputRef.current?.click();
      }}
      style={{
        flex: 1,
        margin: '32px',
        border: `2px dashed ${dragOver ? 'var(--color-paper-mid)' : 'var(--color-paper-light)'}`,
        borderRadius: '10px',
        background: 'var(--color-paper-surface)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '14px',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        transition: 'all 0.15s',
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        disabled={disabled}
        style={{ display: 'none' }}
        onChange={(e) => handleFiles(e.target.files)}
      />
      <Icon
        icon="mdi:file-upload-outline"
        style={{ width: 48, height: 48, color: 'var(--color-paper-mid)' }}
      />
      <div
        style={{
          fontFamily: "'Newsreader', serif",
          fontSize: '18px',
          color: 'var(--color-paper-dark)',
          fontWeight: 600,
        }}
      >
        {disabled
          ? 'Quota used up for this period'
          : 'Drag and drop a file here, or click to select'}
      </div>
      <div
        style={{
          fontFamily: "'Newsreader', serif",
          fontSize: '15px',
          color: 'var(--color-paper-mid)',
        }}
      >
        Supports .pdf, .tex, .zip (Overleaf project export) — up to 20MB
      </div>
    </div>
  );
};

export default PDFUploadZone;
