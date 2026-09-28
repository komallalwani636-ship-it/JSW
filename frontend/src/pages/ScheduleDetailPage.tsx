import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  useDeleteAuditEvent,
  useExportSchedule,
  useFinalizeSchedule,
  useOptimizeSchedule,
  useReorderSchedule,
  useRevertAuditEvent,
  useSchedule,
  useScheduleAudit,
  useUndoReorder,
  useUnlockSchedule,
} from "../api/hooks";
import type { ScheduleItem } from "../api/types";
import { Apl7Section } from "../components/Apl7Section";
import { AuditTrailPanel } from "../components/AuditTrailPanel";
import { CoilDetailDrawer } from "../components/CoilDetailDrawer";
import { FinalizeModal } from "../components/FinalizeModal";
import { KpiBar } from "../components/KpiBar";
import { ScheduleTable } from "../components/ScheduleTable";
import { useAuth } from "../auth";

export function ScheduleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const scheduleId = Number(id);
  const { isPlanner } = useAuth();

  const { data: schedule, isLoading } = useSchedule(scheduleId);
  const { data: auditEvents, isLoading: auditLoading } = useScheduleAudit(
    scheduleId,
    isPlanner,
  );

  const reorder = useReorderSchedule(scheduleId);
  const optimize = useOptimizeSchedule(scheduleId);
  const undo = useUndoReorder(scheduleId);
  const revertAudit = useRevertAuditEvent(scheduleId);
  const deleteAudit = useDeleteAuditEvent(scheduleId);
  const finalize = useFinalizeSchedule(scheduleId);
  const unlock = useUnlockSchedule(scheduleId);
  const exportMut = useExportSchedule(scheduleId);

  const [showFinalize, setShowFinalize] = useState(false);
  const [selectedCoil, setSelectedCoil] = useState<ScheduleItem | null>(null);

  if (isLoading || !schedule) {
    return <p>Loading schedule…</p>;
  }

  const isDraft = schedule.status === "draft";
  const canReorder = isPlanner && isDraft;
  const canFinalize = isPlanner && isDraft;
  const canUnlock = isPlanner && schedule.status === "final";
  const canExport = isPlanner;

  const hasReorderToUndo = Boolean(
    auditEvents?.some(
      (e) =>
        e.event_type === "reorder" &&
        Boolean(e.detail && (e.detail as Record<string, unknown>).position_changes),
    ),
  );

  async function handleExport() {
    const blob = await exportMut.mutateAsync();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `schedule_${scheduleId}_${schedule!.version_label}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <p><Link to="/">← Dashboard</Link> · <Link to="/history">History</Link></p>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
        <h2 style={{ margin: 0 }}>
          Schedule {schedule.version_label}
          {" "}
          <span className={`status-badge ${schedule.status}`}>{schedule.status}</span>
        </h2>
        <div className="page-actions no-print">
          {canReorder && (
            <button
              className="btn btn-secondary"
              style={{
                borderColor: "#0284c7",
                color: "#0284c7",
                fontWeight: 600,
              }}
              onClick={() => optimize.mutate()}
              disabled={optimize.isPending}
            >
              {optimize.isPending ? "Optimizing…" : "⚡ Auto-Resolve Violations"}
            </button>
          )}
          {canReorder && hasReorderToUndo && (
            <button
              className="btn btn-secondary"
              style={{
                borderColor: "#64748b",
                color: "#334155",
                fontWeight: 600,
              }}
              onClick={() => undo.mutate()}
              disabled={undo.isPending}
              title="Undo the most recent sequence change"
            >
              {undo.isPending ? "Undoing…" : "↩ Undo Last Edit"}
            </button>
          )}
          {canExport && (
            <button className="btn btn-secondary" onClick={handleExport} disabled={exportMut.isPending}>
              {exportMut.isPending ? "Exporting…" : "Export XLSX"}
            </button>
          )}
          {canFinalize && (
            <button className="btn" onClick={() => setShowFinalize(true)}>
              Finalize
            </button>
          )}
          {canUnlock && (
            <button
              className="btn btn-secondary"
              onClick={() => unlock.mutate()}
              disabled={unlock.isPending}
            >
              {unlock.isPending ? "Unlocking…" : "Unlock / Revise"}
            </button>
          )}
          <button className="btn btn-secondary" onClick={() => window.print()}>
            Print
          </button>
        </div>
      </div>

      <KpiBar kpis={schedule.kpi_snapshot} />

      <ScheduleTable
        items={schedule.items}
        violations={schedule.violations}
        canReorder={canReorder}
        onReorder={(coilIds) => reorder.mutate(coilIds)}
        onRowClick={setSelectedCoil}
        reordering={reorder.isPending}
      />

      <Apl7Section items={schedule.items} />

      {isPlanner && (
        <AuditTrailPanel
          events={auditEvents ?? []}
          loading={auditLoading}
          canReorder={canReorder}
          onRevert={(auditId) => revertAudit.mutate(auditId)}
          onDelete={(auditId) => deleteAudit.mutate(auditId)}
          actionLoading={revertAudit.isPending || deleteAudit.isPending || undo.isPending}
        />
      )}

      {selectedCoil && (
        <CoilDetailDrawer
          coil={selectedCoil.coil}
          onClose={() => setSelectedCoil(null)}
        />
      )}

      {showFinalize && (
        <FinalizeModal
          violations={schedule.violations}
          onCancel={() => setShowFinalize(false)}
          onConfirm={async (reason) => {
            await finalize.mutateAsync(reason);
            setShowFinalize(false);
          }}
          submitting={finalize.isPending}
        />
      )}
    </div>
  );
}
