import type { ParseSummary } from "../api/types";

interface ParseSummaryModalProps {
  summary: ParseSummary;
  uploadId: number;
  onClose: () => void;
  onGenerate: (uploadId: number) => void;
  generating?: boolean;
  canGenerate?: boolean;
}

export function ParseSummaryModal({
  summary,
  uploadId,
  onClose,
  onGenerate,
  generating,
  canGenerate = true,
}: ParseSummaryModalProps) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Parse Summary</h2>
        <dl style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "0.5rem" }}>
          <dt>Total rows read</dt><dd>{summary.total_rows}</dd>
          <dt>Eligible coils</dt><dd>{summary.eligible_count}</dd>
          <dt>APL7 coils</dt><dd>{summary.apl7_count}</dd>
          <dt>Excluded — product</dt><dd>{summary.excluded_product}</dd>
          <dt>Excluded — act path / prev unit</dt><dd>{summary.excluded_act_path}</dd>
          <dt>Excluded — status</dt><dd>{summary.excluded_status}</dd>
          <dt>Excluded — closed orders</dt><dd>{summary.excluded_closed}</dd>
        </dl>

        {summary.parse_warnings.length > 0 && (
          <>
            <h3>Parse Warnings ({summary.parse_warnings.length})</h3>
            <ul style={{ fontSize: "0.875rem", maxHeight: "200px", overflowY: "auto" }}>
              {summary.parse_warnings.map((w, i) => (
                <li key={i}>
                  Row {w.row}, {w.column}: {w.message}
                </li>
              ))}
            </ul>
          </>
        )}

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
          {canGenerate && (
            <button
              className="btn"
              disabled={generating}
              onClick={() => onGenerate(uploadId)}
            >
              {generating ? "Generating…" : "Generate Schedule"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
