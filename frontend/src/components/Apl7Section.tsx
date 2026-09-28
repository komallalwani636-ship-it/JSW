import type { ScheduleItem } from "../api/types";

interface Apl7SectionProps {
  items: ScheduleItem[];
}

export function Apl7Section({ items }: Apl7SectionProps) {
  const apl7 = items.filter((i) => i.is_apl7).sort((a, b) => a.position - b.position);

  if (apl7.length === 0) return null;

  return (
    <details className="apl7-section" open>
      <summary>APL7 Coils ({apl7.length}) — not in schedule sequence</summary>
      <div className="table-wrap" style={{ border: "none" }}>
        <table className="schedule-table">
          <thead>
            <tr>
              <th>HR Coil No</th>
              <th>Product</th>
              <th>Thk</th>
              <th>Wdt</th>
              <th>Wgt</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {apl7.map((item) => (
              <tr key={item.id}>
                <td>{item.coil.hr_coil_no}</td>
                <td>{item.coil.product}</td>
                <td>{item.coil.thk ?? "—"}</td>
                <td>{item.coil.wdt ?? "—"}</td>
                <td>{item.coil.wgt ?? "—"}</td>
                <td>{item.coil.status ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
