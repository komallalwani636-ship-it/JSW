import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { login } from "./auth";
import { uploadFile } from "./uploads";
import {
  deleteAuditEvent,
  exportSchedule,
  finalizeSchedule,
  generateSchedule,
  getBinSchedules,
  getSchedule,
  getScheduleAudit,
  getScheduleKpis,
  getScheduleViolations,
  listSchedules,
  moveToBin,
  optimizeSchedule,
  permanentlyDeleteSchedule,
  reorderSchedule,
  restoreFromBin,
  revertAuditEvent,
  undoLastReorder,
  unlockSchedule,
} from "./schedules";

export function useLogin() {
  return useMutation({ mutationFn: ({ username, password }: { username: string; password: string }) => login(username, password) });
}

export function useUpload() {
  return useMutation({ mutationFn: uploadFile });
}

export function useGenerateSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: generateSchedule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

export function useSchedules() {
  return useQuery({ queryKey: ["schedules"], queryFn: listSchedules });
}

export function useSchedule(scheduleId: number | undefined) {
  return useQuery({
    queryKey: ["schedule", scheduleId],
    queryFn: () => getSchedule(scheduleId!),
    enabled: scheduleId !== undefined,
  });
}

export function useScheduleKpis(scheduleId: number | undefined) {
  return useQuery({
    queryKey: ["schedule", scheduleId, "kpis"],
    queryFn: () => getScheduleKpis(scheduleId!),
    enabled: scheduleId !== undefined,
  });
}

export function useScheduleViolations(scheduleId: number | undefined) {
  return useQuery({
    queryKey: ["schedule", scheduleId, "violations"],
    queryFn: () => getScheduleViolations(scheduleId!),
    enabled: scheduleId !== undefined,
  });
}

export function useScheduleAudit(scheduleId: number | undefined, enabled = true) {
  return useQuery({
    queryKey: ["schedule", scheduleId, "audit"],
    queryFn: () => getScheduleAudit(scheduleId!),
    enabled: scheduleId !== undefined && enabled,
  });
}

export function useReorderSchedule(scheduleId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (coilIds: number[]) => reorderSchedule(scheduleId, coilIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule", scheduleId] });
    },
  });
}

export function useOptimizeSchedule(scheduleId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => optimizeSchedule(scheduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule", scheduleId] });
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

export function useFinalizeSchedule(scheduleId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (overrideReason?: string) => finalizeSchedule(scheduleId, overrideReason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule", scheduleId] });
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

export function useUnlockSchedule(scheduleId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => unlockSchedule(scheduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule", scheduleId] });
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

export function useExportSchedule(scheduleId: number) {
  return useMutation({ mutationFn: () => exportSchedule(scheduleId) });
}

export function useBinSchedules() {
  return useQuery({
    queryKey: ["schedules", "bin"],
    queryFn: getBinSchedules,
  });
}

export function useMoveToBin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scheduleId: number) => moveToBin(scheduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
      queryClient.invalidateQueries({ queryKey: ["schedules", "bin"] });
    },
  });
}

export function useRestoreFromBin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scheduleId: number) => restoreFromBin(scheduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
      queryClient.invalidateQueries({ queryKey: ["schedules", "bin"] });
    },
  });
}

export function usePermanentlyDelete() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scheduleId: number) => permanentlyDeleteSchedule(scheduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules", "bin"] });
    },
  });
}

export function useUndoReorder(scheduleId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => undoLastReorder(scheduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule", scheduleId] });
      queryClient.invalidateQueries({ queryKey: ["schedule-audit", scheduleId] });
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

export function useRevertAuditEvent(scheduleId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (auditId: number) => revertAuditEvent(scheduleId, auditId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule", scheduleId] });
      queryClient.invalidateQueries({ queryKey: ["schedule-audit", scheduleId] });
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

export function useDeleteAuditEvent(scheduleId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (auditId: number) => deleteAuditEvent(scheduleId, auditId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule-audit", scheduleId] });
    },
  });
}

