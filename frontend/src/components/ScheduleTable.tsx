import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMemo, useState } from "react";
import type { ScheduleItem, ViolationDetail } from "../api/types";
import { isViolationRow, ViolationBadge } from "./ViolationBadge";

interface ScheduleTableProps {
  items: ScheduleItem[];
  violations: ViolationDetail[];
  canReorder?: boolean;
  onReorder?: (coilIds: number[]) => void;
  onRowClick?: (item: ScheduleItem) => void;
  reordering?: boolean;
}

function statusClass(status: string | null): string {
  if (status === "TA") return "ta";
  if (status === "TW") return "tw";
  return "other";
}

interface SortableRowProps {
  item: ScheduleItem;
  violations: ViolationDetail[];
  canReorder: boolean;
  onRowClick?: (item: ScheduleItem) => void;
}

function SortableRow({ item, violations, canReorder, onRowClick }: SortableRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: item.coil.id, disabled: !canReorder });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const violated = isViolationRow(violations, item.position);
  const coil = item.coil;

  return (
    <tr
      ref={setNodeRef}
      style={style}
      className={violated ? "violation-row" : undefined}
      onClick={() => onRowClick?.(item)}
    >
      <td>
        {canReorder && (
          <span className="drag-handle no-print" {...attributes} {...listeners}>☰</span>
        )}
        {item.position}
      </td>
      <td>{coil.hr_coil_no}</td>
      <td>{coil.product}</td>
      <td>{coil.thk ?? "—"}</td>
      <td>{coil.wdt ?? "—"}</td>
      <td>{coil.wgt ?? "—"}</td>
      <td>{coil.age_hours ?? "—"}</td>
      <td>
        <span className={`status-badge ${statusClass(coil.status)}`}>
          {coil.status ?? "—"}
        </span>
        <ViolationBadge violations={violations} position={item.position} />
      </td>
      <td>{coil.grade ?? "—"}</td>
      <td>{coil.silicon_pct ?? "—"}</td>
    </tr>
  );
}

export function applyReorder(items: ScheduleItem[], coilIds: number[]): ScheduleItem[] {
  const idToItem = new Map(items.map((i) => [i.coil.id, i]));
  return coilIds.map((id, idx) => {
    const item = idToItem.get(id)!;
    return { ...item, position: idx + 1 };
  });
}

export function verifyReorderIntegrity(
  original: ScheduleItem[],
  reordered: ScheduleItem[],
): boolean {
  const origIds = original.map((i) => i.coil.id).sort();
  const newIds = reordered.map((i) => i.coil.id).sort();
  if (origIds.length !== newIds.length) return false;
  for (let i = 0; i < origIds.length; i++) {
    if (origIds[i] !== newIds[i]) return false;
  }
  const positions = reordered.map((i) => i.position).sort((a, b) => a - b);
  for (let i = 0; i < positions.length; i++) {
    if (positions[i] !== i + 1) return false;
  }
  return true;
}

export function ScheduleTable({
  items,
  violations,
  canReorder = false,
  onReorder,
  onRowClick,
  reordering,
}: ScheduleTableProps) {
  const eligible = useMemo(
    () => items.filter((i) => !i.is_apl7).sort((a, b) => a.position - b.position),
    [items],
  );

  const [search, setSearch] = useState("");
  const [productFilter, setProductFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return eligible.filter((item) => {
      const coil = item.coil;
      if (productFilter && coil.product !== productFilter) return false;
      if (statusFilter && coil.status !== statusFilter) return false;
      if (!q) return true;
      return (
        coil.hr_coil_no.toLowerCase().includes(q) ||
        (coil.grade?.toLowerCase().includes(q) ?? false) ||
        (coil.product?.toLowerCase().includes(q) ?? false)
      );
    });
  }, [eligible, search, productFilter, statusFilter]);

  const products = useMemo(
    () => [...new Set(eligible.map((i) => i.coil.product).filter(Boolean))],
    [eligible],
  );
  const statuses = useMemo(
    () => [...new Set(eligible.map((i) => i.coil.status).filter(Boolean))],
    [eligible],
  );

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id || !onReorder) return;

    const ids = eligible.map((i) => i.coil.id);
    const oldIndex = ids.indexOf(Number(active.id));
    const newIndex = ids.indexOf(Number(over.id));
    if (oldIndex === -1 || newIndex === -1) return;

    const newIds = arrayMove(ids, oldIndex, newIndex);
    onReorder(newIds);
  }

  const coilIds = filtered.map((i) => i.coil.id);

  return (
    <div>
      <div className="filters-bar no-print">
        <input
          type="search"
          placeholder="Search coils…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={productFilter} onChange={(e) => setProductFilter(e.target.value)}>
          <option value="">All products</option>
          {products.map((p) => (
            <option key={p} value={p!}>{p}</option>
          ))}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          {statuses.map((s) => (
            <option key={s} value={s!}>{s}</option>
          ))}
        </select>
        {reordering && <span style={{ color: "var(--muted)" }}>Saving order…</span>}
      </div>

      <div className="table-wrap">
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <table className="schedule-table">
            <thead>
              <tr>
                <th>#</th>
                <th>HR Coil No</th>
                <th>Product</th>
                <th>Thk</th>
                <th>Wdt</th>
                <th>Wgt</th>
                <th>Age Hrs</th>
                <th>Status</th>
                <th>Grade</th>
                <th>Silicon %</th>
              </tr>
            </thead>
            <SortableContext items={canReorder ? coilIds : []} strategy={verticalListSortingStrategy}>
              <tbody>
                {filtered.map((item) => (
                  <SortableRow
                    key={item.coil.id}
                    item={item}
                    violations={violations}
                    canReorder={canReorder}
                    onRowClick={onRowClick}
                  />
                ))}
              </tbody>
            </SortableContext>
          </table>
        </DndContext>
      </div>
    </div>
  );
}
