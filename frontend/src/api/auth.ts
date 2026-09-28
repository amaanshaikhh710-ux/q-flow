import { apiClient } from './client';
import type { TokenResponse, UserResponse } from '../types/api';

export interface RegisterPayload {
  name: string;
  email?: string;
  phone?: string;
  password: string;
}

export interface LoginPayload {
  identifier: string;
  password: string;
}

export const authApi = {
  register: async (payload: RegisterPayload): Promise<UserResponse> => {
    const { data } = await apiClient.post<UserResponse>('/auth/register', payload);
    return data;
  },

  login: async (payload: LoginPayload): Promise<TokenResponse> => {
    const { data } = await apiClient.post<TokenResponse>('/auth/login', payload);
    return data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout');
  },

  me: async (): Promise<UserResponse> => {
    const { data } = await apiClient.get<UserResponse>('/auth/me');
    return data;
  },
};
