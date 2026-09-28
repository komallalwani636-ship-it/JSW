import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  useBinSchedules,
  useMoveToBin,
  usePermanentlyDelete,
  useRestoreFromBin,
  useSchedules,
} from "../api/hooks";
import { useAuth } from "../auth";

export function HistoryPage() {
  const [activeTab, setActiveTab] = useState<"active" | "bin">("active");
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const { data: schedules, isLoading: activeLoading } = useSchedules();
  const { data: binSchedules, isLoading: binLoading } = useBinSchedules();

  const moveToBin = useMoveToBin();
  const restoreFromBin = useRestoreFromBin();
  const permanentlyDelete = usePermanentlyDelete();
  const { isPlanner } = useAuth();
  const navigate = useNavigate();

  const activeCount = schedules?.length ?? 0;
  const binCount = binSchedules?.length ?? 0;

  function flashMessage(msg: string) {
    setActionMessage(msg);
    setTimeout(() => setActionMessage(null), 4000);
  }

  function handleMoveToBin(e: React.MouseEvent, scheduleId: number, version: string) {
    e.stopPropagation();
    if (!window.confirm(`Move schedule "${version}" to the Bin?`)) return;

    moveToBin.mutate(scheduleId, {
      onSuccess: () => flashMessage(`Schedule "${version}" moved to Bin.`),
      onError: (err: any) =>
        flashMessage(`Failed to delete: ${err?.response?.data?.detail || err.message}`),
    });
  }

  function handleRestore(e: React.MouseEvent, scheduleId: number, version: string) {
    e.stopPropagation();
    restoreFromBin.mutate(scheduleId, {
      onSuccess: () => flashMessage(`Schedule "${version}" restored from Bin.`),
      onError: (err: any) =>
        flashMessage(`Failed to restore: ${err?.response?.data?.detail || err.message}`),
    });
  }

  function handlePermanentDelete(e: React.MouseEvent, scheduleId: number, version: string) {
    e.stopPropagation();
    if (
      !window.confirm(
        `Are you sure you want to permanently delete schedule "${version}"? This cannot be undone.`,
      )
    ) {
      return;
    }

    permanentlyDelete.mutate(scheduleId, {
      onSuccess: () => flashMessage(`Schedule "${version}" permanently deleted.`),
      onError: (err: any) =>
        flashMessage(`Failed to delete permanently: ${err?.response?.data?.detail || err.message}`),
    });
  }

  return (
    <div>
      <p>
        <Link to="/">← Back to Dashboard</Link>
      </p>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          marginBottom: "1rem",
        }}
      >
        <h2 style={{ margin: 0 }}>Schedule History & Bin</h2>
      </div>

      {actionMessage && (
        <div
          style={{
            padding: "0.75rem 1rem",
            marginBottom: "1rem",
            borderRadius: "6px",
            backgroundColor: "#dcfce7",
            color: "#15803d",
            fontWeight: 500,
            border: "1px solid #bbf7d0",
          }}
        >
          ✓ {actionMessage}
        </div>
      )}

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: "0.5rem",
          borderBottom: "2px solid #e2e8f0",
          marginBottom: "1.25rem",
        }}
      >
        <button
          className="btn"
          style={{
            borderBottomLeftRadius: 0,
            borderBottomRightRadius: 0,
            backgroundColor: activeTab === "active" ? "#0284c7" : "#f1f5f9",
            color: activeTab === "active" ? "#ffffff" : "#475569",
            border: "none",
            fontWeight: 600,
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
          onClick={() => setActiveTab("active")}
        >
          <span>📁 Active Schedules</span>
          <span
            style={{
              fontSize: "0.75rem",
              padding: "0.15rem 0.45rem",
              borderRadius: "999px",
              backgroundColor: activeTab === "active" ? "rgba(255,255,255,0.25)" : "#cbd5e1",
              color: activeTab === "active" ? "#ffffff" : "#334155",
            }}
          >
            {activeCount}
          </span>
        </button>

        <button
          className="btn"
          style={{
            borderBottomLeftRadius: 0,
            borderBottomRightRadius: 0,
            backgroundColor: activeTab === "bin" ? "#dc2626" : "#f1f5f9",
            color: activeTab === "bin" ? "#ffffff" : "#475569",
            border: "none",
            fontWeight: 600,
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
          onClick={() => setActiveTab("bin")}
        >
          <span>🗑️ Bin (Trash)</span>
          <span
            style={{
              fontSize: "0.75rem",
              padding: "0.15rem 0.45rem",
              borderRadius: "999px",
              backgroundColor: activeTab === "bin" ? "rgba(255,255,255,0.25)" : "#cbd5e1",
              color: activeTab === "bin" ? "#ffffff" : "#334155",
            }}
          >
            {binCount}
          </span>
        </button>
      </div>

      {/* Tab: Active Schedules */}
      {activeTab === "active" && (
        <>
          {activeLoading ? (
            <p>Loading active schedules…</p>
          ) : schedules && schedules.length > 0 ? (
            <div className="table-wrap">
              <table className="schedule-table">
                <thead>
                  <tr>
                    <th>Version</th>
                    <th>Upload File</th>
                    <th>Generated</th>
                    <th>Planner</th>
                    <th>Status</th>
                    {isPlanner && <th style={{ textAlign: "right" }}>Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {schedules.map((s) => (
                    <tr
                      key={s.id}
                      style={{ cursor: "pointer" }}
                      onClick={() => navigate(`/schedules/${s.id}`)}
                    >
                      <td style={{ fontWeight: 600 }}>{s.version_label}</td>
                      <td>{s.upload_filename ?? `Upload #${s.upload_file_id}`}</td>
                      <td>{new Date(s.generated_at).toLocaleString()}</td>
                      <td>{s.generator_username ?? "—"}</td>
                      <td>
                        <span className={`status-badge ${s.status}`}>{s.status}</span>
                      </td>
                      {isPlanner && (
                        <td style={{ textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                          <button
                            className="btn btn-secondary"
                            style={{
                              padding: "0.25rem 0.6rem",
                              fontSize: "0.85rem",
                              color: "#dc2626",
                              borderColor: "#fca5a5",
                            }}
                            title="Move to Bin"
                            onClick={(e) => handleMoveToBin(e, s.id, s.version_label)}
                            disabled={moveToBin.isPending}
                          >
                            🗑️ Delete to Bin
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>No active schedules in history.</p>
          )}
        </>
      )}

      {/* Tab: Bin */}
      {activeTab === "bin" && (
        <>
          {binLoading ? (
            <p>Loading Bin…</p>
          ) : binSchedules && binSchedules.length > 0 ? (
            <div className="table-wrap">
              <table className="schedule-table">
                <thead>
                  <tr>
                    <th>Version</th>
                    <th>Upload File</th>
                    <th>Original Status</th>
                    <th>Deleted At</th>
                    <th>Planner</th>
                    {isPlanner && <th style={{ textAlign: "right" }}>Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {binSchedules.map((s) => (
                    <tr key={s.id}>
                      <td style={{ fontWeight: 600 }}>{s.version_label}</td>
                      <td>{s.upload_filename ?? `Upload #${s.upload_file_id}`}</td>
                      <td>
                        <span className={`status-badge ${s.status}`}>{s.status}</span>
                      </td>
                      <td>{s.deleted_at ? new Date(s.deleted_at).toLocaleString() : "Recently"}</td>
                      <td>{s.generator_username ?? "—"}</td>
                      {isPlanner && (
                        <td style={{ textAlign: "right" }}>
                          <button
                            className="btn btn-secondary"
                            style={{
                              padding: "0.25rem 0.6rem",
                              fontSize: "0.85rem",
                              marginRight: "0.5rem",
                              color: "#0284c7",
                              borderColor: "#7dd3fc",
                            }}
                            title="Restore back to Active History"
                            onClick={(e) => handleRestore(e, s.id, s.version_label)}
                            disabled={restoreFromBin.isPending}
                          >
                            ↺ Restore
                          </button>
                          <button
                            className="btn btn-secondary"
                            style={{
                              padding: "0.25rem 0.6rem",
                              fontSize: "0.85rem",
                              color: "#dc2626",
                              borderColor: "#fca5a5",
                            }}
                            title="Permanently remove"
                            onClick={(e) => handlePermanentDelete(e, s.id, s.version_label)}
                            disabled={permanentlyDelete.isPending}
                          >
                            ❌ Delete Permanently
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div
              style={{
                textAlign: "center",
                padding: "2.5rem 1rem",
                color: "#64748b",
                border: "2px dashed #cbd5e1",
                borderRadius: "8px",
              }}
            >
              <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>🗑️</div>
              <p style={{ margin: 0, fontWeight: 500 }}>The Bin is empty.</p>
              <p style={{ margin: "0.25rem 0 0 0", fontSize: "0.9rem" }}>
                Deleted schedules will appear here where they can be restored or purged permanently.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
