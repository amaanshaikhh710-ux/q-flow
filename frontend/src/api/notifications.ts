import { apiClient } from './client';

export interface NotificationItem {
  id: string;
  queue_entry_id?: string | null;
  trigger_event_id?: string | null;
  channel: string;
  notification_type: string;
  title?: string | null;
  message?: string | null;
  payload_json?: Record<string, any> | null;
  status: string;
  failure_reason?: string | null;
  created_at: string;
  delivered_at?: string | null;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  total: number;
}

export const notificationsApi = {
  getMy: async (): Promise<NotificationListResponse> => {
    const { data } = await apiClient.get<NotificationListResponse>('/notifications/my');
    return data;
  },
};
