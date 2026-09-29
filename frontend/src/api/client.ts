/**
 * Hardened Axios HTTP client with JWT Bearer token interceptor.
 * Base URL is configured via VITE_API_BASE_URL environment variable.
 * NEVER call Google Routes API from the frontend.
 */
import axios, { AxiosError } from 'axios';
import type { ApiError } from '../types/api';

const isLocalhost =
  typeof window !== 'undefined' &&
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

const DEFAULT_BACKEND_URL = isLocalhost
  ? 'http://localhost:8000'
  : 'https://q-flow-1.onrender.com';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || DEFAULT_BACKEND_URL;

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
});

// Attach JWT token from localStorage on every request
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('qflow_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle common HTTP error statuses centrally
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Clear token if unauthorized / token expired
      localStorage.removeItem('qflow_token');
      localStorage.removeItem('qflow_user');
    }
    return Promise.reject(error);
  }
);

/** Extract a clear, human-readable error message from any error */
export function extractErrorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    if (err.code === 'ECONNABORTED' || err.message.toLowerCase().includes('timeout')) {
      return 'The request timed out. Please check your internet connection or try again.';
    }
    if (!err.response) {
      return 'Unable to reach the server. Please ensure the backend is running on ' + BASE_URL;
    }

    const status = err.response.status;
    const data = err.response.data as ApiError | undefined;

    if (data?.detail) {
      if (typeof data.detail === 'string') return data.detail;
      if (Array.isArray(data.detail)) {
        return data.detail.map((d) => d.msg).join('; ');
      }
    }

    switch (status) {
      case 401:
        return 'Session expired or invalid credentials. Please log in again.';
      case 403:
        return 'Access denied. You do not have permission to view or perform this action.';
      case 404:
        return 'The requested resource was not found.';
      case 409:
        return 'Conflict: Operation could not be completed with the current queue state.';
      case 422:
        return 'Validation error: Please verify your input and try again.';
      case 500:
        return 'Server error. Our medical queuing service encountered an unexpected issue.';
      default:
        return `Request failed with status code ${status}.`;
    }
  }

  if (err instanceof Error) {
    return err.message;
  }
  return 'An unexpected error occurred.';
}

export const API_BASE_URL = BASE_URL;
