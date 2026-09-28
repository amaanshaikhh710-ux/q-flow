/**
 * Typed WebSocket hooks for Q-FLOW real-time updates.
 *
 * - Sends JWT token as ?token=<jwt> query param
 * - Auto-reconnects with exponential backoff (max 30s)
 * - Calls onMessage with correctly-typed discriminated union
 * - Cleans up on unmount
 * - WS failures do NOT break REST fallback — they are enhancement-only
 */
import { useEffect, useRef, useCallback } from 'react';
import type { PatientWsMessage, StaffWsMessage, WsMessage } from '../types/api';
import { API_BASE_URL } from '../api/client';

function getWsBase(): string {
  if (typeof window === 'undefined') return 'ws://localhost:8000';
  if (API_BASE_URL.startsWith('https://')) {
    return API_BASE_URL.replace(/^https:\/\//, 'wss://');
  }
  if (API_BASE_URL.startsWith('http://')) {
    return API_BASE_URL.replace(/^http:\/\//, 'ws://');
  }
  const loc = window.location;
  const protocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${loc.host}${API_BASE_URL}`;
}

const WS_BASE = getWsBase();

interface UseWebSocketOptions<T> {
  path: string;
  token: string | null;
  onMessage: (msg: T) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  enabled?: boolean;
}

function createWebSocketHook<T>() {
  return function useTypedWebSocket({
    path,
    token,
    onMessage,
    onConnect,
    onDisconnect,
    enabled = true,
  }: UseWebSocketOptions<T>) {
    const wsRef = useRef<WebSocket | null>(null);
    const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const retryDelayRef = useRef(2000);
    const mountedRef = useRef(true);
    const onMessageRef = useRef(onMessage);
    const onConnectRef = useRef(onConnect);
    const onDisconnectRef = useRef(onDisconnect);
    onMessageRef.current = onMessage;
    onConnectRef.current = onConnect;
    onDisconnectRef.current = onDisconnect;

    const connect = useCallback(() => {
      if (!enabled || !token || !mountedRef.current) return;
      // Don't reconnect if already open
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

      const url = `${WS_BASE}${path}?token=${encodeURIComponent(token)}`;

      let ws: WebSocket;
      try {
        ws = new WebSocket(url);
      } catch {
        // WebSocket URL invalid — don't retry
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        retryDelayRef.current = 2000; // reset backoff on successful connect
        onConnectRef.current?.();
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const msg = JSON.parse(event.data as string) as T;
          onMessageRef.current(msg);
        } catch {
          // Ignore non-JSON frames
        }
      };

      ws.onclose = () => {
        onDisconnectRef.current?.();
        if (!mountedRef.current) return;
        // Exponential backoff: 2s → 4s → 8s → … capped at 30s
        const delay = retryDelayRef.current;
        retryDelayRef.current = Math.min(delay * 2, 30000);
        retryRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        // onclose fires after onerror, which handles reconnect
        ws.close();
      };
    }, [enabled, token, path]);

    useEffect(() => {
      mountedRef.current = true;
      connect();
      return () => {
        mountedRef.current = false;
        if (retryRef.current) clearTimeout(retryRef.current);
        if (wsRef.current) {
          wsRef.current.onclose = null; // prevent reconnect on intentional unmount
          wsRef.current.close();
          wsRef.current = null;
        }
      };
    }, [connect]);
  };
}

/** Patient-typed WebSocket hook — matches actual backend patient snapshot format */
export const usePatientWebSocket = createWebSocketHook<PatientWsMessage>();

/** Staff-typed WebSocket hook — matches actual backend staff snapshot format */
export const useStaffWebSocket = createWebSocketHook<StaffWsMessage>();

/** Generic WebSocket hook fallback */
export const useWebSocket = createWebSocketHook<WsMessage>();
