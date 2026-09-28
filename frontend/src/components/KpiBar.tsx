import type { KpiResult } from "../api/types";

interface KpiBarProps {
  kpis: KpiResult | null | undefined;
  loading?: boolean;
}

export function KpiBar({ kpis, loading }: KpiBarProps) {
  if (loading) {
    return <div className="kpi-grid"><div className="kpi-card"><div className="label">Loading</div></div></div>;
  }

  if (!kpis) {
    return null;
  }

  return (
    <div className="kpi-grid" data-testid="kpi-bar">
      <div className="kpi-card">
        <div className="label">Total Eligible</div>
        <div className="value" data-testid="kpi-total-eligible">{kpis.total_eligible}</div>
      </div>
      <div className="kpi-card">
        <div className="label">HRPO</div>
        <div className="value">{kpis.hrpo_count} ({kpis.hrpo_weight.toFixed(1)}t)</div>
      </div>
      <div className="kpi-card">
        <div className="label">HRSPO</div>
        <div className="value">{kpis.hrspo_count} ({kpis.hrspo_weight.toFixed(1)}t)</div>
      </div>
      <div className="kpi-card">
        <div className="label">NGO FP</div>
        <div className="value">{kpis.ngo_count} ({kpis.ngo_weight.toFixed(1)}t)</div>
      </div>
      <div className="kpi-card">
        <div className="label">Age &gt; 72h</div>
        <div className="value">{kpis.age_gt_72h}</div>
      </div>
      <div className="kpi-card">
        <div className="label">Age &gt; 120h</div>
        <div className="value">{kpis.age_gt_120h}</div>
      </div>
      <div className="kpi-card">
        <div className="label">Age &gt; 168h</div>
        <div className="value">{kpis.age_gt_168h}</div>
      </div>
      <div className="kpi-card">
        <div className="label">Violations</div>
        <div className="value" style={{ color: kpis.violation_count > 0 ? "var(--danger)" : undefined }}>
          {kpis.violation_count}
        </div>
      </div>
      <div className="kpi-card">
        <div className="label">Status</div>
        <div className="value">
          <span className={`status-badge ${kpis.schedule_status}`}>
            {kpis.schedule_status}
          </span>
        </div>
      </div>
    </div>
  );
}

export function verifyKpiArithmetic(kpis: KpiResult): boolean {
  const sum = kpis.hrpo_count + kpis.hrspo_count + kpis.ngo_count;
  return sum === kpis.total_eligible;
}
