import { apiClient } from './client';
import type {
  HospitalBrief,
  DepartmentBrief,
  DoctorBrief,
  OPDSessionBrief,
  DoctorAvailabilityResponse,
} from '../types/api';

// Exported types for use by staff portal pages
export interface StaffQueueItem {
  queue_id: string;
  queue_name: string;
  queue_date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  status: string;
  session_id: string;
  department_id: string;
  department_name?: string;
  doctor_id: string;
  doctor_name: string;
  current_token?: string | null;
  operational_status?: string;
  waiting_count?: number;
  total_waiting: number;
  total_booked: number;
  total_active?: number;
}

export interface StaffHospitalMetrics {
  today_appointments: number;
  active_queues: number;
  waiting_patients: number;
  in_consultation: number;
  completed_consultations: number;
  no_shows: number;
  doctor_delays: number;
  emergency_events: number;
}

export interface StaffDoctorItem {
  id: string;
  name: string;
  department_id: string;
  department_name: string;
  status: string;
}

export interface StaffHospitalDetails {
  hospital: HospitalBrief;
  departments: DepartmentBrief[];
  doctors?: StaffDoctorItem[];
  queues: StaffQueueItem[];
  metrics?: StaffHospitalMetrics;
}

export const discoveryApi = {
  listHospitals: async (): Promise<HospitalBrief[]> => {
    const { data } = await apiClient.get<HospitalBrief[]>('/discovery/hospitals');
    return data;
  },

  listDepartments: async (hospitalId: string): Promise<DepartmentBrief[]> => {
    const { data } = await apiClient.get<DepartmentBrief[]>(
      `/discovery/hospitals/${hospitalId}/departments`
    );
    return data;
  },

  listDoctors: async (departmentId: string): Promise<DoctorBrief[]> => {
    const { data } = await apiClient.get<DoctorBrief[]>(
      `/discovery/departments/${departmentId}/doctors`
    );
    return data;
  },

  listDoctorSessions: async (doctorId: string): Promise<OPDSessionBrief[]> => {
    const { data } = await apiClient.get<OPDSessionBrief[]>(
      `/discovery/doctors/${doctorId}/sessions`
    );
    return data;
  },

  getStaffHospital: async (): Promise<StaffHospitalDetails> => {
    // SECURITY: No hospital_id param — the backend derives hospital context exclusively
    // from the authenticated user's JWT token. Do NOT pass any hospital_id here.
    const { data } = await apiClient.get('/discovery/staff-hospital');
    return data;
  },

  getDoctorAvailability: async (
    doctorId: string,
    days: number = 14
  ): Promise<DoctorAvailabilityResponse> => {
    const { data } = await apiClient.get<DoctorAvailabilityResponse>(
      `/doctors/${doctorId}/availability?days=${days}`
    );
    return data;
  },

  setDoctorAvailability: async (
    doctorId: string,
    payload: { availability_date: string; is_available: boolean; reason?: string }
  ): Promise<{ message: string; availability: any }> => {
    const { data } = await apiClient.post(
      `/doctors/${doctorId}/availability`,
      payload
    );
    return data;
  },
};
