import { apiClient } from './client';
import type { PredictionResponse } from '../types/api';

export const predictionsApi = {
  getPrediction: async (entryId: string): Promise<PredictionResponse> => {
    const { data } = await apiClient.get<PredictionResponse>(
      `/queue-entries/${entryId}/prediction`
    );
    return data;
  },

  getPredictionHistory: async (
    entryId: string
  ): Promise<{ queue_entry_id: string; total_snapshots: number; history: PredictionResponse[] }> => {
    const { data } = await apiClient.get(
      `/queue-entries/${entryId}/prediction/history`
    );
    return data;
  },
};
