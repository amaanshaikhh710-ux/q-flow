/**
 * Core API response types — mirror backend Pydantic schemas exactly.
 * Backend is the single source of truth. Do NOT invent fields here.
 * WebSocket message types match actual backend output verified from handlers.py + snapshot_service.py
 */

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export type UserRole = 'patient' | 'staff' | 'admin';

export interface UserResponse {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  role: UserRole;
  hospital_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserResponse;
}

// ---------------------------------------------------------------------------
// Discovery
// ---------------------------------------------------------------------------

export interface HospitalBrief {
  id: string;
  name: string;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface DepartmentBrief {
  id: string;
  hospital_id: string;
  name: string;
}

export type DoctorStatus = 'available' | 'unavailable' | 'break';

export interface DoctorBrief {
  id: string;
  department_id: string;
  name: string;
  status: DoctorStatus;
}

export interface DoctorScheduleAvailabilityResponse {
  hospital_id: string;
  department_id: string;
  doctor_id: string;
  doctor_name: string;
  schedules: AvailableDoctorItem[];
}

export type QueueStatus = 'ACTIVE' | 'PAUSED' | 'COMPLETED';
export type SessionStatus = 'scheduled' | 'active' | 'paused' | 'completed' | 'cancelled';

export interface ActiveQueueBrief {
  id: string;
  name: string;
  status: QueueStatus;
  total_waiting: number;
}

export interface OPDSessionBrief {
  id: string;
  doctor_id: string;
  department_id: string;
  status: SessionStatus;
  starts_at: string;
  ends_at: string | null;
  active_queue: ActiveQueueBrief | null;
}

// ---------------------------------------------------------------------------
// Queue & Entries
// ---------------------------------------------------------------------------

export type QueueEntryStatus =
  | 'BOOKED'
  | 'ARRIVED'
  | 'WAITING'
  | 'CALLED'
  | 'IN_CONSULTATION'
  | 'COMPLETED'
  | 'TEMPORARILY_LEFT'
  | 'RETURNED'
  | 'NO_SHOW';

export type PriorityClass = 'NORMAL' | 'PRIORITY' | 'EMERGENCY';

export interface QueueEntryResponse {
  id: string;
  queue_id: string;
  patient_user_id: string;
  patient_name?: string | null;
  patient_phone?: string | null;
  token_number: number;
  token_display: string;
  priority_class: PriorityClass;
  status: QueueEntryStatus;
  booking_source?: string;
  notes?: string | null;
  position: number | null;
  appointment_date?: string | null;
  schedule_id?: string | null;
  appointment_time?: string | null;
  joined_at: string;
  arrived_at?: string | null;
  called_at: string | null;
  temporary_left_at: string | null;
  returned_at: string | null;
  no_show_at: string | null;
  created_at: string;
}

export interface StaffBookAppointmentRequest {
  patient_name: string;
  patient_phone?: string;
  booking_source?: string;
  priority_class?: PriorityClass;
  appointment_date?: string;
  appointment_time?: string;
  notes?: string;
}

export interface DoctorAvailabilityItem {
  date: string;
  is_available: boolean;
  is_past: boolean;
  reason?: string | null;
}

export interface DoctorAvailabilityResponse {
  doctor_id: string;
  doctor_name: string;
  availability: DoctorAvailabilityItem[];
}

export interface PatientAppointmentItem {
  id: string;
  queue_id: string;
  token_number: number;
  token_display: string;
  status: QueueEntryStatus;
  priority_class: PriorityClass;
  booking_source: string;
  notes?: string | null;
  appointment_date?: string | null;
  joined_at: string;
  arrived_at?: string | null;
  called_at?: string | null;
  position: number | null;
  hospital_id: string;
  hospital_name: string;
  hospital_address?: string | null;
  hospital_latitude?: number | null;
  hospital_longitude?: number | null;
  department_id: string;
  department_name: string;
  doctor_id: string;
  doctor_name: string;
  estimated_wait_minutes?: number | null;
  estimated_start_time?: string | null;
  latest_departure_time?: string | null;
  travel_duration_minutes?: number | null;
  travel_uncertainty_minutes?: number | null;
  travel_mode: string;
  travel_status: string;
  created_at: string;
}

export interface PatientAppointmentsResponse {
  today: PatientAppointmentItem[];
  upcoming: PatientAppointmentItem[];
  past: PatientAppointmentItem[];
  total: number;
}

export interface QueueJoinResponse {
  entry: QueueEntryResponse;
  message: string;
}

export interface QueueResponse {
  id: string;
  opd_session_id: string;
  name: string;
  status: QueueStatus;
  current_position: number | null;
  created_at: string;
  updated_at: string;
}

export interface QueueSnapshotResponse {
  queue_id: string;
  queue_name: string;
  queue_date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  hospital_id?: string | null;
  hospital_name?: string | null;
  status: QueueStatus;
  opd_session_id: string;
  doctor_id: string | null;
  doctor_name: string | null;
  department_name: string | null;
  currently_serving: QueueEntryResponse | null;
  currently_called: QueueEntryResponse | null;
  next_patient: QueueEntryResponse | null;
  total_waiting: number;
  total_in_consultation: number;
  total_completed: number;
  total_no_show: number;
  total_booked?: number;
  total_active?: number;
  booked_entries?: QueueEntryResponse[];
  waiting_entries: QueueEntryResponse[];
  avg_consultation_duration_seconds?: number | null;
  avg_waiting_time_seconds?: number | null;
  current_consultation_elapsed_seconds?: number | null;
  delay_impact_minutes?: number | null;
  estimated_remaining_queue_time_minutes?: number | null;
}


// ---------------------------------------------------------------------------
// Prediction
// ---------------------------------------------------------------------------

export interface PredictionResponse {
  id: string;
  queue_entry_id: string;
  queue_id: string;
  predicted_start_at: string;
  predicted_end_at: string;
  predicted_duration_seconds: number;
  predicted_duration_minutes: number;
  uncertainty_margin_seconds: number;
  uncertainty_minutes: number;
  patients_ahead_count: number;
  explanation: string | null;
  explanation_text: string | null;
  explanation_json: Record<string, unknown>;
  feature_snapshot_json: Record<string, unknown>;
  model_type: string;
  model_version: string;
  prediction_status: string;
  trigger_event_id: string | null;
  is_meaningful_change: boolean;
  shift_minutes: number | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Travel / Arrival Plan
// ---------------------------------------------------------------------------

export type TravelMode = 'DRIVE' | 'TRANSIT' | 'WALK' | 'TWO_WHEELER';

export interface TravelEstimateResponse {
  travel_duration_seconds: number | null;
  travel_duration_minutes: number | null;
  travel_uncertainty_seconds: number | null;
  travel_uncertainty_minutes: number | null;
  route_distance_meters: number | null;
  driving_duration_seconds?: number | null;
  driving_duration_minutes?: number | null;
  driving_distance_meters?: number | null;
  bike_duration_seconds?: number | null;
  bike_duration_minutes?: number | null;
  bike_distance_meters?: number | null;
  walking_duration_seconds?: number | null;
  walking_duration_minutes?: number | null;
  walking_distance_meters?: number | null;
  provider: string;
  travel_status: string;
  is_traffic_aware: boolean;
  calculated_at: string;
}

export interface ArrivalPlanResponse {
  id: string;
  queue_entry_id: string;
  prediction_snapshot_id: string;
  travel_provider: string;
  travel_status: string;
  consultation_start_at: string;
  consultation_end_at: string;
  arrival_start_at: string | null;
  arrival_end_at: string | null;
  departure_start_at: string | null;
  departure_end_at: string | null;
  travel_duration_seconds: number | null;
  travel_duration_minutes: number | null;
  travel_uncertainty_seconds: number | null;
  travel_uncertainty_minutes: number | null;
  route_distance_meters: number | null;
  driving_duration_seconds?: number | null;
  driving_duration_minutes?: number | null;
  driving_distance_meters?: number | null;
  bike_duration_seconds?: number | null;
  bike_duration_minutes?: number | null;
  bike_distance_meters?: number | null;
  walking_duration_seconds?: number | null;
  walking_duration_minutes?: number | null;
  walking_distance_meters?: number | null;
  selected_travel_mode?: 'DRIVE' | 'TWO_WHEELER' | 'WALK' | string;
  origin_address?: string | null;
  arrival_buffer_minutes: number;
  is_meaningful_change: boolean;
  consultation_changed: boolean;
  travel_changed: boolean;
  explanation: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Doctor Daily & Weekly Schedules
// ---------------------------------------------------------------------------

export interface DoctorScheduleResponse {
  id: string;
  hospital_id: string;
  hospital_name?: string | null;
  doctor_id: string;
  doctor_name?: string | null;
  department_id: string;
  department_name?: string | null;
  schedule_date: string;
  start_time: string;
  end_time: string;
  start_time_formatted?: string;
  end_time_formatted?: string;
  status: 'AVAILABLE' | 'UNAVAILABLE' | 'ON_LEAVE' | string;
  appointments_count?: number;
  appointment_count?: number;
  opd_session_id?: string | null;
  queue_id?: string | null;
  queue_status?: string | null;
  created_at?: string;
}

export interface DoctorScheduleCreateRequest {
  doctor_id: string;
  department_id?: string;
  schedule_date: string;
  start_time: string;
  end_time: string;
  status?: 'AVAILABLE' | 'UNAVAILABLE' | 'ON_LEAVE' | string;
}

export interface DoctorScheduleBatchItem {
  schedule_date: string;
  start_time: string;
  end_time: string;
  status: string;
}

export interface DoctorScheduleBatchRequest {
  doctor_id: string;
  schedules: DoctorScheduleBatchItem[];
}

export interface AvailableDoctorItem {
  doctor_id: string;
  doctor_name: string;
  department_id: string;
  department_name: string;
  schedule_date: string;
  start_time: string;
  end_time: string;
  formatted_time: string;
  queue_id?: string | null;
  queue_name?: string | null;
  total_waiting: number;
}

export interface AvailableDoctorsResponse {
  hospital_id: string;
  hospital_name: string;
  date: string;
  total_doctors_available: number;
  doctors: AvailableDoctorItem[];
}

// ---------------------------------------------------------------------------
// WebSocket message discriminated union
// These types match the ACTUAL backend output from:
//   app/websocket/handlers.py
//   app/websocket/snapshot_service.py
// ---------------------------------------------------------------------------

/** Sent immediately on WebSocket connect (both patient and staff) */
export interface WsConnectedMessage {
  type: 'QUEUE_CONNECTED';
  version: number;
  timestamp: string;
  entry_id?: string;
  queue_id?: string;
  message: string;
}

/**
 * Patient QUEUE_SNAPSHOT — flat format from snapshot_service.py
 * NOT a QueueSnapshotResponse. Uses dedicated patient-safe fields.
 */
export interface WsPredictionSummary {
  predicted_start_at: string;
  predicted_end_at: string;
  uncertainty_seconds: number;
  patients_ahead: number;
  predicted_duration_minutes: number | null;
}

export interface WsArrivalPlanSummary {
  arrival_start_at: string | null;
  arrival_end_at: string | null;
  departure_start_at: string | null;
  departure_end_at: string | null;
  travel_status: string;
}

export interface WsPatientSnapshotMessage {
  type: 'QUEUE_SNAPSHOT';
  version: number;
  timestamp: string;
  queue_id: string;
  entry_id: string;
  queue_status: string;
  token_display: string;
  patient_status: string;
  position: number | null;
  patients_ahead: number;
  prediction: WsPredictionSummary | null;
  arrival_plan: WsArrivalPlanSummary | null;
  explanation: string | null;
  last_updated_at: string;
}

/**
 * Staff QUEUE_SNAPSHOT — wraps data in a `payload` key
 * from handlers.py websocket_staff_queue_endpoint
 */
export interface WsStaffSnapshotPayload {
  queue_id: string;
  queue_name: string | null;
  queue_status: string;
  doctor_name: string | null;
  department_name: string | null;
  currently_serving: Record<string, unknown> | null;
  currently_called: Record<string, unknown> | null;
  next_patient: Record<string, unknown> | null;
  waiting_count: number;
  in_consultation_count: number;
  completed_count: number;
  no_show_count: number;
}

export interface WsStaffSnapshotMessage {
  type: 'QUEUE_SNAPSHOT';
  version: number;
  timestamp: string;
  queue_id: string;
  payload: WsStaffSnapshotPayload;
}

/**
 * QUEUE_REFORECAST — dispatched by RealtimeDispatcher after prediction update
 */
export interface WsReforecastMessage {
  type: 'QUEUE_REFORECAST';
  queue_id: string;
  affected_count: number;
  predictions: PredictionResponse[];
}

export interface WsErrorMessage {
  type: 'ERROR';
  detail: string;
}

/** Patient WebSocket message union */
export type PatientWsMessage =
  | WsConnectedMessage
  | WsPatientSnapshotMessage
  | WsReforecastMessage
  | WsErrorMessage;

export interface WsQueueEntryAddedMessage {
  type: 'QUEUE_ENTRY_ADDED';
  queue_id: string;
  entry_id: string;
  token_number: number;
  appointment_date: string;
}

/** Staff WebSocket message union */
export type StaffWsMessage =
  | WsConnectedMessage
  | WsStaffSnapshotMessage
  | WsReforecastMessage
  | WsQueueEntryAddedMessage
  | WsErrorMessage;

/** Generic union (used when context is unknown) */
export type WsMessage = PatientWsMessage | StaffWsMessage;

// ---------------------------------------------------------------------------
// Misc
// ---------------------------------------------------------------------------

export interface ApiError {
  detail: string | { msg: string; type: string }[];
}

export interface ReforecastTriggerResponse {
  success: boolean;
  queue_id: string;
  reforecasted_count: number;
  meaningful_change_count: number;
  message: string;
}
