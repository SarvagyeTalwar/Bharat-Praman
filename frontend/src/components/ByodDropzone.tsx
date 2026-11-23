import React, { useRef, useState } from 'react';
import type { ByodDoc, UserProfile } from '../lib/types';
import { uploadByodDocument, uploadVaultDocument } from '../lib/api';

interface ByodDropzoneProps {
  user: UserProfile | null;
  docs: ByodDoc[];
  onAddDoc: (doc: ByodDoc) => void;
  onRemoveDoc: (index: number) => void;
  onOpenUpgrade: () => void;
}

export const ByodDropzone: React.FC<ByodDropzoneProps> = ({
  user,
  docs,
  onAddDoc,
  onRemoveDoc,
  onOpenUpgrade,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const isPremium = user?.tier === 'premium';

  const handleFiles = async (files: FileList | null) => {
    if (!files || !files.length) return;
    if (docs.length >= 3) {
      alert('Maximum of 3 files allowed.');
      return;
    }

    const file = files[0];
    if (file.size > 10 * 1024 * 1024) {
      alert('File exceeds 10 MB limit.');
      return;
    }

    try {
      if (isPremium) {
        setStatusMsg('Chunking and vectorizing into Neo4j...');
        const res = await uploadVaultDocument(file);
        onAddDoc(res);
      } else {
        setStatusMsg('Ingesting file for session...');
        const res = await uploadByodDocument(file);
        onAddDoc(res);
      }
    } catch (err: any) {
      alert(err.message || 'Upload failed');
    } finally {
      setStatusMsg(null);
    }
  };

  return (
    <div className="space-y-2">
      <div
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={`border border-dashed rounded px-4 py-3 text-xs transition-colors cursor-pointer flex items-center justify-between ${
          isDragging
            ? 'border-zinc-400 bg-zinc-900'
            : 'border-zinc-800 hover:border-zinc-700 bg-zinc-950'
        }`}
      >
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          accept=".pdf,.txt,.md,.csv,.json"
        />

        <div className="flex items-center gap-2">
          <span className="text-zinc-300">
            {statusMsg || 'Attach private document (Tender DPR, RFP, Notes)'}
          </span>
          <span className="text-zinc-600">·</span>
          <span className="text-zinc-500">PDF, TXT, CSV up to 10 MB</span>
        </div>

        <div className="flex items-center gap-2">
          {isPremium ? (
            <span className="font-mono text-[11px] text-zinc-400">Vault Grounded</span>
          ) : (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onOpenUpgrade();
              }}
              className="text-zinc-400 hover:text-zinc-200 transition-colors text-[11px]"
            >
              Upgrade to Persistent Vault
            </button>
          )}
        </div>
      </div>

      {docs.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {docs.map((doc, idx) => (
            <div
              key={doc.doc_id || idx}
              className="inline-flex items-center gap-2 px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-xs text-zinc-300"
            >
              <span className="truncate max-w-[220px]">{doc.filename || doc.title}</span>
              <button
                type="button"
                onClick={() => onRemoveDoc(idx)}
                className="text-zinc-500 hover:text-zinc-300 text-sm leading-none"
                title="Remove"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
