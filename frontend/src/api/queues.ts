import { apiClient } from './client';
import type {
  QueueEntryResponse,
  QueueJoinResponse,
  QueueSnapshotResponse,
  ReforecastTriggerResponse,
  StaffBookAppointmentRequest,
} from '../types/api';

export interface EmergencyInsertPayload {
  patient_user_id: string;
  reason?: string;
}

export interface DoctorDelayPayload {
  delay_minutes: number;
  reason?: string;
}

export interface DoctorBreakPayload {
  duration_minutes: number;
  reason?: string;
}

export const queuesApi = {
  createQueue: async (payload: {
    doctor_id: string;
    queue_date: string;
    start_time: string;
    end_time: string;
  }) => {
    const { data } = await apiClient.post('/queues', payload);
    return data;
  },

  getQueuesForDate: async (date: string) => {
    const { data } = await apiClient.get(`/queues/for-date`, { params: { queue_date: date } });
    return data as any;
  },
  join: async (
    queueId: string,
    appointmentDate?: string,
    appointmentTime?: string
  ): Promise<QueueJoinResponse> => {
    const payload: { appointment_date?: string; appointment_time?: string } = {};
    if (appointmentDate) payload.appointment_date = appointmentDate;
    if (appointmentTime) payload.appointment_time = appointmentTime;
    const { data } = await apiClient.post<QueueJoinResponse>(
      `/queues/${queueId}/join`,
      Object.keys(payload).length > 0 ? payload : undefined
    );
    return data;
  },

  staffBook: async (
    queueId: string,
    payload: StaffBookAppointmentRequest
  ): Promise<QueueJoinResponse> => {
    const { data } = await apiClient.post<QueueJoinResponse>(
      `/queues/${queueId}/staff-book`,
      payload
    );
    return data;
  },

  getSnapshot: async (queueId: string, targetDate?: string): Promise<QueueSnapshotResponse> => {
    const { data } = await apiClient.get<QueueSnapshotResponse>(
      `/queues/${queueId}/snapshot`,
      { params: targetDate ? { target_date: targetDate } : undefined }
    );
    return data;
  },

  callNext: async (queueId: string): Promise<QueueEntryResponse> => {
    const { data } = await apiClient.post<QueueEntryResponse>(
      `/queues/${queueId}/call-next`
    );
    return data;
  },

  insertEmergency: async (
    queueId: string,
    payload: EmergencyInsertPayload
  ): Promise<QueueEntryResponse> => {
    const { data } = await apiClient.post<QueueEntryResponse>(
      `/queues/${queueId}/emergency`,
      payload
    );
    return data;
  },

  pause: async (queueId: string): Promise<{ message: string }> => {
    const { data } = await apiClient.post<{ message: string }>(`/queues/${queueId}/pause`);
    return data;
  },

  resume: async (queueId: string): Promise<{ message: string }> => {
    const { data } = await apiClient.post<{ message: string }>(
      `/queues/${queueId}/resume`
    );
    return data;
  },

  doctorDelay: async (queueId: string, payload: DoctorDelayPayload): Promise<{ message: string }> => {
    const { data } = await apiClient.post<{ message: string }>(
      `/queues/${queueId}/doctor-delay`,
      payload
    );
    return data;
  },

  doctorBreakStart: async (queueId: string, payload: DoctorBreakPayload): Promise<{ message: string }> => {
    const { data } = await apiClient.post<{ message: string }>(
      `/queues/${queueId}/doctor-break/start`,
      payload
    );
    return data;
  },

  doctorBreakEnd: async (queueId: string): Promise<{ message: string }> => {
    const { data } = await apiClient.post<{ message: string }>(
      `/queues/${queueId}/doctor-break/end`
    );
    return data;
  },

  reforecast: async (queueId: string): Promise<ReforecastTriggerResponse> => {
    const { data } = await apiClient.post<ReforecastTriggerResponse>(
      `/queues/${queueId}/reforecast`
    );
    return data;
  },

  endQueue: async (queueId: string): Promise<{ message: string }> => {
    const { data } = await apiClient.post<{ message: string }>(
      `/queues/${queueId}/end`
    );
    return data;
  },
};
