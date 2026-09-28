import type { ViolationDetail } from "../api/types";

interface ViolationBadgeProps {
  violations: ViolationDetail[];
  position: number;
}

export function getViolationsForPosition(
  violations: ViolationDetail[],
  position: number,
): ViolationDetail[] {
  return violations.filter(
    (v) => v.position_a === position || v.position_b === position,
  );
}

export function formatViolationTooltip(v: ViolationDetail): string {
  const detail = v.detail;
  const parts = [`Rule: ${v.rule_type}`];
  for (const [key, value] of Object.entries(detail)) {
    parts.push(`${key}: ${value}`);
  }
  return parts.join(" | ");
}

export function ViolationBadge({ violations, position }: ViolationBadgeProps) {
  const relevant = getViolationsForPosition(violations, position);
  if (relevant.length === 0) return null;

  return (
    <span className="tooltip" style={{ marginLeft: "0.25rem" }}>
      <span style={{ color: "var(--danger)", fontWeight: 700 }}>⚠</span>
      <span className="tooltip-content">
        {relevant.map((v, i) => (
          <div key={i}>{formatViolationTooltip(v)}</div>
        ))}
      </span>
    </span>
  );
}

export function isViolationRow(violations: ViolationDetail[], position: number): boolean {
  return getViolationsForPosition(violations, position).length > 0;
}
