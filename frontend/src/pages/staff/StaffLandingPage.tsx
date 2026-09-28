import { useState, useMemo } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../store/AuthContext';
import { useQuery } from '@tanstack/react-query';
import { discoveryApi } from '../../api/discovery';
import { queuesApi } from '../../api/queues';
import { queueEntriesApi } from '../../api/queueEntries';
import { extractErrorMessage } from '../../api/client';
import { BrandLogo } from '../../components/BrandLogo';
import { StaffBookModal } from './StaffBookModal';
import { DoctorAvailabilityModal } from './DoctorAvailabilityModal';
import { StaffDoctorScheduleManager } from './StaffDoctorScheduleManager';
import { StaffCreateQueueModal } from './StaffCreateQueueModal';
import { StaffDoctorScheduleModal } from './StaffDoctorScheduleModal';
import { StaffDatePicker } from '../../components/StaffDatePicker';
import {
  getHospitalTodayDateString,
  addDaysToCanonicalDate,
  formatCanonicalDateDisplay,
} from '../../utils/dateUtils';
import { formatDoctorName } from '../../utils/format';
import { useWebSocket } from '../../hooks/useWebSocket';
import {
  LogOut,
  ArrowRight,
  LayoutDashboard,
  Building2,
  Users,
  Layers,
  ChevronRight,
  Search,
  UserPlus,
  Stethoscope,
  Clock,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Flame,
  Activity,
  Calendar,
  Plus,
  Phone,
} from 'lucide-react';

export default function StaffLandingPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [queueId, setQueueId] = useState('');
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'dashboard' | 'queues' | 'schedules'>('dashboard');
  const [isBookModalOpen, setIsBookModalOpen] = useState(false);
  const [targetQueueForBooking, setTargetQueueForBooking] = useState<string>('');
  const [availabilityDoctor, setAvailabilityDoctor] = useState<{ id: string; name: string } | null>(null);
  const [isCreateQueueOpen, setIsCreateQueueOpen] = useState(false);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  
  // Date selection state for Staff Queue view (defaults to today)
  const [queueDate, setQueueDate] = useState(() => getHospitalTodayDateString());

  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Quick date shortcuts
  const todayStr = useMemo(() => getHospitalTodayDateString(), []);
  const tomorrowStr = useMemo(() => addDaysToCanonicalDate(todayStr, 1), [todayStr]);
  const day3Str = useMemo(() => addDaysToCanonicalDate(todayStr, 2), [todayStr]);
  const day4Str = useMemo(() => addDaysToCanonicalDate(todayStr, 3), [todayStr]);

  // Fetch staff member's assigned hospital, departments, and active queues
  const {
    data: staffHospitalData,
    isLoading: queuesLoading,
    refetch: refetchHospitalData,
  } = useQuery({
    queryKey: ['staff-hospital-data', user?.hospital_id],
    queryFn: () => discoveryApi.getStaffHospital(),
    staleTime: 5_000,
    refetchInterval: 5_000,
  });

  const hospital = staffHospitalData?.hospital;
  const queues = staffHospitalData?.queues || [];
  const backendMetrics = staffHospitalData?.metrics;

  // Real-time WebSocket connection for staff operations center
  const token = localStorage.getItem('qflow_token');
  useWebSocket({
    path: hospital?.id ? `/ws/hospital/${hospital.id}` : '',
    token,
    enabled: Boolean(hospital?.id && token),
    onMessage: () => {
      refetchHospitalData();
      refetchDateQueues();
    },
  });

  // Query: Fetch queues and named patients for the selected queueDate
  const {
    data: dateQueuesData,
    isLoading: isDateQueuesLoading,
    refetch: refetchDateQueues,
  } = useQuery({
    queryKey: ['staff-queues-for-date', queueDate, user?.hospital_id],
    queryFn: () => queuesApi.getQueuesForDate(queueDate),
    enabled: Boolean(user?.hospital_id),
    staleTime: 3_000,
    refetchInterval: 5_000,
  });

  const dateViewQueues = dateQueuesData?.queues || [];

  // Map queues for StaffBookModal options
  const modalQueueOptions = useMemo(() => {
    const map = new Map<string, { queue_id: string; queue_name: string; doctor_name: string; total_waiting: number }>();
    for (const q of dateViewQueues) {
      map.set(q.queue_id, {
        queue_id: q.queue_id,
        queue_name: q.queue_name || `${formatDoctorName(q.doctor_name, 'Doctor')} Queue`,
        doctor_name: formatDoctorName(q.doctor_name, 'Doctor'),
        total_waiting: q.entries?.length || 0,
      });
    }
    for (const q of queues) {
      if (!map.has(q.queue_id)) {
        map.set(q.queue_id, {
          queue_id: q.queue_id,
          queue_name: q.queue_name,
          doctor_name: formatDoctorName(q.doctor_name, 'Doctor'),
          total_waiting: q.total_waiting,
        });
      }
    }
    return Array.from(map.values());
  }, [dateViewQueues, queues]);

  const handleOpenBookForQueue = (qId: string) => {
    setTargetQueueForBooking(qId);
    setIsBookModalOpen(true);
  };

  const handleEntryAction = async (actionFn: () => Promise<any>, entryId: string) => {
    try {
      setActionLoadingId(entryId);
      setActionError(null);
      await actionFn();
      await Promise.all([refetchDateQueues(), refetchHospitalData()]);
    } catch (err: any) {
      setActionError(extractErrorMessage(err));
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleGo = () => {
    const trimmed = queueId.trim();
    if (!trimmed) {
      setError('Please enter a valid Queue ID.');
      return;
    }
    navigate(`/staff/queue/${trimmed}`);
  };

  const formatDateDisplay = (dateString: string) => {
    return formatCanonicalDateDisplay(dateString, 'long');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Staff Walk-in / Phone Booking Modal */}
      <StaffBookModal
        isOpen={isBookModalOpen}
        onClose={() => {
          setIsBookModalOpen(false);
          setTargetQueueForBooking('');
        }}
        queues={modalQueueOptions}
        defaultQueueId={targetQueueForBooking || (dateViewQueues[0]?.queue_id || queues[0]?.queue_id)}
        defaultDate={queueDate}
        onSuccess={() => {
          refetchDateQueues();
          refetchHospitalData();
        }}
      />

      {/* Doctor Availability Management Modal */}
      <DoctorAvailabilityModal
        isOpen={Boolean(availabilityDoctor)}
        onClose={() => setAvailabilityDoctor(null)}
        doctorId={availabilityDoctor?.id || ''}
        doctorName={availabilityDoctor?.name || ''}
      />

      {/* Create Queue Modal (Hospital auto-determined from staff account) */}
      <StaffCreateQueueModal
        isOpen={isCreateQueueOpen}
        onClose={() => setIsCreateQueueOpen(false)}
        hospitalName={hospital?.name}
        doctors={staffHospitalData?.doctors || []}
        defaultDate={queueDate}
        onCreated={() => {
          refetchHospitalData();
          refetchDateQueues();
        }}
      />

      {/* Schedule Doctor OPD Modal */}
      <StaffDoctorScheduleModal
        isOpen={isScheduleModalOpen}
        onClose={() => setIsScheduleModalOpen(false)}
        hospitalName={hospital?.name}
        doctors={staffHospitalData?.doctors || []}
        defaultDate={queueDate}
        onSaved={() => {
          refetchHospitalData();
          refetchDateQueues();
        }}
      />

      {/* Top Operations Header */}
      <header className="bg-slate-900 border-b border-slate-800 text-white sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BrandLogo size="sm" showTagline={false} theme="dark" linkTo="/staff" />
            <span className="text-[10px] font-bold uppercase tracking-wider bg-blue-900/80 text-blue-300 border border-blue-700/60 px-2 py-0.5 rounded-md hidden sm:inline-block">
              Hospital Operations
            </span>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <button
              type="button"
              onClick={() => setIsScheduleModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs shadow-sm transition-all cursor-pointer"
              title="Schedule Doctor OPD Shift"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>+ SCHEDULE DOCTOR OPD</span>
            </button>

            <Link
              to="/staff/historical"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-medium transition-all shadow-sm"
            >
              <svg className="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <span>Reports</span>
            </Link>

            <div className="flex items-center gap-2 bg-slate-800/80 border border-slate-700/60 rounded-xl px-3 py-1.5">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <div className="flex flex-col text-left">
                <span className="font-bold text-white text-[11px] leading-tight">
                  {user?.name || 'Staff User'}
                </span>
                <span className="text-[10px] text-slate-400 capitalize">
                  {hospital?.name ? `${hospital.name.slice(0, 22)}...` : 'Assigned Staff'}
                </span>
              </div>
            </div>

            <button
              onClick={() => logout()}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-slate-800 transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 w-full flex-1">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          
          {/* Navigation Sidebar */}
          <aside className="lg:col-span-3 space-y-4">
            <div className="bg-white rounded-2xl border border-slate-200/90 p-2 shadow-2xs space-y-1">
              <button
                type="button"
                onClick={() => setActiveTab('dashboard')}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'dashboard'
                    ? 'bg-slate-900 text-white shadow-2xs font-bold'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <LayoutDashboard className="w-4 h-4 text-blue-400" />
                  <span>Operations Overview</span>
                </div>
                <ChevronRight className="w-3.5 h-3.5 opacity-50" />
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('queues')}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'queues'
                    ? 'bg-slate-900 text-white shadow-2xs font-bold'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Layers className="w-4 h-4 text-emerald-400" />
                  <span>OPD Queues & Triage</span>
                </div>
                <span className="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full font-bold">
                  {dateViewQueues.length}
                </span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('schedules')}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'schedules'
                    ? 'bg-slate-900 text-white shadow-2xs font-bold'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Calendar className="w-4 h-4 text-cyan-400" />
                  <span className="font-bold">DOCTOR OPD SCHEDULE</span>
                </div>
                <span className="text-[10px] bg-cyan-100 text-cyan-800 px-2 py-0.5 rounded-full font-bold">
                  {staffHospitalData?.doctors?.length ?? 0}
                </span>
              </button>
            </div>

            {/* Direct UUID Lookup Card */}
            <div className="bg-white rounded-2xl border border-slate-200/90 p-4 shadow-2xs space-y-2.5">
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 block">
                Direct Queue Lookup
              </span>
              <input
                type="text"
                value={queueId}
                onChange={(e) => {
                  setQueueId(e.target.value);
                  setError('');
                }}
                onKeyDown={(e) => e.key === 'Enter' && handleGo()}
                placeholder="Paste Queue ID..."
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs font-mono text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
              />
              {error && <p className="text-[11px] text-red-600 font-medium">{error}</p>}
              <button
                type="button"
                onClick={handleGo}
                className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs transition-all cursor-pointer shadow-2xs"
              >
                <Search className="w-3.5 h-3.5" />
                <span>Open Queue</span>
              </button>
            </div>
          </aside>

          {/* Main Content Area */}
          <main className="lg:col-span-9 space-y-6">

            {/* TAB 1: Doctor Schedules */}
            {activeTab === 'schedules' && (
              <StaffDoctorScheduleManager
                hospitalData={staffHospitalData}
                onOpenScheduleModal={() => setIsScheduleModalOpen(true)}
                onScheduleUpdated={() => {
                  refetchHospitalData();
                  refetchDateQueues();
                }}
              />
            )}

            {/* TAB 2: STAFF QUEUE SECTION (Requirements 1, 8, 9, 10, 13) */}
            {activeTab === 'queues' && (
              <div className="space-y-6">
                
                {/* Queue Management Toolbar & Date Selector */}
                <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-2xs flex flex-col gap-4">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-extrabold uppercase tracking-wider bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded">
                          {hospital?.name || 'Hospital'} OPD Queues
                        </span>
                        <span className="text-xs text-slate-500 font-medium">
                          Active Planning & Roster
                        </span>
                      </div>
                      <h1 className="text-xl font-black text-slate-900 mt-1">
                        OPD Session Queues & Scheduling
                      </h1>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Manage doctor queues by date, view real-time patient rosters, and admit phone or walk-in arrivals.
                      </p>
                    </div>

                    {/* Queue Actions */}
                    <div className="flex flex-wrap items-center gap-2.5">
                      <button
                        type="button"
                        onClick={() => setIsScheduleModalOpen(true)}
                        className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs shadow-md transition-all cursor-pointer shrink-0"
                      >
                        <Plus className="w-4 h-4" />
                        <span>+ SCHEDULE DOCTOR OPD</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setIsCreateQueueOpen(true)}
                        className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-md transition-all cursor-pointer shrink-0"
                      >
                        <Plus className="w-4 h-4" />
                        <span>+ CREATE QUEUE</span>
                      </button>
                    </div>
                  </div>

                  {/* Obvious Date Selector (Requirement 8) */}
                  <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <StaffDatePicker
                        selectedDate={queueDate}
                        onSelectDate={(newDate) => setQueueDate(newDate)}
                        labelPrefix="Queue Date:"
                      />
                    </div>

                    {/* Quick Date Pills */}
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => setQueueDate(todayStr)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                          queueDate === todayStr
                            ? 'bg-slate-900 text-white shadow-2xs'
                            : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                        }`}
                      >
                        Today
                      </button>
                      <button
                        type="button"
                        onClick={() => setQueueDate(tomorrowStr)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                          queueDate === tomorrowStr
                            ? 'bg-slate-900 text-white shadow-2xs'
                            : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                        }`}
                      >
                        Tomorrow
                      </button>
                      <button
                        type="button"
                        onClick={() => setQueueDate(day3Str)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                          queueDate === day3Str
                            ? 'bg-slate-900 text-white shadow-2xs'
                            : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                        }`}
                      >
                        +2 Days
                      </button>
                      <button
                        type="button"
                        onClick={() => setQueueDate(day4Str)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                          queueDate === day4Str
                            ? 'bg-slate-900 text-white shadow-2xs'
                            : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                        }`}
                      >
                        +3 Days
                      </button>
                    </div>
                  </div>
                </div>

                {/* Action Feedback Banner */}
                {actionError && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-2xl text-rose-700 text-xs flex items-center justify-between">
                    <span>{actionError}</span>
                    <button onClick={() => setActionError(null)} className="text-rose-500 font-bold hover:underline">
                      Dismiss
                    </button>
                  </div>
                )}

                {/* Date Queues List */}
                {isDateQueuesLoading ? (
                  <div className="bg-white rounded-3xl p-12 border border-slate-200/90 shadow-2xs text-center">
                    <div className="w-8 h-8 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                    <p className="text-xs text-slate-500 font-semibold">
                      Loading doctor queues for {formatDateDisplay(queueDate)}...
                    </p>
                  </div>
                ) : dateViewQueues.length === 0 ? (
                  <div className="bg-white rounded-3xl p-12 border border-slate-200/90 shadow-2xs text-center space-y-4">
                    <div className="w-14 h-14 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto">
                      <Calendar className="w-7 h-7" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-slate-900">
                        No Queues Scheduled for {formatDateDisplay(queueDate)}
                      </h3>
                      <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
                        There are currently no doctor OPD queues scheduled for this date. Click "+ CREATE QUEUE" to establish an OPD session for one of your hospital's doctors.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setIsCreateQueueOpen(true)}
                      className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-md transition-all cursor-pointer"
                    >
                      <Plus className="w-4 h-4" />
                      <span>+ Create Queue for {formatDateDisplay(queueDate)}</span>
                    </button>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {dateViewQueues.map((q: any) => {
                      const entries = q.entries || [];
                      return (
                        <div
                          key={q.queue_id}
                          className="bg-white rounded-3xl border border-slate-200/90 shadow-2xs overflow-hidden transition-all"
                        >
                          {/* Queue Card Header */}
                          <div className="p-6 border-b border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-50/50">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-[10px] font-extrabold uppercase tracking-wider bg-blue-100 text-blue-800 px-2 py-0.5 rounded-md">
                                  {q.department_name}
                                </span>
                                <span className="text-[10px] font-bold text-slate-500 flex items-center gap-1">
                                  <Clock className="w-3 h-3 text-emerald-600" />
                                  <span>{q.start_time} – {q.end_time}</span>
                                </span>
                                <span className="text-[10px] font-bold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
                                  {q.status}
                                </span>
                              </div>
                              <h2 className="text-lg font-black text-slate-900 mt-1">
                                {formatDoctorName(q.doctor_name)}
                              </h2>
                              <p className="text-xs text-slate-500">
                                {q.queue_name || `${formatDoctorName(q.doctor_name)} Clinic Queue`} • Date: {formatDateDisplay(q.queue_date)}
                              </p>
                            </div>

                            {/* Queue Card Actions */}
                            <div className="flex items-center gap-2.5 shrink-0">
                              <span className="text-xs font-bold text-slate-700 bg-white border border-slate-200 px-3 py-1.5 rounded-xl shadow-2xs">
                                Patients: <span className="text-emerald-600 font-extrabold">{entries.length}</span>
                              </span>

                              {/* + ADD WALK-IN / PHONE PATIENT BUTTON */}
                              <button
                                type="button"
                                onClick={() => handleOpenBookForQueue(q.queue_id)}
                                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-2xs transition-all cursor-pointer"
                                title="Add a walk-in, phone, or staff appointment into this exact queue"
                              >
                                <UserPlus className="w-3.5 h-3.5" />
                                <span>+ ADD WALK-IN / PHONE PATIENT</span>
                              </button>

                              {/* OPEN QUEUE CONTROL BUTTON */}
                              <button
                                type="button"
                                onClick={() => navigate(`/staff/queue/${q.queue_id}${q.queue_date ? `?date=${q.queue_date}` : ''}`)}
                                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs shadow-2xs transition-all cursor-pointer"
                              >
                                <span>Queue Control</span>
                                <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                              </button>
                            </div>
                          </div>

                          {/* PATIENT LIST TABLE (Requirements 9, 11, 12, 13) */}
                          <div className="p-6">
                            <div className="flex items-center justify-between mb-3">
                              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                                Patient Queue Roster ({entries.length} Registered)
                              </h3>
                              <span className="text-[11px] text-slate-400">
                                Unified queue for Online, Phone, and Walk-in bookings
                              </span>
                            </div>

                            {entries.length === 0 ? (
                              <div className="p-8 rounded-2xl bg-slate-50 text-center border border-dashed border-slate-200 text-xs text-slate-400 space-y-2">
                                <p>No patients currently registered in this queue for {formatDateDisplay(q.queue_date)}.</p>
                                <button
                                  type="button"
                                  onClick={() => handleOpenBookForQueue(q.queue_id)}
                                  className="font-bold text-emerald-700 hover:underline inline-flex items-center gap-1"
                                >
                                  <UserPlus className="w-3.5 h-3.5" />
                                  <span>+ Add first patient to this queue</span>
                                </button>
                              </div>
                            ) : (
                              <div className="overflow-x-auto rounded-2xl border border-slate-200/80">
                                <table className="w-full text-left text-xs border-collapse">
                                  <thead>
                                    <tr className="bg-slate-100/80 text-slate-700 uppercase font-black tracking-wider text-[10px] border-b border-slate-200">
                                      <th className="py-2.5 px-3.5">Token</th>
                                      <th className="py-2.5 px-3.5">Patient Name</th>
                                      <th className="py-2.5 px-3.5">Time</th>
                                      <th className="py-2.5 px-3.5">Source</th>
                                      <th className="py-2.5 px-3.5">Status</th>
                                      <th className="py-2.5 px-3.5 text-right">Queue Actions</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-slate-100">
                                    {entries.map((entry: any) => (
                                      <tr key={entry.id} className="hover:bg-slate-50/80 transition-colors">
                                        <td className="py-2.5 px-3.5">
                                          <span className="font-mono font-black text-slate-900 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-md">
                                            {entry.token_display || `Q${String(entry.token_number).padStart(3, '0')}`}
                                          </span>
                                        </td>
                                        <td className="py-2.5 px-3.5">
                                          <div className="font-bold text-slate-900">{entry.patient_name}</div>
                                          {entry.patient_phone && (
                                            <div className="text-[10px] text-slate-400 font-mono flex items-center gap-1 mt-0.5">
                                              <Phone className="w-2.5 h-2.5" />
                                              <span>{entry.patient_phone}</span>
                                            </div>
                                          )}
                                        </td>
                                        <td className="py-2.5 px-3.5 font-medium text-slate-600">
                                          {entry.appointment_time || '—'}
                                        </td>
                                        <td className="py-2.5 px-3.5">
                                          {entry.booking_source === 'ONLINE' ? (
                                            <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-blue-50 text-blue-700 border border-blue-200">
                                              ONLINE
                                            </span>
                                          ) : entry.booking_source === 'PHONE' ? (
                                            <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-purple-50 text-purple-700 border border-purple-200">
                                              PHONE
                                            </span>
                                          ) : entry.booking_source === 'WALK_IN' ? (
                                            <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-amber-50 text-amber-700 border border-amber-200">
                                              WALK-IN
                                            </span>
                                          ) : (
                                            <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-slate-50 text-slate-700 border border-slate-200">
                                              {entry.booking_source || 'STAFF'}
                                            </span>
                                          )}
                                        </td>
                                        <td className="py-2.5 px-3.5">
                                          {entry.status === 'BOOKED' && (
                                            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-blue-100 text-blue-800">
                                              BOOKED
                                            </span>
                                          )}
                                          {entry.status === 'ARRIVED' && (
                                            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-teal-100 text-teal-800">
                                              ARRIVED
                                            </span>
                                          )}
                                          {entry.status === 'WAITING' && (
                                            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800">
                                              WAITING
                                            </span>
                                          )}
                                          {entry.status === 'CALLED' && (
                                            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-orange-100 text-orange-800 animate-pulse">
                                              CALLED
                                            </span>
                                          )}
                                          {entry.status === 'IN_CONSULTATION' && (
                                            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800">
                                              IN CONSULTATION
                                            </span>
                                          )}
                                          {entry.status === 'COMPLETED' && (
                                            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-200 text-slate-700">
                                              COMPLETED
                                            </span>
                                          )}
                                          {entry.status === 'NO_SHOW' && (
                                            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-100 text-rose-800">
                                              NO SHOW
                                            </span>
                                          )}
                                        </td>

                                        {/* State Machine Transition Actions (Requirement 13) */}
                                        <td className="py-2.5 px-3.5 text-right">
                                          <div className="flex items-center justify-end gap-1.5 flex-wrap">
                                            {entry.status === 'BOOKED' && (
                                              <button
                                                type="button"
                                                disabled={actionLoadingId === entry.id}
                                                onClick={() => handleEntryAction(() => queueEntriesApi.arrive(entry.id), entry.id)}
                                                className="px-2.5 py-1 rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-bold text-[11px] shadow-2xs transition-all cursor-pointer"
                                                title="Patient has arrived at hospital waiting room"
                                              >
                                                {actionLoadingId === entry.id ? 'Saving...' : 'Mark Arrived'}
                                              </button>
                                            )}

                                            {(entry.status === 'WAITING' || entry.status === 'ARRIVED') && (
                                              <button
                                                type="button"
                                                disabled={actionLoadingId === entry.id}
                                                onClick={() => handleEntryAction(() => queueEntriesApi.call(entry.id), entry.id)}
                                                className="px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold text-[11px] shadow-2xs transition-all cursor-pointer"
                                                title="Call patient into consultation"
                                              >
                                                {actionLoadingId === entry.id ? 'Calling...' : 'Call Next'}
                                              </button>
                                            )}

                                            {entry.status === 'CALLED' && (
                                              <button
                                                type="button"
                                                disabled={actionLoadingId === entry.id}
                                                onClick={() => handleEntryAction(() => queueEntriesApi.startConsultation(entry.id), entry.id)}
                                                className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-[11px] shadow-2xs transition-all cursor-pointer"
                                                title="Start doctor consultation"
                                              >
                                                {actionLoadingId === entry.id ? 'Starting...' : 'Start Consult'}
                                              </button>
                                            )}

                                            {entry.status === 'IN_CONSULTATION' && (
                                              <button
                                                type="button"
                                                disabled={actionLoadingId === entry.id}
                                                onClick={() => handleEntryAction(() => queueEntriesApi.completeConsultation(entry.id), entry.id)}
                                                className="px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-bold text-[11px] shadow-2xs transition-all cursor-pointer"
                                                title="Finish doctor consultation"
                                              >
                                                {actionLoadingId === entry.id ? 'Ending...' : 'End Consult'}
                                              </button>
                                            )}

                                            {['BOOKED', 'WAITING', 'ARRIVED', 'CALLED'].includes(entry.status) && (
                                              <button
                                                type="button"
                                                disabled={actionLoadingId === entry.id}
                                                onClick={() => handleEntryAction(() => queueEntriesApi.noShow(entry.id), entry.id)}
                                                className="px-2 py-1 rounded-lg border border-rose-200 hover:bg-rose-50 text-rose-600 font-semibold text-[11px] transition-all cursor-pointer"
                                                title="Mark as No-Show"
                                              >
                                                No-Show
                                              </button>
                                            )}
                                          </div>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: Dashboard / Overview */}
            {activeTab === 'dashboard' && (
              <>
                {/* Facility Welcome Banner */}
                <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-2xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-3.5">
                    <div className="w-12 h-12 rounded-2xl bg-blue-50 border border-blue-200 text-blue-600 flex items-center justify-center shrink-0">
                      <Building2 className="w-6 h-6" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h1 className="text-lg font-bold text-slate-900">
                          {hospital?.name || 'Assigned Healthcare Facility'}
                        </h1>
                        <span className="text-[10px] font-extrabold uppercase tracking-wider bg-slate-900 text-white px-2 py-0.5 rounded">
                          Operations Center
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {hospital?.address || 'Central Outpatient Department & Clinical Triage'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => setActiveTab('queues')}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-emerald-300 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-xs font-bold transition-all cursor-pointer shadow-2xs"
                    >
                      <Layers className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Manage OPD Queues</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setActiveTab('schedules')}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-cyan-300 bg-cyan-50 hover:bg-cyan-100 text-cyan-800 text-xs font-bold transition-all cursor-pointer shadow-2xs"
                    >
                      <Calendar className="w-3.5 h-3.5 text-cyan-600" />
                      <span>Doctor Scheduling</span>
                    </button>
                  </div>
                </div>

                {/* Real Operational Metrics for Today */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                      Today's Operational Summary
                    </span>
                    <span className="text-[11px] text-slate-400">Live data from hospital database</span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[10px] font-bold uppercase tracking-wider">Appointments</span>
                        <Activity className="w-4 h-4 text-blue-500" />
                      </div>
                      <p className="text-2xl font-black text-slate-900 mt-1 tracking-tight">
                        {backendMetrics?.today_appointments ?? 0}
                      </p>
                      <span className="text-[10px] text-slate-400 mt-0.5 block">Booked / Joined Today</span>
                    </div>

                    <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[10px] font-bold uppercase tracking-wider">Waiting</span>
                        <Clock className="w-4 h-4 text-amber-500" />
                      </div>
                      <p className="text-2xl font-black text-amber-600 mt-1 tracking-tight">
                        {backendMetrics?.waiting_patients ?? 0}
                      </p>
                      <span className="text-[10px] text-slate-400 mt-0.5 block">In Clinic Waiting Area</span>
                    </div>

                    <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[10px] font-bold uppercase tracking-wider">In Consultation</span>
                        <Stethoscope className="w-4 h-4 text-emerald-500" />
                      </div>
                      <p className="text-2xl font-black text-emerald-600 mt-1 tracking-tight">
                        {backendMetrics?.in_consultation ?? 0}
                      </p>
                      <span className="text-[10px] text-slate-400 mt-0.5 block">Currently with Doctors</span>
                    </div>

                    <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[10px] font-bold uppercase tracking-wider">Completed</span>
                        <CheckCircle2 className="w-4 h-4 text-blue-600" />
                      </div>
                      <p className="text-2xl font-black text-slate-900 mt-1 tracking-tight">
                        {backendMetrics?.completed_consultations ?? 0}
                      </p>
                      <span className="text-[10px] text-slate-400 mt-0.5 block">Consultations Done</span>
                    </div>

                    <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[10px] font-bold uppercase tracking-wider">No Shows</span>
                        <AlertCircle className="w-4 h-4 text-rose-500" />
                      </div>
                      <p className="text-2xl font-black text-rose-600 mt-1 tracking-tight">
                        {backendMetrics?.no_shows ?? 0}
                      </p>
                      <span className="text-[10px] text-slate-400 mt-0.5 block">Did Not Arrive</span>
                    </div>

                    <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[10px] font-bold uppercase tracking-wider">Doctor Delays</span>
                        <AlertTriangle className="w-4 h-4 text-orange-500" />
                      </div>
                      <p className="text-2xl font-black text-orange-600 mt-1 tracking-tight">
                        {backendMetrics?.doctor_delays ?? 0}
                      </p>
                      <span className="text-[10px] text-slate-400 mt-0.5 block">Reported Today</span>
                    </div>

                    <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[10px] font-bold uppercase tracking-wider">Emergencies</span>
                        <Flame className="w-4 h-4 text-red-600" />
                      </div>
                      <p className="text-2xl font-black text-red-600 mt-1 tracking-tight">
                        {backendMetrics?.emergency_events ?? 0}
                      </p>
                      <span className="text-[10px] text-slate-400 mt-0.5 block">Urgent Insertions</span>
                    </div>

                    <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[10px] font-bold uppercase tracking-wider">Active Queues</span>
                        <Layers className="w-4 h-4 text-teal-600" />
                      </div>
                      <p className="text-2xl font-black text-teal-700 mt-1 tracking-tight">
                        {backendMetrics?.active_queues ?? queues.length}
                      </p>
                      <span className="text-[10px] text-slate-400 mt-0.5 block">Live Doctor Queues</span>
                    </div>
                  </div>
                </div>

                {/* Active Doctors & Queues Overview */}
                <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-2xs space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-base font-bold text-slate-900">Active Doctors & Today's Queues</h2>
                      <p className="text-xs text-slate-500">
                        Real-time status, current active token, and waiting counts for each clinic
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setIsBookModalOpen(true)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-sm cursor-pointer"
                      >
                        <UserPlus className="w-3.5 h-3.5" />
                        <span>+ Walk-in Patient</span>
                      </button>
                      <button
                        onClick={() => setActiveTab('queues')}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs shadow-sm cursor-pointer"
                      >
                        <Layers className="w-3.5 h-3.5" />
                        <span>View All Queues</span>
                      </button>
                    </div>
                  </div>

                  {queuesLoading ? (
                    <div className="py-12 text-center text-xs text-slate-400">
                      Loading active clinic queues from database...
                    </div>
                  ) : queues && queues.length > 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {queues.map((q) => {
                        const currentToken = q.current_token || 'None';
                        const opStatus = q.operational_status || (q.status === 'ACTIVE' ? 'Available' : q.status);
                        const isConsulting = opStatus === 'In Consultation';
                        const isCalling = opStatus === 'Calling';
                        const isPaused = opStatus === 'Paused';

                        return (
                          <div
                            key={q.queue_id}
                            className="p-5 rounded-2xl bg-slate-50 border border-slate-200/80 hover:border-blue-300 hover:bg-blue-50/20 transition-all flex flex-col justify-between gap-4 shadow-2xs group"
                          >
                            <div className="space-y-3">
                              <div className="flex items-center justify-between">
                                <span className="text-[10px] font-bold uppercase tracking-wider bg-blue-100 text-blue-700 px-2 py-0.5 rounded-md">
                                  {q.department_name || 'OPD Clinic'}
                                </span>
                                
                                <span
                                  className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold ${
                                    isConsulting
                                      ? 'bg-emerald-100 text-emerald-800'
                                      : isCalling
                                      ? 'bg-amber-100 text-amber-800 animate-pulse'
                                      : isPaused
                                      ? 'bg-slate-200 text-slate-700'
                                      : 'bg-blue-100 text-blue-800'
                                  }`}
                                >
                                  {(isConsulting || isCalling) && (
                                    <span className="w-1.5 h-1.5 rounded-full bg-current animate-ping" />
                                  )}
                                  <span>{opStatus}</span>
                                </span>
                              </div>

                              <div>
                                <h3 className="text-base font-bold text-slate-900 group-hover:text-blue-700 transition-colors">
                                  {q.doctor_name}
                                </h3>
                                <p className="text-xs text-slate-500 mt-0.5 font-medium">
                                  {q.queue_name}
                                </p>
                                <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
                                  {q.queue_date && (
                                    <span className="font-semibold text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md flex items-center gap-1">
                                      <Calendar className="w-3 h-3 text-blue-500" />
                                      <span>
                                        {new Date(q.queue_date + 'T00:00:00').toLocaleDateString('en-US', {
                                          day: 'numeric',
                                          month: 'short',
                                        })}
                                      </span>
                                    </span>
                                  )}
                                  {q.start_time && (
                                    <span className="font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md flex items-center gap-1">
                                      <Clock className="w-3 h-3 text-emerald-600" />
                                      <span>{q.start_time} – {q.end_time || 'End'}</span>
                                    </span>
                                  )}
                                </div>
                              </div>

                              <div className="grid grid-cols-2 gap-2 bg-white p-2.5 rounded-xl border border-slate-200/70 text-xs">
                                <div>
                                  <span className="text-[10px] text-slate-400 font-bold uppercase block">
                                    Current Token
                                  </span>
                                  <span className="font-extrabold text-slate-900 font-mono text-sm">
                                    {currentToken}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-[10px] text-slate-400 font-bold uppercase block">
                                    Active / Registered
                                  </span>
                                  <span className="font-extrabold text-blue-600 text-sm flex items-center gap-1">
                                    <Users className="w-3.5 h-3.5" />
                                    {q.total_active ?? (q.waiting_count ?? q.total_waiting)}
                                  </span>
                                </div>
                              </div>
                            </div>

                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => setAvailabilityDoctor({ id: q.doctor_id, name: q.doctor_name })}
                                className="px-3 py-2.5 rounded-xl border border-slate-300 hover:border-emerald-500 hover:bg-emerald-50 text-slate-700 hover:text-emerald-800 font-semibold text-xs transition-all flex items-center gap-1.5 cursor-pointer shadow-2xs"
                                title="Configure date availability for this doctor"
                              >
                                <Calendar className="w-3.5 h-3.5 text-emerald-600" />
                                <span>Availability</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => navigate(`/staff/queue/${q.queue_id}${q.queue_date ? `?date=${q.queue_date}` : ''}`)}
                                className="flex-1 inline-flex items-center justify-center gap-2 px-3.5 py-2.5 rounded-xl bg-slate-900 group-hover:bg-blue-600 text-white font-semibold text-xs shadow-2xs transition-all cursor-pointer"
                              >
                                <span>Queue Control</span>
                                <ArrowRight className="w-3.5 h-3.5 text-blue-400 group-hover:text-white" />
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="p-8 rounded-2xl bg-slate-50 text-center text-xs text-slate-400">
                      No active doctor queues detected for this hospital.
                    </div>
                  )}
                </div>
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
