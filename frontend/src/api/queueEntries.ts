import { apiClient } from './client';
import type { QueueEntryResponse, PatientAppointmentsResponse } from '../types/api';

export interface NoShowPayload {
  reason?: string;
}

export interface CompleteConsultationPayload {
  interruption_notes?: string;
}

export interface PriorityUpdatePayload {
  priority_class: string;
  reason?: string;
}

export const queueEntriesApi = {
  getMy: async (): Promise<PatientAppointmentsResponse> => {
    const { data } = await apiClient.get<PatientAppointmentsResponse>('/queue-entries/my');
    return data;
  },

  getEntry: async (entryId: string): Promise<QueueEntryResponse> => {
    const { data } = await apiClient.get<QueueEntryResponse>(`/queue-entries/${entryId}`);
    return data;
  },

  call: async (entryId: string): Promise<QueueEntryResponse> => {
    const { data } = await apiClient.post<QueueEntryResponse>(
      `/queue-entries/${entryId}/call`
    );
    return data;
  },

  startConsultation: async (entryId: string): Promise<QueueEntryResponse> => {
    const { data } = await apiClient.post<QueueEntryResponse>(
      `/queue-entries/${entryId}/start-consultation`
    );
    return data;
  },

  completeConsultation: async (
    entryId: string,
    payload?: CompleteConsultationPayload
  ): Promise<QueueEntryResponse> => {
    const { data } = await apiClient.post<QueueEntryResponse>(
      `/queue-entries/${entryId}/complete-consultation`,
      payload ?? {}
    );
    return data;
  },

  noShow: async (entryId: string, payload?: NoShowPayload): Promise<QueueEntryResponse> => {
    const { data } = await apiClient.post<QueueEntryResponse>(
      `/queue-entries/${entryId}/no-show`,
      payload ?? {}
    );
    return data;
  },

  leave: async (entryId: string, reason?: string): Promise<QueueEntryResponse> => {
    const { data } = await apiClient.post<QueueEntryResponse>(
      `/queue-entries/${entryId}/leave`,
      { reason }
    );
    return data;
  },

  return: async (entryId: string): Promise<QueueEntryResponse> => {
    const { data } = await apiClient.post<QueueEntryResponse>(
      `/queue-entries/${entryId}/return`
    );
    return data;
  },

  requeue: async (
    entryId: string,
    payload?: { priority_class?: string; reason?: string }
  ): Promise<QueueEntryResponse> => {
    const { data } = await apiClient.post<QueueEntryResponse>(
      `/queue-entries/${entryId}/requeue`,
      payload ?? {}
    );
    return data;
  },

  updatePriority: async (
    entryId: string,
    payload: PriorityUpdatePayload
  ): Promise<QueueEntryResponse> => {
    const { data } = await apiClient.post<QueueEntryResponse>(
      `/queue-entries/${entryId}/priority`,
      payload
    );
    return data;
  },

  arrive: async (entryId: string): Promise<QueueEntryResponse> => {
    const { data } = await apiClient.post<QueueEntryResponse>(
      `/queue-entries/${entryId}/arrive`
    );
    return data;
  },

  wait: async (entryId: string): Promise<QueueEntryResponse> => {
    const { data } = await apiClient.post<QueueEntryResponse>(
      `/queue-entries/${entryId}/wait`
    );
    return data;
  },
};

