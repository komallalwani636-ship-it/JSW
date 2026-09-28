import type { AuditEvent } from "../api/types";

interface AuditTrailPanelProps {
  events: AuditEvent[];
  loading?: boolean;
  canReorder?: boolean;
  onRevert?: (auditId: number) => void;
  onDelete?: (auditId: number) => void;
  actionLoading?: boolean;
}

const EVENT_LABELS: Record<string, string> = {
  upload: "File uploaded",
  generate: "Schedule generated",
  reorder: "Sequence reordered",
  undo_reorder: "Sequence reorder reverted / undone",
  finalize: "Schedule finalized",
  unlock: "Schedule unlocked",
  export: "Schedule exported",
  delete_to_bin: "Moved to bin",
  restore_from_bin: "Restored from bin",
};

export function AuditTrailPanel({
  events,
  loading,
  canReorder = false,
  onRevert,
  onDelete,
  actionLoading = false,
}: AuditTrailPanelProps) {
  if (loading) {
    return <div className="audit-panel">Loading audit trail…</div>;
  }

  if (events.length === 0) {
    return null;
  }

  return (
    <details className="audit-panel" open>
      <summary style={{ cursor: "pointer", fontWeight: 600 }}>
        Audit Trail ({events.length} event{events.length === 1 ? "" : "s"})
      </summary>
      <ul className="audit-list" style={{ marginTop: "0.5rem" }}>
        {events.map((event) => {
          const hasPositionChanges =
            event.event_type === "reorder" &&
            Boolean(event.detail && (event.detail as Record<string, unknown>).position_changes);

          return (
            <li
              key={event.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "0.5rem",
                padding: "0.35rem 0",
                borderBottom: "1px dashed #e2e8f0",
              }}
            >
              <div>
                <strong style={{ color: event.event_type === "undo_reorder" ? "#0284c7" : undefined }}>
                  {EVENT_LABELS[event.event_type] ?? event.event_type}
                </strong>
                {" — "}
                <span style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
                  {new Date(event.occurred_at).toLocaleString()}
                </span>
                {event.detail && Object.keys(event.detail).length > 0 && (
                  <span
                    style={{
                      color: "var(--muted)",
                      marginLeft: "0.5rem",
                      fontSize: "0.8rem",
                      fontFamily: "monospace",
                    }}
                  >
                    {JSON.stringify(event.detail)}
                  </span>
                )}
              </div>
              <div style={{ display: "flex", gap: "0.35rem" }}>
                {canReorder && hasPositionChanges && onRevert && (
                  <button
                    className="btn btn-secondary"
                    style={{
                      padding: "0.15rem 0.5rem",
                      fontSize: "0.75rem",
                      borderColor: "#0284c7",
                      color: "#0284c7",
                    }}
                    onClick={() => {
                      if (window.confirm(`Undo / revert the sequence changes made in this audit event (#${event.id})?`)) {
                        onRevert(event.id);
                      }
                    }}
                    disabled={actionLoading}
                    title="Revert coil sequence to before this event"
                  >
                    ↩ Undo this edit
                  </button>
                )}
                {onDelete && (
                  <button
                    className="btn btn-secondary"
                    style={{
                      padding: "0.15rem 0.5rem",
                      fontSize: "0.75rem",
                      color: "#dc2626",
                      borderColor: "#fca5a5",
                    }}
                    onClick={() => {
                      if (window.confirm(`Remove audit log record #${event.id}?`)) {
                        onDelete(event.id);
                      }
                    }}
                    disabled={actionLoading}
                    title="Remove this audit log entry"
                  >
                    🗑 Delete log
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </details>
  );
}

