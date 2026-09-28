import { apiClient } from './client';

export interface HistoricalFilterParams {
  date_preset?: string;
  start_date?: string;
  end_date?: string;
  doctor_id?: string;
  department_id?: string;
  queue_id?: string;
  status?: string;
  booking_source?: string;
  page?: number;
  page_size?: number;
}

export interface HistoricalAppointmentItem {
  id: string;
  token_number: number;
  token_display: string;
  date: string;
  booking_source: string;
  doctor_id: string;
  doctor_name: string;
  department_id: string;
  department_name: string;
  queue_id: string;
  queue_name: string;
  patient_name: string;
  patient_phone?: string;
  arrived_at?: string;
  consultation_started_at?: string;
  consultation_completed_at?: string;
  consultation_duration_seconds?: number;
  consultation_duration_minutes?: number;
  waiting_time_seconds?: number;
  waiting_time_minutes?: number;
  status: string;
  notes?: string;
}

export interface HistoricalAppointmentsResponse {
  items: HistoricalAppointmentItem[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export const historicalApi = {
  getAppointments: async (params: HistoricalFilterParams): Promise<HistoricalAppointmentsResponse> => {
    const { data } = await apiClient.get<HistoricalAppointmentsResponse>('/historical-appointments', {
      params,
    });
    return data;
  },

  downloadCsv: async (params: HistoricalFilterParams): Promise<void> => {
    const response = await apiClient.get('/historical-appointments/export', {
      params,
      responseType: 'blob',
    });
    const blob = new Blob([response.data], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `qflow_historical_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};
