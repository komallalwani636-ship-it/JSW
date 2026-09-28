import { useState } from "react";
import type { ViolationDetail } from "../api/types";

interface FinalizeModalProps {
  violations: ViolationDetail[];
  onConfirm: (overrideReason?: string) => void;
  onCancel: () => void;
  submitting?: boolean;
}

export function FinalizeModal({
  violations,
  onConfirm,
  onCancel,
  submitting,
}: FinalizeModalProps) {
  const [reason, setReason] = useState("");
  const needsReason = violations.length > 0;
  const canConfirm = !needsReason || reason.trim().length > 0;

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Finalize Schedule</h2>
        <p>
          Finalizing will lock this schedule from further edits.
          {needsReason && (
            <> This schedule has <strong>{violations.length}</strong> violation(s) and requires an override reason.</>
          )}
        </p>

        {needsReason && (
          <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
            Override reason (required)
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              style={{ padding: "0.5rem", border: "1px solid var(--border)", borderRadius: "4px" }}
            />
          </label>
        )}

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button
            className="btn"
            disabled={!canConfirm || submitting}
            onClick={() => onConfirm(needsReason ? reason.trim() : undefined)}
          >
            {submitting ? "Finalizing…" : "Confirm Finalize"}
          </button>
        </div>
      </div>
    </div>
  );
}
