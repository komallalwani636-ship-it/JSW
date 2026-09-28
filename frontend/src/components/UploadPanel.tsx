import { useCallback, useRef, useState } from "react";
import { useUpload } from "../api/hooks";
import type { ParseSummary } from "../api/types";
import { ParseSummaryModal } from "./ParseSummaryModal";

interface UploadPanelProps {
  onUploadComplete?: (uploadId: number, summary: ParseSummary) => void;
  onGenerate?: (uploadId: number) => void;
  generating?: boolean;
  disabled?: boolean;
}

const ACCEPTED = [".xls", ".xlsx"];

function isValidFile(file: File): boolean {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  return ACCEPTED.includes(ext);
}

export function UploadPanel({
  onUploadComplete,
  onGenerate,
  generating,
  disabled,
}: UploadPanelProps) {
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modalData, setModalData] = useState<{ uploadId: number; summary: ParseSummary } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useUpload();

  const processFile = useCallback(
    async (file: File) => {
      if (!isValidFile(file)) {
        setError("Only .xls and .xlsx files are accepted.");
        return;
      }
      setError(null);
      setLoading(true);
      try {
        const result = await upload.mutateAsync(file);
        setModalData({ uploadId: result.upload_id, summary: result.parse_summary });
        onUploadComplete?.(result.upload_id, result.parse_summary);
      } catch {
        setError("Upload failed. Please try again.");
      } finally {
        setLoading(false);
      }
    },
    [upload, onUploadComplete],
  );

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) processFile(file);
    e.target.value = "";
  }

  if (disabled) {
    return null;
  }

  return (
    <>
      <div
        className={`upload-panel ${dragOver ? "drag-over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xls,.xlsx"
          onChange={handleFileChange}
          disabled={loading}
        />
        {loading ? (
          <p>Uploading and parsing…</p>
        ) : (
          <>
            <p><strong>Drop HR Stock Report here</strong></p>
            <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>
              or click to browse (.xls / .xlsx)
            </p>
          </>
        )}
        {error && <p className="error-msg">{error}</p>}
      </div>

      {modalData && (
        <ParseSummaryModal
          summary={modalData.summary}
          uploadId={modalData.uploadId}
          onClose={() => setModalData(null)}
          onGenerate={(id) => {
            onGenerate?.(id);
            setModalData(null);
          }}
          generating={generating}
          canGenerate={Boolean(onGenerate)}
        />
      )}
    </>
  );
}
