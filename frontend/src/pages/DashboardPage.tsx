import { useNavigate } from "react-router-dom";
import { useGenerateSchedule, useSchedules } from "../api/hooks";
import { KpiBar } from "../components/KpiBar";
import { UploadPanel } from "../components/UploadPanel";
import { useAuth } from "../auth";

export function DashboardPage() {
  const { isPlanner } = useAuth();
  const { data: schedules, isLoading } = useSchedules();
  const generate = useGenerateSchedule();
  const navigate = useNavigate();

  const latest = schedules?.[0];
  const kpis = latest?.kpi_snapshot ?? null;

  async function handleGenerate(uploadId: number) {
    const result = await generate.mutateAsync(uploadId);
    navigate(`/schedules/${result.id}`);
  }

  return (
    <div>
      <h2>Dashboard</h2>

      {isPlanner && (
        <UploadPanel
          onGenerate={handleGenerate}
          generating={generate.isPending}
        />
      )}

      <section style={{ marginTop: "1.5rem" }}>
        <h3>Latest Schedule KPIs</h3>
        <KpiBar kpis={kpis} loading={isLoading} />
        {latest && (
          <p>
            Latest:{" "}
            <button
              className="btn btn-secondary"
              onClick={() => navigate(`/schedules/${latest.id}`)}
            >
              {latest.version_label}
            </button>
            {" "}
            <span className={`status-badge ${latest.status}`}>{latest.status}</span>
          </p>
        )}
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <h3>Recent Schedules</h3>
        {isLoading ? (
          <p>Loading…</p>
        ) : schedules && schedules.length > 0 ? (
          <div className="table-wrap">
            <table className="schedule-table">
              <thead>
                <tr>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Generated</th>
                  <th>Eligible</th>
                </tr>
              </thead>
              <tbody>
                {schedules.slice(0, 5).map((s) => (
                  <tr
                    key={s.id}
                    style={{ cursor: "pointer" }}
                    onClick={() => navigate(`/schedules/${s.id}`)}
                  >
                    <td>{s.version_label}</td>
                    <td><span className={`status-badge ${s.status}`}>{s.status}</span></td>
                    <td>{new Date(s.generated_at).toLocaleString()}</td>
                    <td>{s.kpi_snapshot?.total_eligible ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>No schedules yet. Upload a file to get started.</p>
        )}
      </section>
    </div>
  );
}
