import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { DashboardPage } from "../pages/DashboardPage";
import { ScheduleDetailPage } from "../pages/ScheduleDetailPage";

vi.mock("../api/hooks", () => ({
  useSchedules: () => ({ data: [], isLoading: false }),
  useGenerateSchedule: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpload: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSchedule: () => ({
    data: {
      id: 1,
      version_label: "test-v1",
      status: "draft",
      generated_at: new Date().toISOString(),
      upload_file_id: 1,
      kpi_snapshot: null,
      items: [],
      violations: [],
    },
    isLoading: false,
  }),
  useScheduleAudit: () => ({ data: [], isLoading: false }),
  useReorderSchedule: () => ({ mutate: vi.fn(), isPending: false }),
  useOptimizeSchedule: () => ({ mutate: vi.fn(), isPending: false }),
  useFinalizeSchedule: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUnlockSchedule: () => ({ mutate: vi.fn(), isPending: false }),
  useExportSchedule: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useBinSchedules: () => ({ data: [], isLoading: false }),
  useMoveToBin: () => ({ mutate: vi.fn(), isPending: false }),
  useRestoreFromBin: () => ({ mutate: vi.fn(), isPending: false }),
  usePermanentlyDelete: () => ({ mutate: vi.fn(), isPending: false }),
  useUndoReorder: () => ({ mutate: vi.fn(), isPending: false }),
  useRevertAuditEvent: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteAuditEvent: () => ({ mutate: vi.fn(), isPending: false }),
}));

const viewerAuth = {
  token: "t",
  username: "viewer",
  role: "viewer" as const,
  isPlanner: false,
  isAuthenticated: true,
  setToken: vi.fn(),
  logout: vi.fn(),
};

const plannerAuth = { ...viewerAuth, username: "planner", role: "planner" as const, isPlanner: true };

vi.mock("../auth", () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from "../auth";

describe("role-based UI enforcement", () => {
  it("viewer dashboard hides upload panel", () => {
    vi.mocked(useAuth).mockReturnValue(viewerAuth);
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    expect(screen.queryByText(/Drop HR Stock Report here/i)).not.toBeInTheDocument();
  });

  it("planner dashboard shows upload panel", () => {
    vi.mocked(useAuth).mockReturnValue(plannerAuth);
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Drop HR Stock Report here/i)).toBeInTheDocument();
  });

  it("viewer schedule detail hides planner actions", () => {
    vi.mocked(useAuth).mockReturnValue(viewerAuth);
    render(
      <MemoryRouter initialEntries={["/schedules/1"]}>
        <Routes>
          <Route path="/schedules/:id" element={<ScheduleDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.queryByText("Finalize")).not.toBeInTheDocument();
    expect(screen.queryByText("Export XLSX")).not.toBeInTheDocument();
    expect(screen.queryByText("Unlock / Revise")).not.toBeInTheDocument();
  });

  it("planner schedule detail shows finalize and export", () => {
    vi.mocked(useAuth).mockReturnValue(plannerAuth);
    render(
      <MemoryRouter initialEntries={["/schedules/1"]}>
        <Routes>
          <Route path="/schedules/:id" element={<ScheduleDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("Finalize")).toBeInTheDocument();
    expect(screen.getByText("Export XLSX")).toBeInTheDocument();
  });
});
