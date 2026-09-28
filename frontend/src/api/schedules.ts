import { apiClient } from "./client";
import type {
  AuditEvent,
  KpiResult,
  ScheduleDetail,
  ScheduleItem,
  ScheduleSummary,
  ViolationDetail,
} from "./types";

export async function generateSchedule(uploadId: number): Promise<ScheduleSummary> {
  const { data } = await apiClient.post<ScheduleSummary>("/api/schedules", {
    upload_id: uploadId,
  });
  return data;
}

export async function listSchedules(): Promise<ScheduleSummary[]> {
  const { data } = await apiClient.get<ScheduleSummary[]>("/api/schedules");
  return data;
}

export async function getSchedule(scheduleId: number): Promise<ScheduleDetail> {
  const { data } = await apiClient.get<ScheduleDetail>(`/api/schedules/${scheduleId}`);
  return data;
}

export async function getScheduleItems(scheduleId: number): Promise<ScheduleItem[]> {
  const { data } = await apiClient.get<ScheduleItem[]>(
    `/api/schedules/${scheduleId}/items`,
  );
  return data;
}

export async function getScheduleKpis(scheduleId: number): Promise<KpiResult> {
  const { data } = await apiClient.get<KpiResult>(`/api/schedules/${scheduleId}/kpis`);
  return data;
}

export async function getScheduleViolations(
  scheduleId: number,
): Promise<ViolationDetail[]> {
  const { data } = await apiClient.get<ViolationDetail[]>(
    `/api/schedules/${scheduleId}/violations`,
  );
  return data;
}

export async function reorderSchedule(
  scheduleId: number,
  coilIds: number[],
): Promise<ScheduleDetail> {
  const { data } = await apiClient.patch<ScheduleDetail>(
    `/api/schedules/${scheduleId}/reorder`,
    { coil_ids: coilIds },
  );
  return data;
}

export async function optimizeSchedule(
  scheduleId: number,
): Promise<ScheduleDetail> {
  const { data } = await apiClient.post<ScheduleDetail>(
    `/api/schedules/${scheduleId}/optimize`,
  );
  return data;
}

export async function finalizeSchedule(
  scheduleId: number,
  overrideReason?: string,
): Promise<ScheduleSummary> {
  const { data } = await apiClient.post<ScheduleSummary>(
    `/api/schedules/${scheduleId}/finalize`,
    { override_reason: overrideReason ?? null },
  );
  return data;
}

export async function unlockSchedule(scheduleId: number): Promise<ScheduleSummary> {
  const { data } = await apiClient.post<ScheduleSummary>(
    `/api/schedules/${scheduleId}/unlock`,
  );
  return data;
}

export async function getScheduleAudit(scheduleId: number): Promise<AuditEvent[]> {
  const { data } = await apiClient.get<AuditEvent[]>(
    `/api/schedules/${scheduleId}/audit`,
  );
  return data;
}

export async function exportSchedule(scheduleId: number): Promise<Blob> {
  const { data } = await apiClient.get<Blob>(`/api/schedules/${scheduleId}/export`, {
    responseType: "blob",
  });
  return data;
}

export async function getBinSchedules(): Promise<ScheduleSummary[]> {
  const { data } = await apiClient.get<ScheduleSummary[]>("/api/schedules/bin");
  return data;
}

export async function moveToBin(scheduleId: number): Promise<{ message: string; id: number }> {
  const { data } = await apiClient.delete<{ message: string; id: number }>(
    `/api/schedules/${scheduleId}`,
  );
  return data;
}

export async function restoreFromBin(scheduleId: number): Promise<{ message: string; id: number }> {
  const { data } = await apiClient.post<{ message: string; id: number }>(
    `/api/schedules/${scheduleId}/restore`,
  );
  return data;
}

export async function permanentlyDeleteSchedule(
  scheduleId: number,
): Promise<{ message: string; id: number }> {
  const { data } = await apiClient.delete<{ message: string; id: number }>(
    `/api/schedules/${scheduleId}/permanent`,
  );
  return data;
}

export async function undoLastReorder(scheduleId: number): Promise<ScheduleDetail> {
  const { data } = await apiClient.post<ScheduleDetail>(
    `/api/schedules/${scheduleId}/undo`,
  );
  return data;
}

export async function revertAuditEvent(
  scheduleId: number,
  auditId: number,
): Promise<ScheduleDetail> {
  const { data } = await apiClient.post<ScheduleDetail>(
    `/api/schedules/${scheduleId}/audit/${auditId}/revert`,
  );
  return data;
}

export async function deleteAuditEvent(
  scheduleId: number,
  auditId: number,
): Promise<{ message: string; id: number }> {
  const { data } = await apiClient.delete<{ message: string; id: number }>(
    `/api/schedules/${scheduleId}/audit/${auditId}`,
  );
  return data;
}

