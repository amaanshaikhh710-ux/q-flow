import { useState, useCallback, useEffect } from 'react';
import { useNavigate, useParams, useSearchParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { queuesApi } from '../../api/queues';
import { queueEntriesApi } from '../../api/queueEntries';
import { useAuth } from '../../store/AuthContext';
import { useStaffWebSocket } from '../../hooks/useWebSocket';
import { PageSpinner } from '../../components/Spinner';
import { ErrorState } from '../../components/ErrorState';
import { LiveIndicator } from '../../components/StatusIndicator';
import { extractErrorMessage } from '../../api/client';
import { formatRelative, formatDoctorName } from '../../utils/format';
import {
  normalizeToCanonicalDate,
  getHospitalTodayDateString,
  toCanonicalDateString,
} from '../../utils/dateUtils';
import { StaffDatePicker } from '../../components/StaffDatePicker';
import type {
  StaffWsMessage,
  QueueEntryResponse,
} from '../../types/api';
import {
  Users,
  Activity,
  CheckCircle,
  Phone,
  UserX,
  Coffee,
  Clock,
  Zap,
  RefreshCw,
  Pause,
  Play,
  LogOut,
  LayoutDashboard,
  ArrowLeft,
  Sparkles,
  Calendar,
  UserCheck,
  History,
  UserPlus,
  TrendingUp,
} from 'lucide-react';

import EmergencyModal from './EmergencyModal';
import DoctorBreakModal from './DoctorBreakModal';
import DoctorDelayModal from './DoctorDelayModal';
import TemporaryLeaveModal from './TemporaryLeaveModal';
import PriorityChangeModal from './PriorityChangeModal';
import { StaffBookModal } from './StaffBookModal';

interface StatsCardProps {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  bgClass: string;
  textClass: string;
}

function StatsCard({ label, value, icon, bgClass, textClass }: StatsCardProps) {
  return (
    <div className="bg-white rounded-2xl p-5 border border-slate-200/90 shadow-2xs flex items-center justify-between">
      <div>
        <p className="text-xs font-bold uppercase tracking-wider text-slate-400">{label}</p>
        <p className="mt-1 text-2xl font-black text-slate-900 tracking-tight">{value}</p>
      </div>
      <div className={`w-12 h-12 rounded-2xl ${bgClass} ${textClass} flex items-center justify-center`}>
        {icon}
      </div>
    </div>
  );
}

export default function QueueControlPage() {
  const { queueId } = useParams<{ queueId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const rawDateParam = searchParams.get('date');
  const targetDate = normalizeToCanonicalDate(rawDateParam) || undefined;
  const navigate = useNavigate();
  const { token, user, logout } = useAuth();
  const queryClient = useQueryClient();

  const [wsConnected, setWsConnected] = useState(false);
  const [wsReconnecting, setWsReconnecting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Modal dialog states
  const [showEmergency, setShowEmergency] = useState(false);
  const [showBreak, setShowBreak] = useState(false);
  const [showDelay, setShowDelay] = useState(false);
  const [isBookModalOpen, setIsBookModalOpen] = useState(false);
  const [selectedEntryForLeave, setSelectedEntryForLeave] = useState<QueueEntryResponse | null>(null);
  const [selectedEntryForPriority, setSelectedEntryForPriority] = useState<QueueEntryResponse | null>(null);

  const isValidParam = Boolean(queueId && queueId !== ':queueId');

  // Authoritative Queue snapshot query
  const {
    data: snapshot,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['snapshot', queueId, targetDate],
    queryFn: () => queuesApi.getSnapshot(queueId!, targetDate),
    enabled: isValidParam,
    staleTime: 10_000,
  });

  const effectiveDate = targetDate || toCanonicalDateString(snapshot?.queue_date) || getHospitalTodayDateString();

  // Query hospital OPD clinic queues for the active date so staff can switch without leaving
  const { data: hospitalQueuesData } = useQuery({
    queryKey: ['staff-queues-for-date', effectiveDate, user?.hospital_id],
    queryFn: () => queuesApi.getQueuesForDate(effectiveDate),
    enabled: Boolean(user?.hospital_id && effectiveDate),
    staleTime: 10_000,
  });
  const sessionQueues = hospitalQueuesData?.queues || [];

  // Sanitize and replace URL parameter if corrupted (e.g. 0002)
  useEffect(() => {
    if (rawDateParam && !normalizeToCanonicalDate(rawDateParam)) {
      const cleanDate = toCanonicalDateString(snapshot?.queue_date) || getHospitalTodayDateString();
      setSearchParams({ date: cleanDate }, { replace: true });
    }
  }, [rawDateParam, snapshot?.queue_date, setSearchParams]);

  // Synchronize active queue ID if date resolution mapped to a date-specific queue
  useEffect(() => {
    if (snapshot?.queue_id && queueId && snapshot.queue_id !== queueId) {
      navigate(`/staff/queue/${snapshot.queue_id}?date=${effectiveDate}`, { replace: true });
    }
  }, [snapshot?.queue_id, snapshot?.queue_date, queueId, effectiveDate, navigate]);

  const activeQueueId = snapshot?.queue_id || queueId;

  // Staff WebSocket connection
  const handleWsMessage = useCallback(
    (msg: StaffWsMessage) => {
      if (msg.type === 'QUEUE_CONNECTED') {
        setWsConnected(true);
        setWsReconnecting(false);
      } else if (msg.type === 'QUEUE_SNAPSHOT' || msg.type === 'QUEUE_REFORECAST' || msg.type === 'QUEUE_ENTRY_ADDED') {
        setWsConnected(true);
        setWsReconnecting(false);
        // Refresh authoritative snapshot
        void queryClient.invalidateQueries({ queryKey: ['snapshot', queueId] });
      } else if (msg.type === 'ERROR') {
        setWsConnected(false);
      }
    },
    [queueId, queryClient]
  );

  useStaffWebSocket({
    path: `/api/v1/ws/queue/${queueId}`,
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

  const withAction = (fn: () => Promise<unknown>) => async () => {
    setActionError(null);
    try {
      await fn();
      void queryClient.invalidateQueries({ queryKey: ['snapshot', queueId] });
      if (activeQueueId && activeQueueId !== queueId) {
        void queryClient.invalidateQueries({ queryKey: ['snapshot', activeQueueId] });
      }
    } catch (err) {
      setActionError(extractErrorMessage(err));
    }
  };

  const handleCallNext = withAction(() => queuesApi.callNext(activeQueueId!));
  const handlePause = withAction(() => queuesApi.pause(activeQueueId!));
  const handleResume = withAction(() => queuesApi.resume(activeQueueId!));
  const handleReforecast = withAction(() => queuesApi.reforecast(activeQueueId!));
  const handleEndQueue = withAction(() => queuesApi.endQueue(activeQueueId!));

  const handleCall = (id: string) => withAction(() => queueEntriesApi.call(id))();
  const handleStartConsultation = (id: string) =>
    withAction(() => queueEntriesApi.startConsultation(id))();
  const handleCompleteConsultation = (id: string) =>
    withAction(() => queueEntriesApi.completeConsultation(id))();
  const handleNoShow = (id: string) => withAction(() => queueEntriesApi.noShow(id))();
  const handleReturn = (id: string) => withAction(() => queueEntriesApi.return(id))();
  const handleArrive = (id: string) => withAction(() => queueEntriesApi.arrive(id))();
  const handleWait = (id: string) => withAction(() => queueEntriesApi.wait(id))();


  if (!isValidParam) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans p-6">
        <ErrorState
          title="Invalid Queue ID"
          message="Please select a valid queue to open the clinical control center."
          backTo="/staff"
          backLabel="Back to Staff Portal"
        />
      </div>
    );
  }

  if (isLoading) return <PageSpinner />;

  if (isError || !snapshot) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans p-6">
        <ErrorState
          title="Failed to Load Queue Snapshot"
          message={extractErrorMessage(error)}
          onRetry={() => refetch()}
          backTo="/staff"
          backLabel="Return to Portal"
        />
      </div>
    );
  }

  const isPaused = (snapshot.status ?? '').toUpperCase() === 'PAUSED';

  return (
    <div className="min-h-screen bg-slate-100 flex font-sans">
      {/* 1. PROFESSIONAL DESKTOP SIDEBAR (PART P) */}
      <aside className="hidden lg:flex w-64 bg-slate-900 text-slate-300 flex-col shrink-0 border-r border-slate-800 select-none">
        <div className="p-6 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center text-white">
              <Activity className="w-4 h-4" />
            </div>
            <span className="text-lg font-black tracking-tight text-white">Q-FLOW</span>
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-md">
            Staff
          </span>
        </div>

        <nav className="flex-1 p-4 space-y-1.5 text-xs font-semibold">
          <Link
            to="/staff"
            className="flex items-center gap-3 px-3.5 py-2.5 rounded-xl bg-slate-800 text-white transition-colors"
          >
            <LayoutDashboard className="w-4 h-4 text-blue-400" />
            <span>Live Queue Control</span>
          </Link>
          <Link
            to="/staff/historical"
            className="flex items-center gap-3 px-3.5 py-2.5 rounded-xl hover:bg-slate-800/60 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <History className="w-4 h-4 text-cyan-400" />
            <span>Historical Reports</span>
          </Link>
        </nav>


        <div className="p-4 border-t border-slate-800 text-xs">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="font-bold text-white">{user?.name}</p>
              <p className="text-[11px] text-slate-500 capitalize">{user?.role} Access</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void logout().then(() => navigate('/login'))}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-slate-800/80 hover:bg-red-500/20 hover:text-red-400 text-slate-400 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* 2. MAIN CONTROL CENTER CONTENT */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              to="/staff"
              className="lg:hidden p-2 rounded-xl text-slate-600 hover:bg-slate-100"
              aria-label="Back"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-xl font-bold text-slate-900">{snapshot.queue_name}</h1>
                <span
                  className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                    isPaused
                      ? 'bg-amber-100 text-amber-800'
                      : 'bg-emerald-100 text-emerald-800'
                  }`}
                >
                  {snapshot.status}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-slate-600 mt-1">
                <span>
                  <strong className="text-slate-800">DOCTOR:</strong> {formatDoctorName(snapshot.doctor_name)}
                </span>
                <span>•</span>
                <span>
                  <strong className="text-slate-800">DEPARTMENT:</strong> {snapshot.department_name}
                </span>
                <span>•</span>
                <StaffDatePicker
                  selectedDate={
                    targetDate || toCanonicalDateString(snapshot?.queue_date) || getHospitalTodayDateString()
                  }
                  onSelectDate={(newDate) => {
                    setSearchParams({ date: newDate }, { replace: true });
                  }}
                  labelPrefix="QUEUE DATE:"
                />
                {snapshot.start_time && (
                  <>
                    <span>•</span>
                    <span className="inline-flex items-center gap-1.5 text-emerald-800 font-bold bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200">
                      <Clock className="w-3.5 h-3.5 text-emerald-600" />
                      <span className="text-[11px] uppercase tracking-wider">OPD TIME:</span>
                      <span className="text-xs">{snapshot.start_time} – {snapshot.end_time || 'End'}</span>
                    </span>
                  </>
                )}
                {sessionQueues.length > 1 && (
                  <>
                    <span>•</span>
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-slate-800 text-[11px] uppercase">SWITCH CLINIC:</span>
                      <select
                        value={activeQueueId}
                        onChange={(e) => navigate(`/staff/queue/${e.target.value}?date=${effectiveDate}`)}
                        className="text-xs font-semibold bg-white border border-slate-200 rounded-lg px-2 py-1 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                      >
                        {sessionQueues.map((sq: any) => (
                          <option key={sq.queue_id} value={sq.queue_id}>
                            {formatDoctorName(sq.doctor_name)} ({sq.department_name} • {sq.start_time}-{sq.end_time})
                          </option>
                        ))}
                      </select>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <LiveIndicator connected={wsConnected} isConnecting={wsReconnecting} />
            <button
              type="button"
              onClick={() => void refetch()}
              className="p-2 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors"
              title="Refresh queue snapshot"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </header>

        <main className="flex-1 p-6 space-y-6 overflow-y-auto max-w-7xl w-full">
          {/* Action error banner */}
          {actionError && (
            <div className="p-4 rounded-2xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center justify-between">
              <span>{actionError}</span>
              <button
                onClick={() => setActionError(null)}
                className="text-xs font-bold text-red-600 hover:text-red-900"
              >
                ✕
              </button>
            </div>
          )}

          {/* TOP STATISTICS (PART P) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
            <StatsCard
              label="Booked (Pre-Arrival)"
              value={snapshot.total_booked ?? 0}
              icon={<Calendar className="w-6 h-6" />}
              bgClass="bg-amber-50"
              textClass="text-amber-600"
            />
            <StatsCard
              label="Waiting Patients"
              value={snapshot.total_waiting}
              icon={<Users className="w-6 h-6" />}
              bgClass="bg-blue-50"
              textClass="text-blue-600"
            />
            <StatsCard
              label="In Consultation"
              value={snapshot.total_in_consultation}
              icon={<Activity className="w-6 h-6" />}
              bgClass="bg-emerald-50"
              textClass="text-emerald-600"
            />
            <StatsCard
              label="Completed Visits"
              value={snapshot.total_completed}
              icon={<CheckCircle className="w-6 h-6" />}
              bgClass="bg-indigo-50"
              textClass="text-indigo-600"
            />
            <StatsCard
              label="No-Shows / Left"
              value={snapshot.total_no_show}
              icon={<UserX className="w-6 h-6" />}
              bgClass="bg-slate-100"
              textClass="text-slate-600"
            />
          </div>

          {/* CLINICAL TELEMETRY & REAL-TIME PERFORMANCE (Requirement 21) */}
          <div className="bg-slate-900 text-white rounded-2xl p-4 shadow-sm border border-slate-800">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
                  Authoritative Clinical Telemetry
                </span>
              </div>
              <span className="text-[10px] text-slate-400 font-medium">Computed strictly from real session timestamps</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 pt-3 text-xs">
              <div>
                <span className="text-[10px] text-slate-400 font-semibold uppercase block">Avg Consultation</span>
                <span className="text-sm font-bold text-white mt-0.5 block">
                  {snapshot.avg_consultation_duration_seconds != null
                    ? `${Math.round(snapshot.avg_consultation_duration_seconds / 60)} min`
                    : <span className="text-slate-500 font-normal text-xs">Insufficient live data</span>}
                </span>
              </div>

              <div>
                <span className="text-[10px] text-slate-400 font-semibold uppercase block">Avg Waiting Time</span>
                <span className="text-sm font-bold text-white mt-0.5 block">
                  {snapshot.avg_waiting_time_seconds != null
                    ? `${Math.round(snapshot.avg_waiting_time_seconds / 60)} min`
                    : <span className="text-slate-500 font-normal text-xs">Insufficient live data</span>}
                </span>
              </div>

              <div>
                <span className="text-[10px] text-slate-400 font-semibold uppercase block">Current Consult Elapsed</span>
                <span className="text-sm font-bold text-emerald-400 mt-0.5 block">
                  {snapshot.current_consultation_elapsed_seconds != null
                    ? `${Math.round(snapshot.current_consultation_elapsed_seconds / 60)} min elapsed`
                    : <span className="text-slate-500 font-normal text-xs">No active consult</span>}
                </span>
              </div>

              <div>
                <span className="text-[10px] text-slate-400 font-semibold uppercase block">Doctor Delay Impact</span>
                <span className="text-sm font-bold mt-0.5 block text-amber-400">
                  {snapshot.delay_impact_minutes && snapshot.delay_impact_minutes > 0
                    ? `+${snapshot.delay_impact_minutes} min recorded`
                    : <span className="text-slate-300 font-normal text-xs">0 min (On schedule)</span>}
                </span>
              </div>

              <div>
                <span className="text-[10px] text-slate-400 font-semibold uppercase block">Remaining Queue Workload</span>
                <span className="text-sm font-bold text-white mt-0.5 block">
                  {snapshot.estimated_remaining_queue_time_minutes != null
                    ? `~${snapshot.estimated_remaining_queue_time_minutes} min est.`
                    : <span className="text-slate-500 font-normal text-xs">Insufficient live data</span>}
                </span>
              </div>
            </div>
          </div>

          {/* CLINICAL DISRUPTION & CONTROL OPERATIONS BAR (PART Q) */}
          <div className="bg-white rounded-2xl p-5 border border-slate-200/90 shadow-2xs flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCallNext}
                disabled={snapshot.total_waiting === 0 || isPaused || snapshot.status === 'COMPLETED'}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-semibold text-sm shadow-xs transition-all disabled:opacity-50"
              >
                <Phone className="w-4 h-4" />
                <span>Call Next Patient</span>
              </button>

              <button
                type="button"
                onClick={() => setIsBookModalOpen(true)}
                disabled={snapshot.status === 'COMPLETED'}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-semibold text-sm shadow-xs transition-all cursor-pointer disabled:opacity-50"
                title="Admit phone or walk-in patient directly into this queue"
              >
                <UserPlus className="w-4 h-4 text-emerald-200" />
                <span>+ Add Patient</span>
              </button>

              {isPaused ? (
                <button
                  type="button"
                  onClick={handleResume}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm shadow-xs transition-all"
                >
                  <Play className="w-4 h-4" />
                  <span>Resume Queue</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handlePause}
                  disabled={snapshot.status === 'COMPLETED'}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-sm transition-colors border border-slate-200 disabled:opacity-50"
                >
                  <Pause className="w-4 h-4" />
                  <span>Pause Queue</span>
                </button>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {/* Emergency Insertion (PART P & Q) */}
              <button
                type="button"
                onClick={() => setShowEmergency(true)}
                disabled={snapshot.status === 'COMPLETED'}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 font-bold text-xs transition-colors disabled:opacity-50"
              >
                <Zap className="w-4 h-4 text-red-600" />
                <span>Emergency Insert</span>
              </button>

              <button
                type="button"
                onClick={() => setShowBreak(true)}
                disabled={snapshot.status === 'COMPLETED'}
                className="inline-flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 font-semibold text-xs transition-colors disabled:opacity-50"
              >
                <Coffee className="w-4 h-4 text-amber-600" />
                <span>Doctor Break</span>
              </button>

              <button
                type="button"
                onClick={() => setShowDelay(true)}
                disabled={snapshot.status === 'COMPLETED'}
                className="inline-flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 font-semibold text-xs transition-colors disabled:opacity-50"
              >
                <Clock className="w-4 h-4 text-slate-500" />
                <span>Doctor Delay</span>
              </button>

              <button
                type="button"
                onClick={handleReforecast}
                className="inline-flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 font-semibold text-xs transition-colors"
                title="Trigger dynamic recalculation of ETAs"
              >
                <Sparkles className="w-4 h-4 text-blue-600" />
                <span>Trigger Reforecast</span>
              </button>

              {snapshot.status !== 'COMPLETED' && (
                <button
                  type="button"
                  onClick={handleEndQueue}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-900 text-white font-semibold text-xs transition-colors cursor-pointer"
                  title="Officially end and close this queue session"
                >
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                  <span>End Queue</span>
                </button>
              )}
            </div>
          </div>

          {/* Queue Completion State Notification (Requirement 20) */}
          {snapshot.status === 'COMPLETED' ? (
            <div className="bg-slate-200/90 border border-slate-300 rounded-2xl p-4 flex items-center gap-3 text-slate-800">
              <CheckCircle className="w-5 h-5 text-emerald-700 shrink-0" />
              <span className="text-xs font-bold">This OPD queue has been officially completed and closed for the session.</span>
            </div>
          ) : snapshot.total_waiting === 0 && snapshot.total_in_consultation === 0 && (!snapshot.total_booked || snapshot.total_booked === 0) && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-4 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-xs animate-fade-up">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-6 h-6 text-emerald-600 shrink-0" />
                <div>
                  <h3 className="text-sm font-bold text-emerald-900">All scheduled patients completed</h3>
                  <p className="text-xs text-emerald-700">There are no waiting or pending patients remaining in this clinic session.</p>
                </div>
              </div>
              <button
                type="button"
                onClick={handleEndQueue}
                className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs rounded-xl shadow-xs transition-all cursor-pointer shrink-0"
              >
                End Queue
              </button>
            </div>
          )}

          {/* ACTIVE CALL & SERVING CARDS */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Currently Serving */}
            <div className="bg-white rounded-2xl p-5 border border-slate-200/90 shadow-2xs">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                In Consultation
              </span>
              {snapshot.currently_serving ? (
                <div className="mt-2 flex items-center justify-between">
                  <div>
                    <div className="text-3xl font-black text-slate-900">
                      {snapshot.currently_serving.token_display}
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                      Priority: {snapshot.currently_serving.priority_class}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleCompleteConsultation(snapshot.currently_serving!.id)}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs transition-colors shadow-xs"
                  >
                    <CheckCircle className="w-4 h-4" />
                    <span>Complete Visit</span>
                  </button>
                </div>
              ) : (
                <p className="text-sm text-slate-400 italic mt-3">
                  No patient currently inside consultation room.
                </p>
              )}
            </div>

            {/* Currently Called */}
            <div className="bg-white rounded-2xl p-5 border border-slate-200/90 shadow-2xs">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Called & Awaiting Entry
              </span>
              {snapshot.currently_called ? (
                <div className="mt-2 flex items-center justify-between">
                  <div>
                    <div className="text-3xl font-black text-amber-600">
                      {snapshot.currently_called.token_display}
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                      Called {formatRelative(snapshot.currently_called.called_at || '')}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleStartConsultation(snapshot.currently_called!.id)}
                      className="px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-xs"
                    >
                      Start
                    </button>
                    <button
                      type="button"
                      onClick={() => handleNoShow(snapshot.currently_called!.id)}
                      className="px-3 py-2 rounded-xl bg-slate-100 hover:bg-red-50 hover:text-red-700 text-slate-600 font-semibold text-xs border border-slate-200"
                    >
                      No-Show
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-400 italic mt-3">
                  No patient currently called.
                </p>
              )}
            </div>
          </div>

          {/* BOOKED PATIENTS AWAITING ARRIVAL */}
          {snapshot.booked_entries && snapshot.booked_entries.length > 0 && (
            <div className="bg-white rounded-2xl border border-amber-200/80 shadow-2xs overflow-hidden">
              <div className="p-5 bg-amber-50/40 border-b border-amber-100 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
                    <h3 className="text-base font-bold text-slate-900">Booked Patients (Awaiting Physical Arrival)</h3>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {snapshot.booked_entries.length} patient(s) booked online/phone. Click "Mark Arrived" when they physically reach the clinic.
                  </p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-100">
                    <tr>
                      <th className="px-5 py-3.5">Token</th>
                      <th className="px-5 py-3.5">Patient Name</th>
                      <th className="px-5 py-3.5">Appt Time</th>
                      <th className="px-5 py-3.5">Source</th>
                      <th className="px-5 py-3.5">Priority</th>
                      <th className="px-5 py-3.5">Status</th>
                      <th className="px-5 py-3.5">Booked At</th>
                      <th className="px-5 py-3.5 text-right">Arrival Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700 font-medium">
                    {snapshot.booked_entries.map((entry: QueueEntryResponse) => (
                      <tr key={entry.id} className="hover:bg-amber-50/30 transition-colors">
                        <td className="px-5 py-4 font-black text-sm text-slate-900">
                          {entry.token_display}
                        </td>
                        <td className="px-5 py-4 font-bold text-slate-900">
                          {entry.patient_name || 'Patient'}
                        </td>
                        <td className="px-5 py-4 font-mono font-bold text-blue-700">
                          {entry.appointment_time ? entry.appointment_time.slice(0, 5) : '—'}
                        </td>
                        <td className="px-5 py-4">
                          <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-slate-100 text-slate-700">
                            {entry.booking_source || 'ONLINE'}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <span
                            className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
                              entry.priority_class === 'EMERGENCY'
                                ? 'bg-red-100 text-red-800'
                                : entry.priority_class === 'PRIORITY'
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-slate-100 text-slate-600'
                            }`}
                          >
                            {entry.priority_class}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-amber-100 text-amber-800">
                            BOOKED
                          </span>
                        </td>
                        <td className="px-5 py-4 text-slate-400">
                          {formatRelative(entry.joined_at)}
                        </td>
                        <td className="px-5 py-4 text-right">
                          <button
                            type="button"
                            onClick={() => handleArrive(entry.id)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-2xs transition-all cursor-pointer"
                          >
                            <UserCheck className="w-3.5 h-3.5" />
                            <span>Mark Arrived</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* QUEUE TABLE / LIST (PART P) */}
          <div className="bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900">Waiting Queue</h3>
                <p className="text-xs text-slate-500">
                  {snapshot.waiting_entries.length} patients in ordered line
                </p>
              </div>
            </div>

            {snapshot.waiting_entries.length === 0 ? (
              <div className="p-12 text-center text-slate-400 text-sm">
                No patients waiting in queue.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-100">
                    <tr>
                      <th className="px-5 py-3.5">Pos</th>
                      <th className="px-5 py-3.5">Token</th>
                      <th className="px-5 py-3.5">Patient Name</th>
                      <th className="px-5 py-3.5">Appt Time</th>
                      <th className="px-5 py-3.5">Source</th>
                      <th className="px-5 py-3.5">Priority</th>
                      <th className="px-5 py-3.5">Status</th>
                      <th className="px-5 py-3.5">Joined / Arrived</th>
                      <th className="px-5 py-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700 font-medium">
                    {snapshot.waiting_entries.map((entry: QueueEntryResponse) => (
                      <tr key={entry.id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="px-5 py-4 font-bold text-slate-900">
                          #{entry.position ?? '—'}
                        </td>
                        <td className="px-5 py-4 font-black text-sm text-slate-900">
                          {entry.token_display}
                        </td>
                        <td className="px-5 py-4 font-bold text-slate-900">
                          {entry.patient_name || 'Patient'}
                        </td>
                        <td className="px-5 py-4 font-mono font-bold text-blue-700">
                          {entry.appointment_time ? entry.appointment_time.slice(0, 5) : '—'}
                        </td>
                        <td className="px-5 py-4">
                          <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-slate-100 text-slate-700">
                            {entry.booking_source || 'ONLINE'}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <span
                            className={`px-2 py-0.5 rounded-md text-[11px] font-semibold ${
                              entry.status === 'TEMPORARILY_LEFT'
                                ? 'bg-amber-50 text-amber-700'
                                : entry.status === 'ARRIVED'
                                ? 'bg-emerald-50 text-emerald-700 font-bold'
                                : entry.status === 'BOOKED'
                                ? 'bg-amber-50 text-amber-700'
                                : 'bg-blue-50 text-blue-700'
                            }`}
                          >
                            {entry.status}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-slate-400">
                          {entry.arrived_at
                            ? `Arrived ${formatRelative(entry.arrived_at)}`
                            : formatRelative(entry.joined_at)}
                        </td>
                        <td className="px-5 py-4 text-right space-x-1.5">
                          {entry.status === 'BOOKED' && (
                            <button
                              type="button"
                              onClick={() => handleArrive(entry.id)}
                              className="px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs"
                            >
                              Arrive
                            </button>
                          )}

                          {entry.status === 'ARRIVED' && (
                            <button
                              type="button"
                              onClick={() => handleWait(entry.id)}
                              className="px-2.5 py-1.5 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 font-semibold border border-blue-200"
                            >
                              Wait
                            </button>
                          )}

                          {entry.status === 'TEMPORARILY_LEFT' ? (
                            <button
                              type="button"
                              onClick={() => handleReturn(entry.id)}
                              className="px-2.5 py-1.5 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-semibold border border-emerald-200"
                            >
                              Return
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setSelectedEntryForLeave(entry)}
                              className="px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium"
                            >
                              Leave
                            </button>
                          )}

                          <button
                            type="button"
                            onClick={() => setSelectedEntryForPriority(entry)}
                            className="px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium"
                          >
                            Priority
                          </button>

                          <button
                            type="button"
                            onClick={() => handleCall(entry.id)}
                            className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow-2xs"
                          >
                            Call
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

          </div>
        </main>
      </div>

      {/* DISRUPTION MODALS (PART Q) */}
      {showEmergency && (
        <EmergencyModal
          queueId={activeQueueId!}
          waitingEntries={snapshot?.waiting_entries}
          onClose={() => setShowEmergency(false)}
          onSuccess={() => {
            setShowEmergency(false);
            void queryClient.invalidateQueries({ queryKey: ['snapshot', queueId] });
            if (activeQueueId && activeQueueId !== queueId) {
              void queryClient.invalidateQueries({ queryKey: ['snapshot', activeQueueId] });
            }
          }}
        />
      )}

      {showBreak && (
        <DoctorBreakModal
          queueId={activeQueueId!}
          onClose={() => setShowBreak(false)}
          onSuccess={() => {
            setShowBreak(false);
            void queryClient.invalidateQueries({ queryKey: ['snapshot', queueId] });
            if (activeQueueId && activeQueueId !== queueId) {
              void queryClient.invalidateQueries({ queryKey: ['snapshot', activeQueueId] });
            }
          }}
        />
      )}

      {showDelay && (
        <DoctorDelayModal
          queueId={activeQueueId!}
          onClose={() => setShowDelay(false)}
          onSuccess={() => {
            setShowDelay(false);
            void queryClient.invalidateQueries({ queryKey: ['snapshot', queueId] });
            if (activeQueueId && activeQueueId !== queueId) {
              void queryClient.invalidateQueries({ queryKey: ['snapshot', activeQueueId] });
            }
          }}
        />
      )}

      {selectedEntryForLeave && (
        <TemporaryLeaveModal
          entryId={selectedEntryForLeave.id}
          tokenDisplay={selectedEntryForLeave.token_display}
          onClose={() => setSelectedEntryForLeave(null)}
          onSuccess={() => {
            setSelectedEntryForLeave(null);
            void queryClient.invalidateQueries({ queryKey: ['snapshot', queueId] });
          }}
        />
      )}

      {selectedEntryForPriority && (
        <PriorityChangeModal
          entryId={selectedEntryForPriority.id}
          tokenDisplay={selectedEntryForPriority.token_display}
          currentPriority={selectedEntryForPriority.priority_class}
          onClose={() => setSelectedEntryForPriority(null)}
          onSuccess={() => {
            setSelectedEntryForPriority(null);
            void queryClient.invalidateQueries({ queryKey: ['snapshot', queueId] });
          }}
        />
      )}

      {isBookModalOpen && (
        <StaffBookModal
          isOpen={isBookModalOpen}
          onClose={() => setIsBookModalOpen(false)}
          queues={
            sessionQueues.length > 0
              ? sessionQueues.map((q: any) => ({
                  queue_id: q.id,
                  queue_name: q.name || 'OPD Queue',
                  doctor_name: formatDoctorName(q.doctor_name, 'Doctor'),
                  total_waiting: q.total_waiting ?? 0,
                }))
              : snapshot
              ? [
                  {
                    queue_id: activeQueueId!,
                    queue_name: snapshot.queue_name || 'Current Queue',
                    doctor_name: formatDoctorName(snapshot.doctor_name, 'Doctor'),
                    total_waiting: snapshot.total_waiting,
                  },
                ]
              : []
          }
          defaultQueueId={activeQueueId}
          defaultDate={effectiveDate}
          onSuccess={() => {
            setIsBookModalOpen(false);
            void queryClient.invalidateQueries({ queryKey: ['snapshot', queueId] });
            if (activeQueueId && activeQueueId !== queueId) {
              void queryClient.invalidateQueries({ queryKey: ['snapshot', activeQueueId] });
            }
          }}
        />
      )}
    </div>
  );
}
