import { apiClient } from './client';
import type { ArrivalPlanResponse, TravelMode } from '../types/api';

export interface TravelOriginPayload {
  latitude: number;
  longitude: number;
  travel_mode: TravelMode;
  origin_address?: string;
}

export interface ResolvedLocationItem {
  name: string;
  formatted_address: string;
  latitude: number;
  longitude: number;
}

export interface ResolveAddressResponse {
  query: string;
  results: ResolvedLocationItem[];
  resolved_by: string;
}

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

export const travelApi = {
  resolveAddress: async (query: string): Promise<ResolveAddressResponse> => {
    const { data } = await apiClient.post<ResolveAddressResponse>(
      '/travel/resolve-address',
      { query }
    );
    return data;
  },

  setOrigin: async (
    entryId: string,
    payload: TravelOriginPayload
  ): Promise<ArrivalPlanResponse> => {
    const { data } = await apiClient.post<ArrivalPlanResponse>(
      `/queue-entries/${entryId}/travel-origin`,
      payload
    );
    return data;
  },

  setTravelMode: async (
    entryId: string,
    travelMode: 'DRIVE' | 'TWO_WHEELER' | 'WALK' | string
  ): Promise<ArrivalPlanResponse> => {
    const { data } = await apiClient.post<ArrivalPlanResponse>(
      `/queue-entries/${entryId}/travel-mode`,
      { travel_mode: travelMode }
    );
    return data;
  },

  getTravelEstimate: async (entryId: string): Promise<TravelEstimateResponse> => {
    const { data } = await apiClient.get<TravelEstimateResponse>(
      `/queue-entries/${entryId}/travel`
    );
    return data;
  },

  getArrivalPlan: async (entryId: string): Promise<ArrivalPlanResponse> => {
    const { data } = await apiClient.get<ArrivalPlanResponse>(
      `/queue-entries/${entryId}/arrival-plan`
    );
    return data;
  },

  getArrivalPlanHistory: async (
    entryId: string
  ): Promise<{
    queue_entry_id: string;
    total_plans: number;
    history: ArrivalPlanResponse[];
  }> => {
    const { data } = await apiClient.get(
      `/queue-entries/${entryId}/arrival-plan/history`
    );
    return data;
  },
};
