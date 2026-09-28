import { Fragment } from "react";
import type { CoilRecord } from "../api/types";

interface CoilDetailDrawerProps {
  coil: CoilRecord | null;
  onClose: () => void;
}

export function CoilDetailDrawer({ coil, onClose }: CoilDetailDrawerProps) {
  if (!coil) return null;

  const entries = Object.entries(coil.all_columns).sort(([a], [b]) => a.localeCompare(b));

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>Coil {coil.hr_coil_no}</h2>
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
        <dl>
          {entries.map(([key, value]) => (
            <Fragment key={key}>
              <dt>{key}</dt>
              <dd>{String(value ?? "")}</dd>
            </Fragment>
          ))}
        </dl>
      </div>
    </>
  );
}
