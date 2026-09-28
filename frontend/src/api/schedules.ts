import { apiClient } from './client';
import type {
  DoctorScheduleResponse,
  DoctorScheduleCreateRequest,
  DoctorScheduleBatchRequest,
  AvailableDoctorsResponse,
  DoctorScheduleAvailabilityResponse,
} from '../types/api';

export const schedulesApi = {
  getDoctorAvailability: async (doctorId: string, hospitalId?: string, departmentId?: string): Promise<DoctorScheduleAvailabilityResponse> => {
    const params: Record<string, string> = {};
    if (hospitalId) params.hospital_id = hospitalId;
    if (departmentId) params.department_id = departmentId;
    const { data } = await apiClient.get<DoctorScheduleAvailabilityResponse>(`/schedules/doctors/${doctorId}/availability`, {
      params,
    });
    return data;
  },
  /**
   * Get doctors available on a specific date for a hospital.
   * Returns ONLY doctors who are scheduled and available with their timing.
   */
  getAvailableDoctors: async (
    hospitalId: string,
    date: string,
    departmentId?: string
  ): Promise<AvailableDoctorsResponse> => {
    const { data } = await apiClient.get<AvailableDoctorsResponse>(
      '/schedules/available-doctors',
      {
        params: {
          hospital_id: hospitalId,
          date,
          ...(departmentId ? { department_id: departmentId } : {}),
        },
      }
    );
    return data;
  },

  /**
   * Staff: Create or update a doctor schedule for a specific date and time window.
   */
  createSchedule: async (
    payload: DoctorScheduleCreateRequest
  ): Promise<DoctorScheduleResponse> => {
    const { data } = await apiClient.post<DoctorScheduleResponse>(
      '/schedules',
      payload
    );
    return data;
  },

  /**
   * Staff: Batch schedule a doctor across multiple dates or an entire week.
   */
  createBatchSchedule: async (
    payload: DoctorScheduleBatchRequest
  ): Promise<DoctorScheduleResponse[]> => {
    const { data } = await apiClient.post<DoctorScheduleResponse[]>(
      '/schedules/batch',
      payload
    );
    return data;
  },

  /**
   * Staff: List schedules for a hospital or doctor within a date range.
   */
  getSchedules: async (params?: {
    hospital_id?: string;
    doctor_id?: string;
    department_id?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<DoctorScheduleResponse[]> => {
    const { data } = await apiClient.get<DoctorScheduleResponse[]>(
      '/schedules',
      { params: params || {} }
    );
    return data;
  },

  /**
   * Staff: Update a doctor schedule shift.
   */
  updateSchedule: async (scheduleId: string, payload: { start_time?: string; end_time?: string; status?: string }): Promise<DoctorScheduleResponse> => {
    const { data } = await apiClient.put<DoctorScheduleResponse>(
      `/schedules/${scheduleId}`,
      payload
    );
    return data;
  },

  /**
   * Staff: Delete / cancel a doctor schedule.
   */
  deleteSchedule: async (scheduleId: string): Promise<{ status: string; schedule_id: string }> => {
    const { data } = await apiClient.delete<{ status: string; schedule_id: string }>(
      `/schedules/${scheduleId}`
    );
    return data;
  },
};
