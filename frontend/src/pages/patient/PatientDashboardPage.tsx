import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Calendar,
  Clock,
  MapPin,
  Plus,
  Car,
  Bike,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  LogOut,
  ChevronRight,
  Sparkles,
  Bell,
  X,
  Navigation,
  Footprints,
  Radio,
} from 'lucide-react';
import { queueEntriesApi } from '../../api/queueEntries';
import { notificationsApi, type NotificationItem } from '../../api/notifications';
import { useAuth } from '../../store/AuthContext';
import { BrandLogo } from '../../components/BrandLogo';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useRelativeTime } from '../../hooks/useRelativeTime';
import { formatTime, formatDateTime, formatDoctorName } from '../../utils/format';

function NotificationRow({ item }: { item: NotificationItem }) {
  const relativeTime = useRelativeTime(item.created_at);
  return (
    <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1 text-xs">
      <div className="flex items-center justify-between gap-2">
        <span className="font-bold text-slate-900">{item.title || 'Notification'}</span>
        <span className="text-[10px] text-slate-400 shrink-0 font-medium">{relativeTime}</span>
      </div>
      <p className="text-slate-600 leading-relaxed">{item.message}</p>
      <div className="flex items-center gap-2 pt-1">
        <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
          {item.channel}
        </span>
        <span className="text-[9px] font-medium text-slate-400 capitalize">
          Status: {item.status}
        </span>
      </div>
    </div>
  );
}

export default function PatientDashboardPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<'today' | 'upcoming' | 'past'>('today');
  const [isNotifOpen, setIsNotifOpen] = useState(false);

  // 1. Fetch appointments
  const {
    data: appointmentsData,
    isLoading,
    isRefetching,
    refetch: refetchAppointments,
    error,
  } = useQuery({
    queryKey: ['my-appointments'],
    queryFn: () => queueEntriesApi.getMy(),
    staleTime: 5000,
    refetchInterval: 10000,
  });

  // 2. Fetch in-app notifications
  const {
    data: notifsData,
    refetch: refetchNotifications,
  } = useQuery({
    queryKey: ['my-notifications'],
    queryFn: () => notificationsApi.getMy(),
    staleTime: 5000,
    refetchInterval: 10000,
  });

  const notifications = notifsData?.items || [];
  const unreadCount = notifications.length;

  // 3. Real-time WebSocket connection for user events & notifications
  const token = localStorage.getItem('qflow_token');
  useWebSocket({
    path: '/ws/user',
    token,
    enabled: Boolean(token),
    onMessage: () => {
      // Automatic live update on CALL, START, COMPLETE, DELAY, EMERGENCY, NOTIFICATION
      refetchAppointments();
      refetchNotifications();
    },
  });

  const todayList = appointmentsData?.today ?? [];
  const upcomingList = appointmentsData?.upcoming ?? [];
  const pastList = appointmentsData?.past ?? [];

  const currentList =
    activeTab === 'today'
      ? todayList
      : activeTab === 'upcoming'
      ? upcomingList
      : pastList;

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'IN_CONSULTATION':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300 animate-pulse">
            <span className="w-2 h-2 rounded-full bg-emerald-600" />
            In Consultation
          </span>
        );
      case 'CALLED':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300 animate-bounce">
            <span className="w-2 h-2 rounded-full bg-amber-600" />
            Called — Enter OPD Room
          </span>
        );
      case 'WAITING':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <Clock className="w-3.5 h-3.5" />
            Waiting in Queue
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            Completed
          </span>
        );
      case 'NO_SHOW':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertCircle className="w-3.5 h-3.5" />
            No Show
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans relative">
      {/* Top Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-2xs">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <BrandLogo size="md" />
            <span className="hidden sm:inline-block px-2.5 py-1 text-xs font-bold bg-emerald-50 text-emerald-700 rounded-md border border-emerald-100">
              Patient Portal
            </span>
          </div>

          <div className="flex items-center gap-3">
            {/* Real-time Indicator */}
            <span className="hidden md:inline-flex items-center gap-1.5 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
              <Radio className="w-3 h-3 text-emerald-600 animate-pulse" />
              <span>Real-Time Sync Active</span>
            </span>

            {/* Notification Bell Button */}
            <button
              onClick={() => setIsNotifOpen(!isNotifOpen)}
              className="relative p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors cursor-pointer"
              title="Notifications"
            >
              <Bell className="w-4 h-4" />
              {unreadCount > 0 && (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-emerald-600 ring-2 ring-white" />
              )}
            </button>

            <button
              onClick={() => {
                refetchAppointments();
                refetchNotifications();
              }}
              disabled={isRefetching}
              title="Refresh appointments"
              className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors cursor-pointer"
            >
              <RefreshCw className={`w-4 h-4 ${isRefetching ? 'animate-spin text-emerald-600' : ''}`} />
            </button>

            <Link
              to="/book"
              className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-xs transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Book Appointment</span>
            </Link>

            <div className="h-6 w-px bg-slate-200 mx-1 hidden sm:block" />

            <div className="flex items-center gap-2 text-sm text-slate-700">
              <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center font-bold text-xs">
                {user?.name ? user.name.slice(0, 2).toUpperCase() : 'PT'}
              </div>
              <span className="hidden md:inline font-semibold text-xs text-slate-800">{user?.name}</span>
            </div>

            <button
              onClick={() => {
                logout();
                navigate('/login');
              }}
              title="Log out"
              className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition-colors cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Slide-over In-App Notification Drawer */}
      {isNotifOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div
            className="absolute inset-0 bg-slate-900/30 backdrop-blur-xs transition-opacity"
            onClick={() => setIsNotifOpen(false)}
          />
          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-sm bg-white shadow-2xl flex flex-col">
              <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
                <div className="flex items-center gap-2">
                  <Bell className="w-4 h-4 text-emerald-600" />
                  <h2 className="text-sm font-bold text-slate-900">In-App Notifications</h2>
                </div>
                <button
                  onClick={() => setIsNotifOpen(false)}
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {notifications.length === 0 ? (
                  <div className="py-12 text-center text-xs text-slate-400">
                    No notifications yet. You will be notified here on queue movements, calls, doctor delays, and departures.
                  </div>
                ) : (
                  notifications.map((notif) => (
                    <NotificationRow key={notif.id} item={notif} />
                  ))
                )}
              </div>

              <div className="p-3 border-t border-slate-200 bg-slate-50 text-[11px] text-slate-500 text-center">
                Real-time updates are enabled. External SMS channel: <span className="font-bold text-slate-700">Configuration Required</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome & Overview Banner */}
        <div className="bg-gradient-to-r from-emerald-800 to-teal-900 rounded-3xl p-6 sm:p-8 text-white mb-8 shadow-sm relative overflow-hidden">
          <div className="relative z-10 max-w-2xl">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight mb-2">
              Hello, {user?.name || 'Patient'}
            </h1>
            <p className="text-emerald-100 text-sm sm:text-base mb-6">
              Track your appointments, live queue positions, doctor turns, and travel departure recommendations in real time without refreshing.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                to="/book"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-white text-emerald-900 hover:bg-emerald-50 text-sm font-bold rounded-xl shadow-md transition-all"
              >
                <Plus className="w-4 h-4 text-emerald-700" />
                <span>Book New Appointment</span>
              </Link>
            </div>
          </div>
          <div className="absolute right-0 top-0 bottom-0 w-80 opacity-10 pointer-events-none flex items-center justify-center">
            <Sparkles className="w-64 h-64 text-white" />
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center justify-between border-b border-slate-200 mb-6">
          <div className="flex gap-2 sm:gap-6">
            <button
              onClick={() => setActiveTab('today')}
              className={`pb-3 text-sm font-semibold border-b-2 flex items-center gap-2 transition-colors cursor-pointer ${
                activeTab === 'today'
                  ? 'border-emerald-600 text-emerald-800'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Clock className="w-4 h-4" />
              <span>Today's Visits</span>
              {todayList.length > 0 && (
                <span className="px-2 py-0.5 text-xs rounded-full bg-emerald-100 text-emerald-800 font-bold">
                  {todayList.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('upcoming')}
              className={`pb-3 text-sm font-semibold border-b-2 flex items-center gap-2 transition-colors cursor-pointer ${
                activeTab === 'upcoming'
                  ? 'border-emerald-600 text-emerald-800'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Calendar className="w-4 h-4" />
              <span>Upcoming</span>
              {upcomingList.length > 0 && (
                <span className="px-2 py-0.5 text-xs rounded-full bg-slate-200 text-slate-700 font-bold">
                  {upcomingList.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('past')}
              className={`pb-3 text-sm font-semibold border-b-2 flex items-center gap-2 transition-colors cursor-pointer ${
                activeTab === 'past'
                  ? 'border-emerald-600 text-emerald-800'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Past History</span>
              {pastList.length > 0 && (
                <span className="px-2 py-0.5 text-xs rounded-full bg-slate-200 text-slate-700 font-bold">
                  {pastList.length}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Appointments List */}
        {isLoading ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center">
            <div className="w-8 h-8 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-slate-500 text-sm">Loading your appointments...</p>
          </div>
        ) : error ? (
          <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center text-rose-700">
            <AlertCircle className="w-6 h-6 mx-auto mb-2 text-rose-500" />
            <p className="font-semibold text-sm">Failed to load appointments</p>
            <button
              onClick={() => refetchAppointments()}
              className="mt-3 px-4 py-1.5 bg-rose-600 text-white rounded-lg text-xs font-semibold hover:bg-rose-700"
            >
              Retry
            </button>
          </div>
        ) : currentList.length === 0 ? (
          <div className="bg-white rounded-3xl border border-slate-200 p-12 text-center">
            <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4 text-slate-400">
              <Calendar className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-slate-800 mb-1">
              No {activeTab} appointments found
            </h3>
            <p className="text-slate-500 text-sm max-w-sm mx-auto mb-6">
              {activeTab === 'today'
                ? "You don't have any appointments scheduled for today. Need to see a doctor?"
                : activeTab === 'upcoming'
                ? "You don't have any future scheduled appointments at this time."
                : 'No past appointment records found.'}
            </p>
            <Link
              to="/book"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-xl shadow-sm transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Book An Appointment</span>
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5">
            {currentList.map((item) => {
              // Determine patients ahead
              let patientsAheadText = null;
              if (item.status === 'WAITING' || item.status === 'ARRIVED') {
                if (item.position !== null && item.position > 1) {
                  patientsAheadText = `${item.position - 1} patients ahead`;
                } else if (item.position === 1) {
                  patientsAheadText = 'Next in line (0 ahead)';
                }
              } else if (item.status === 'CALLED') {
                patientsAheadText = 'Currently called — Please enter room';
              } else if (item.status === 'IN_CONSULTATION') {
                patientsAheadText = 'Currently with doctor';
              }

              // Departure calculation display
              const isConfigRequired = item.travel_status === 'CONFIGURATION_REQUIRED';
              const hasTravelDuration = item.travel_duration_minutes !== null && item.travel_duration_minutes !== undefined;
              const hasDepartureTime = Boolean(item.latest_departure_time);

              return (
                <div
                  key={item.id}
                  onClick={() => navigate(`/ticket/${item.id}`)}
                  className="bg-white rounded-3xl border border-slate-200 p-6 hover:border-emerald-500 hover:shadow-md transition-all cursor-pointer relative group"
                >
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                    {/* Left: Token & Clinic Details */}
                    <div className="flex items-start gap-4">
                      <div className="w-16 h-16 rounded-2xl bg-emerald-50 border border-emerald-100 flex flex-col items-center justify-center text-emerald-800 font-extrabold shadow-sm shrink-0">
                        <span className="text-[10px] uppercase text-emerald-600 font-bold tracking-wider">Token</span>
                        <span className="text-xl leading-none font-mono font-black">{item.token_display}</span>
                      </div>

                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          {getStatusBadge(item.status)}
                          {patientsAheadText && (
                            <span className="text-xs font-bold px-2.5 py-0.5 rounded-md bg-slate-100 text-slate-700">
                              {patientsAheadText}
                            </span>
                          )}
                          {(item.priority_class as string) !== 'normal' && item.priority_class !== 'NORMAL' && (
                            <span className="text-xs font-bold px-2 py-0.5 rounded-md bg-amber-100 text-amber-800 uppercase">
                              {item.priority_class}
                            </span>
                          )}
                        </div>

                        <h3 className="text-lg font-bold text-slate-900 group-hover:text-emerald-700 transition-colors">
                          {formatDoctorName(item.doctor_name)}
                        </h3>
                        <p className="text-xs font-bold text-emerald-800">
                          {item.department_name}
                        </p>
                        <div className="text-xs text-slate-500 flex items-center gap-1.5 flex-wrap">
                          <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span className="font-medium text-slate-700">{item.hospital_name}</span>
                          {item.hospital_address && <span className="text-slate-400 truncate max-w-xs">• {item.hospital_address}</span>}
                        </div>
                        <p className="text-[11px] text-slate-400">
                          Appointment: {formatDateTime(item.joined_at)}
                        </p>
                      </div>
                    </div>

                    {/* Middle: Unified Arrival Intelligence & Queue Telemetry */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50/90 p-4 rounded-2xl border border-slate-200/80 text-xs min-w-0 flex-1">
                      {/* Estimated Turn / Consultation */}
                      <div className="min-w-0">
                        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block truncate">
                          Est. Turn
                        </span>
                        <span className="text-xs sm:text-sm font-bold text-slate-900 block truncate">
                          {item.estimated_start_time ? formatTime(item.estimated_start_time) : <span className="text-slate-400 font-normal">Pending</span>}
                        </span>
                      </div>

                      {/* Estimated Wait */}
                      <div className="min-w-0">
                        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block truncate">
                          Est. Wait
                        </span>
                        <span className="text-xs sm:text-sm font-bold text-blue-600 block truncate">
                          {item.estimated_wait_minutes !== null && item.estimated_wait_minutes !== undefined
                            ? `~${item.estimated_wait_minutes} min`
                            : <span className="text-slate-400 font-normal">—</span>}
                        </span>
                      </div>

                      {/* Travel Duration */}
                      <div className="min-w-0">
                        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block truncate">
                          Travel Time
                        </span>
                        <span className="text-xs font-bold text-slate-800 flex items-center gap-1 mt-0.5 truncate">
                          {hasTravelDuration ? (
                            <>
                              {item.travel_mode === 'WALK' ? (
                                <Footprints className="w-3.5 h-3.5 text-teal-600 shrink-0" />
                              ) : item.travel_mode === 'TWO_WHEELER' ? (
                                <Bike className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                              ) : (
                                <Car className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                              )}
                              <span>~{item.travel_duration_minutes}m</span>
                            </>
                          ) : isConfigRequired ? (
                            <span className="text-amber-600 text-[10px] font-semibold" title="Google Maps API key not configured">
                              Config Req.
                            </span>
                          ) : (
                            <span className="text-slate-400 text-[11px]">Unset</span>
                          )}
                        </span>
                      </div>

                      {/* When Should I Leave? */}
                      <div className="min-w-0">
                        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block truncate">
                          Leave By
                        </span>
                        <span className="text-xs sm:text-sm font-black text-emerald-700 block truncate">
                          {hasDepartureTime ? (
                            formatTime(item.latest_departure_time)
                          ) : isConfigRequired ? (
                            <span className="text-amber-700 text-[10px] font-semibold">Config Req.</span>
                          ) : (
                            <span className="text-slate-400 text-xs font-normal">Set Origin</span>
                          )}
                        </span>
                      </div>
                    </div>

                    {/* Right: Unified Single Action */}
                    <div className="flex items-center shrink-0 self-end lg:self-center">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/ticket/${item.id}#travel`);
                        }}
                        title="Open unified queue tracking and real-time arrival plan"
                        className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-700 hover:bg-emerald-800 text-white text-xs sm:text-sm font-bold rounded-xl shadow-sm hover:shadow-md transition-all cursor-pointer group-hover:scale-[1.02]"
                      >
                        <Navigation className="w-4 h-4 text-emerald-200" />
                        <span>Track & Plan Arrival</span>
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
