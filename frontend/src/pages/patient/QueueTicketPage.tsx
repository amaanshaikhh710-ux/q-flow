import { useState, useCallback, useRef, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  BellRing,
  ArrowRight,
  RefreshCw,
  Building2,
} from 'lucide-react';
import { queueEntriesApi } from '../../api/queueEntries';
import { predictionsApi } from '../../api/predictions';
import { queuesApi } from '../../api/queues';
import { travelApi } from '../../api/travel';
import { useAuth } from '../../store/AuthContext';
import { usePatientWebSocket } from '../../hooks/useWebSocket';
import { BrandLogo } from '../../components/BrandLogo';
import { SkeletonCard } from '../../components/Skeleton';
import { ErrorState } from '../../components/ErrorState';
import { LiveIndicator } from '../../components/StatusIndicator';
import { EntryStatusBadge } from '../../components/StatusBadges';
import { QueueProgress } from '../../components/QueueProgress';
import { EtaChangeBanner, type EtaChangeData } from '../../components/EtaChangeBanner';
import { WhyEstimate } from '../../components/WhyEstimate';
import { ArrivalPlanSummaryCard } from '../../components/ArrivalPlanSummaryCard';
import { extractErrorMessage } from '../../api/client';
import {
  formatTimeWindow,
  formatRelative,
  formatDoctorName,
} from '../../utils/format';
import type {
  PatientWsMessage,
  PredictionResponse,
  WsPatientSnapshotMessage,
} from '../../types/api';

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

export default function QueueTicketPage() {
  const { entryId } = useParams<{ entryId: string }>();
  const { token, user } = useAuth();
  const queryClient = useQueryClient();

  const [wsConnected, setWsConnected] = useState(false);
  const [wsReconnecting, setWsReconnecting] = useState(false);
  const [etaChange, setEtaChange] = useState<EtaChangeData | null>(null);

  // Live overrides received via WebSocket
  const [livePosition, setLivePosition] = useState<number | null>(null);
  const [livePatientsAhead, setLivePatientsAhead] = useState<number | null>(null);
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  const [livePrediction, setLivePrediction] = useState<PredictionResponse | null>(null);

  const prevStartRef = useRef<string | null>(null);

  const isValidParam = Boolean(entryId && entryId !== ':entryId');

  // 1. Authoritative Entry Query
  const {
    data: entry,
    isLoading: entryLoading,
    isError: entryIsError,
    error: entryError,
    refetch: refetchEntry,
  } = useQuery({
    queryKey: ['entry', entryId],
    queryFn: () => queueEntriesApi.getEntry(entryId!),
    enabled: isValidParam,
    staleTime: 30_000,
    retry: 1,
  });

  // 2. Authoritative Prediction Query
  const {
    data: prediction,
    refetch: refetchPrediction,
  } = useQuery({
    queryKey: ['prediction', entryId],
    queryFn: () => predictionsApi.getPrediction(entryId!),
    enabled: isValidParam,
    staleTime: 30_000,
    retry: false,
  });

  // 3. Queue Session Snapshot (for Doctor & Dept names)
  const { data: queueSnapshot } = useQuery({
    queryKey: ['queue-snapshot', entry?.queue_id],
    queryFn: () => queuesApi.getSnapshot(entry!.queue_id),
    enabled: Boolean(entry?.queue_id),
    staleTime: 60_000,
  });

  // 4. Travel Arrival Plan Query
  const { data: arrivalPlan, isLoading: planLoading } = useQuery({
    queryKey: ['arrival-plan', entryId],
    queryFn: () => travelApi.getArrivalPlan(entryId!),
    enabled: isValidParam,
    staleTime: 20_000,
    retry: false,
  });

  // Active prediction reference
  const currentPrediction = livePrediction ?? prediction;
  if (currentPrediction?.predicted_start_at && !prevStartRef.current) {
    prevStartRef.current = currentPrediction.predicted_start_at;
  }

  // WebSocket real-time updates
  const handleWsMessage = useCallback(
    (msg: PatientWsMessage) => {
      if (msg.type === 'QUEUE_CONNECTED') {
        setWsConnected(true);
        setWsReconnecting(false);
      } else if (msg.type === 'QUEUE_SNAPSHOT') {
        const snap = msg as WsPatientSnapshotMessage;
        setWsConnected(true);
        setWsReconnecting(false);

        if (snap.position != null) setLivePosition(snap.position);
        if (snap.patients_ahead != null) setLivePatientsAhead(snap.patients_ahead);
        if (snap.patient_status) setLiveStatus(snap.patient_status);

        if (snap.prediction) {
          setLivePrediction((prev) => ({
            id: prev?.id || 'live-snap',
            queue_entry_id: entryId!,
            queue_id: snap.queue_id,
            predicted_start_at: snap.prediction!.predicted_start_at,
            predicted_end_at: snap.prediction!.predicted_end_at,
            predicted_duration_seconds:
              (snap.prediction!.predicted_duration_minutes || 10) * 60,
            predicted_duration_minutes:
              snap.prediction!.predicted_duration_minutes || 10,
            uncertainty_margin_seconds: snap.prediction!.uncertainty_seconds,
            uncertainty_minutes: Math.round(snap.prediction!.uncertainty_seconds / 60),
            patients_ahead_count: snap.prediction!.patients_ahead,
            explanation: snap.explanation || null,
            explanation_text: snap.explanation || null,
            explanation_json: {},
            feature_snapshot_json: {},
            model_type: 'uncertainty_aware_engine',
            model_version: 'v2',
            prediction_status: 'ACTIVE',
            trigger_event_id: null,
            is_meaningful_change: false,
            shift_minutes: null,
            created_at: new Date().toISOString(),
          }));
        }
      } else if (msg.type === 'QUEUE_REFORECAST') {
        setWsConnected(true);
        setWsReconnecting(false);

        const rawMsg = msg as Record<string, any>;
        const pred = rawMsg.prediction || (rawMsg.predictions && Array.isArray(rawMsg.predictions) ? rawMsg.predictions.find((p: any) => p.queue_entry_id === entryId) : null);
        const explanationText = rawMsg.explanation?.message || (typeof rawMsg.explanation === 'string' ? rawMsg.explanation : pred?.explanation) || 'Queue priority or operational adjustment upstream';

        if (pred) {
          const oldStart = prevStartRef.current;
          const newStart = pred.predicted_start_at;

          if (oldStart && oldStart !== newStart) {
            const shiftMin = pred.shift_minutes || (oldStart && newStart ? Math.round((new Date(newStart).getTime() - new Date(oldStart).getTime()) / 60000) : 0);
            setEtaChange({
              previousStart: oldStart,
              newStart: newStart,
              shiftMinutes: shiftMin,
              reason: explanationText,
              isEmergency: explanationText.toLowerCase().includes('emergency'),
            });
            prevStartRef.current = newStart;
          }

          setLivePrediction((prev) => ({
            id: prev?.id || 'live-reforecast',
            queue_entry_id: entryId!,
            queue_id: rawMsg.queue_id || prev?.queue_id || '',
            predicted_start_at: pred.predicted_start_at,
            predicted_end_at: pred.predicted_end_at,
            predicted_duration_seconds: (pred.predicted_duration_minutes || 10) * 60,
            predicted_duration_minutes: pred.predicted_duration_minutes || 10,
            uncertainty_margin_seconds: pred.uncertainty_seconds ?? (pred.uncertainty_minutes ? pred.uncertainty_minutes * 60 : 300),
            uncertainty_minutes: pred.uncertainty_minutes ?? Math.round((pred.uncertainty_seconds ?? 300) / 60),
            patients_ahead_count: pred.patients_ahead ?? prev?.patients_ahead_count ?? 0,
            explanation: explanationText,
            explanation_text: explanationText,
            explanation_json: {},
            feature_snapshot_json: {},
            model_type: 'uncertainty_aware_engine',
            model_version: 'v2',
            prediction_status: 'ACTIVE',
            trigger_event_id: null,
            is_meaningful_change: true,
            shift_minutes: pred.shift_minutes ?? null,
            created_at: new Date().toISOString(),
          }));
        }

        void queryClient.invalidateQueries({ queryKey: ['entry', entryId] });
        void queryClient.invalidateQueries({ queryKey: ['arrival-plan', entryId] });
      } else if (msg.type === 'ERROR') {
        setWsConnected(false);
      }
    },
    [entryId, queryClient]
  );

  usePatientWebSocket({
    path: `/api/v1/ws/patient/${entryId}`,
    token,
    onMessage: handleWsMessage,
    onConnect: () => {
      setWsConnected(true);
      setWsReconnecting(false);
    },
    onDisconnect: () => {
      setWsConnected(false);
      setWsReconnecting(true);
    },
    enabled: isValidParam && !!token,
  });

  useEffect(() => {
    if (window.location.hash === '#travel') {
      const timer = setTimeout(() => {
        const el = document.getElementById('travel');
        if (el) {
          el.scrollIntoView({ behavior: 'smooth' });
        }
      }, 200);
      return () => clearTimeout(timer);
    }
  }, []);

  if (!isValidParam) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
        <header className="border-b border-slate-200/90 bg-white sticky top-0 z-20">
          <div className="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between">
            <BrandLogo size="sm" showTagline={false} linkTo="/dashboard" />
          </div>
        </header>
        <main className="flex-1 max-w-lg w-full mx-auto px-4 py-8">
          <ErrorState
            title="Ticket Not Found"
            message="Please provide a valid ticket ID to view queue status."
            backTo="/dashboard"
            backLabel="My Appointments"
          />
        </main>
      </div>
    );
  }

  if (entryLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
        <header className="border-b border-slate-200/90 bg-white sticky top-0 z-20">
          <div className="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between">
            <BrandLogo size="sm" showTagline={false} linkTo="/dashboard" />
            <div className="h-6 w-20 bg-slate-100 rounded-full animate-pulse" />
          </div>
        </header>
        <main className="flex-1 max-w-xl w-full mx-auto px-4 py-6 space-y-4">
          <SkeletonCard className="h-64" />
          <SkeletonCard className="h-44" />
        </main>
      </div>
    );
  }

  if (entryIsError || !entry) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
        <header className="border-b border-slate-200/90 bg-white sticky top-0 z-20">
          <div className="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between">
            <BrandLogo size="sm" showTagline={false} linkTo="/dashboard" />
          </div>
        </header>
        <main className="flex-1 max-w-lg w-full mx-auto px-4 py-8">
          <ErrorState
            title="Ticket Verification Failed"
            message={extractErrorMessage(entryError)}
            onRetry={() => {
              refetchEntry();
              refetchPrediction();
            }}
            backTo="/dashboard"
            backLabel="My Appointments"
          />
        </main>
      </div>
    );
  }

  const effectiveStatus = (liveStatus ?? entry.status ?? '').toUpperCase();
  const effectivePosition = livePosition ?? entry.position;
  const effectivePatientsAhead =
    livePatientsAhead ??
    (effectivePosition != null && effectivePosition > 1 ? effectivePosition - 1 : 0);

  const isActive = [
    'BOOKED',
    'ARRIVED',
    'WAITING',
    'CALLED',
    'IN_CONSULTATION',
    'RETURNED',
    'TEMPORARILY_LEFT',
  ].includes(effectiveStatus);

  const greeting = getGreeting();
  const patientDisplayName = user?.name ? user.name.split(' ')[0] : 'Patient';

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans selection:bg-blue-100 selection:text-blue-900 pb-16">
      {/* 1. Minimal Header */}
      <header className="border-b border-slate-200/90 bg-white/95 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <BrandLogo size="sm" showTagline={false} linkTo="/dashboard" />
          <div className="flex items-center gap-3">
            <LiveIndicator connected={wsConnected} isConnecting={wsReconnecting} />
            <button
              type="button"
              onClick={() => {
                refetchEntry();
                refetchPrediction();
              }}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              title="Refresh status"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-xl w-full mx-auto px-4 sm:px-6 py-5 space-y-4 animate-fade-up">
        {/* 2. Patient Context */}
        <div className="flex items-center justify-between pt-1">
          <div>
            <h1 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
              {greeting}, {patientDisplayName}
            </h1>
            <p className="text-xs text-slate-500 font-medium flex items-center gap-1.5 mt-0.5">
              <span>{queueSnapshot?.department_name || 'Cardiology'}</span>
              <span>•</span>
              <span>{formatDoctorName(queueSnapshot?.doctor_name, 'Dr. Attending Specialist')}</span>
            </p>
          </div>
          <span className="text-[11px] text-slate-400 font-medium">
            Joined {formatRelative(entry.joined_at)}
          </span>
        </div>

        {/* Real-Time "Why did my ETA change?" Banner */}
        {etaChange && (
          <EtaChangeBanner
            data={etaChange}
            onDismiss={() => setEtaChange(null)}
          />
        )}

        {/* Called Notification Banner */}
        {effectiveStatus === 'CALLED' && (
          <div className="rounded-2xl bg-blue-900 text-white p-5 shadow-sm flex items-center gap-3.5 border border-blue-800 animate-fade-up">
            <div className="w-10 h-10 rounded-xl bg-blue-800 flex items-center justify-center text-white shrink-0">
              <BellRing className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h2 className="text-sm font-bold">You've Been Called!</h2>
              <p className="text-xs text-blue-200 mt-0.5">
                Please proceed directly to the consultation room now.
              </p>
            </div>
          </div>
        )}

        {/* In Consultation Notice */}
        {effectiveStatus === 'IN_CONSULTATION' && (
          <div className="rounded-2xl bg-emerald-900 text-white p-5 shadow-sm flex items-center gap-3.5 border border-emerald-800 animate-fade-up">
            <div className="w-10 h-10 rounded-xl bg-emerald-800 flex items-center justify-center text-white shrink-0">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold">Consultation in Progress</h2>
              <p className="text-xs text-emerald-200 mt-0.5">
                You are currently inside with the clinician.
              </p>
            </div>
          </div>
        )}

        {/* 3. HERO LIVE TICKET CARD */}
        <div className="bg-white rounded-3xl p-6 sm:p-7 border border-slate-200/90 shadow-sm space-y-5">
          {/* Top Token Row */}
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 block">
                Queue Token Number
              </span>
              <span className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight font-mono">
                {entry.token_display}
              </span>
            </div>
            <EntryStatusBadge status={effectiveStatus} />
          </div>

          {/* 4. ETA — PRIMARY FOCAL POINT (Visually Dominates Screen) */}
          <div className="p-5 sm:p-6 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-black uppercase tracking-wider text-slate-500">
                Estimated Consultation Window
              </span>
              {currentPrediction?.uncertainty_minutes != null && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200/70">
                  ±{currentPrediction.uncertainty_minutes} min
                </span>
              )}
            </div>

            <div className="text-2xl sm:text-3xl md:text-4xl font-black text-slate-900 tracking-tight font-sans whitespace-nowrap overflow-hidden text-ellipsis">
              {currentPrediction?.predicted_start_at
                ? formatTimeWindow(currentPrediction.predicted_start_at, currentPrediction.predicted_end_at)
                : 'Calculating Window...'}
            </div>

            <p className="text-xs text-slate-500">
              Your estimated consultation window • Continuously calibrated
            </p>

            {currentPrediction?.uncertainty_minutes != null && (
              <div className="pt-2.5 border-t border-slate-200/70 flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-[11px] text-slate-400">
                <span className="font-semibold text-slate-600">Estimate uncertainty:</span>
                <span>Your consultation time can shift as the queue changes.</span>
              </div>
            )}
          </div>

          {/* 5. Supporting Metrics: Patients Ahead & Recent Pace */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80">
              <span className="text-2xl sm:text-3xl font-black text-slate-900 block tracking-tight">
                {effectivePatientsAhead}
              </span>
              <span className="text-xs font-semibold text-slate-500">
                Patients ahead
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80">
              <span className="text-2xl sm:text-3xl font-black text-slate-900 block tracking-tight">
                {currentPrediction?.predicted_duration_minutes != null
                  ? `~${currentPrediction.predicted_duration_minutes} min`
                  : <span className="text-sm font-normal text-slate-400">Calibrating...</span>}
              </span>
              <span className="text-xs font-semibold text-slate-500">
                Recent consultation pace
              </span>
            </div>
          </div>

          {/* 6. Subtle Queue Progress */}
          <QueueProgress
            position={effectivePosition}
            totalWaiting={queueSnapshot?.total_waiting ?? (effectivePatientsAhead + 1)}
            status={effectiveStatus as any}
          />
        </div>

        {/* 7. Why This Estimate? (Expandable Breakdown) */}
        <WhyEstimate
          position={effectivePosition}
          patientsAhead={effectivePatientsAhead}
          recentPaceMinutes={currentPrediction?.predicted_duration_minutes}
          doctorName={queueSnapshot?.doctor_name}
          explanation={currentPrediction?.explanation || currentPrediction?.explanation_text}
        />

        {/* 8. Integrated Arrival Plan Card */}
        {isActive && (
          <div id="travel">
            <ArrivalPlanSummaryCard
              entryId={entryId!}
              plan={arrivalPlan}
              isLoading={planLoading}
            />
          </div>
        )}

        {/* Completed State */}
        {(effectiveStatus === 'COMPLETED' || effectiveStatus === 'NO_SHOW') && (
          <div className="p-6 rounded-3xl bg-white border border-slate-200 text-center space-y-4 shadow-2xs">
            <p className="text-base font-bold text-slate-900">
              {effectiveStatus === 'COMPLETED'
                ? 'Consultation Completed'
                : 'Ticket Marked as No-Show'}
            </p>
            <p className="text-xs text-slate-500 max-w-xs mx-auto">
              {effectiveStatus === 'COMPLETED'
                ? 'Thank you for visiting. We hope your consultation went smoothly.'
                : 'Your token was flagged as no-show by clinical reception.'}
            </p>
            <Link
              to="/book"
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs shadow-xs"
            >
              <span>Book Another Appointment</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        )}
      </main>
    </div>
  );
}
