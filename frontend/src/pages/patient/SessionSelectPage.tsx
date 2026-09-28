import { useState, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Clock,
  Calendar,
  Ticket,
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  User,
  Sparkles,
  ChevronRight,
} from 'lucide-react';
import { schedulesApi } from '../../api/schedules';
import { queuesApi } from '../../api/queues';
import { PageHeader } from '../../components/PageHeader';
import { SkeletonList } from '../../components/Skeleton';
import { ErrorState } from '../../components/ErrorState';
import { EmptyState } from '../../components/EmptyState';
import { Modal } from '../../components/Modal';
import { extractErrorMessage } from '../../api/client';
import type { AvailableDoctorItem, QueueJoinResponse } from '../../types/api';

export default function SessionSelectPage() {
  const { doctorId } = useParams<{ doctorId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [selectedSchedule, setSelectedSchedule] = useState<AvailableDoctorItem | null>(null);
  const [selectedTime, setSelectedTime] = useState<string>('');
  const [joinedResult, setJoinedResult] = useState<QueueJoinResponse | null>(null);
  const [joinError, setJoinError] = useState<string | null>(null);

  const isValidParam = Boolean(doctorId && doctorId !== ':doctorId');

  // Query doctor availability and scheduled OPD sessions
  const {
    data: availabilityData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['doctor-availability', doctorId],
    queryFn: () => schedulesApi.getDoctorAvailability(doctorId!),
    enabled: isValidParam,
    staleTime: 5_000,
    refetchInterval: 8_000,
  });

  const schedules = availabilityData?.schedules || [];
  const doctorName = availabilityData?.doctor_name || 'Specialist Clinician';

  // Generate 30-minute time slots for selected schedule
  const timeSlots = useMemo(() => {
    if (!selectedSchedule) return [];
    const [sh, sm] = (selectedSchedule.start_time || '09:00').split(':').map(Number);
    const [eh, em] = (selectedSchedule.end_time || '13:00').split(':').map(Number);
    const slots: { value: string; label: string }[] = [];
    for (let m = sh * 60 + sm; m < eh * 60 + em; m += 30) {
      const h = Math.floor(m / 60);
      const min = m % 60;
      const val = `${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}:00`;
      const period = h >= 12 ? 'PM' : 'AM';
      const dispHour = h % 12 || 12;
      const label = `${dispHour}:${String(min).padStart(2, '0')} ${period}`;
      slots.push({ value: val, label });
    }
    return slots;
  }, [selectedSchedule]);

  // Automatically select first available schedule if none selected
  useMemo(() => {
    if (schedules.length > 0 && !selectedSchedule) {
      setSelectedSchedule(schedules[0]);
    }
  }, [schedules, selectedSchedule]);

  // Join Queue Mutation
  const joinMutation = useMutation({
    mutationFn: async () => {
      if (!selectedSchedule?.queue_id) {
        throw new Error('This schedule does not have an active queue.');
      }
      return queuesApi.join(
        selectedSchedule.queue_id,
        selectedSchedule.schedule_date,
        selectedTime || undefined
      );
    },
    onSuccess: (resp) => {
      queryClient.invalidateQueries({ queryKey: ['doctor-availability'] });
      setJoinedResult(resp);
      setJoinError(null);
    },
    onError: (err) => {
      setJoinError(extractErrorMessage(err));
    },
  });

  if (!isValidParam) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
        <PageHeader title="Doctor Required" backTo="/hospitals" />
        <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8">
          <ErrorState
            title="Doctor Not Specified"
            message="Please select a clinician from the directory before choosing an OPD session."
            backTo="/hospitals"
            backLabel="Back to Hospitals"
          />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <PageHeader
        title="Book OPD Consultation"
        subtitle="Select a date from the doctor's published schedule and choose your preferred time."
      />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 py-6 animate-fade-up space-y-6">
        {/* Error notification */}
        {joinError && (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-start gap-3 shadow-xs">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-rose-600" />
            <div className="flex-1">
              <p className="font-bold">Unable to book appointment</p>
              <p className="mt-0.5 text-xs text-rose-600">{joinError}</p>
            </div>
            <button
              onClick={() => setJoinError(null)}
              className="text-xs font-bold text-rose-500 hover:text-rose-800 cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Doctor Identity Card */}
        <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-5">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-blue-50 border border-blue-100 text-blue-700 font-black text-xl flex items-center justify-center shrink-0 shadow-inner">
              <User className="w-7 h-7" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-black text-slate-900">{doctorName}</h1>
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  <Sparkles className="w-3 h-3 text-emerald-600" />
                  OPD Active
                </span>
              </div>
              <p className="text-xs font-medium text-slate-500 mt-1">
                Hospital OPD Wing • Real-Time Digital Queue Integration
              </p>
            </div>
          </div>
        </div>

        {/* Loading state */}
        {isLoading && <SkeletonList count={2} />}

        {/* Error state */}
        {isError && (
          <ErrorState
            title="Failed to Load Doctor Schedule"
            message={extractErrorMessage(error)}
            onRetry={() => refetch()}
            backTo="/hospitals"
            backLabel="Back to Directory"
          />
        )}

        {/* Empty state: Doctor has no published OPD schedule */}
        {!isLoading && !isError && schedules.length === 0 && (
          <EmptyState
            icon={<Calendar className="w-8 h-8 text-slate-400" />}
            title="No OPD Sessions Scheduled"
            description="Hospital staff has not yet scheduled an OPD clinic for this doctor. Doctor availability requires a staff-created queue."
            action={
              <button
                type="button"
                onClick={() => navigate(-1)}
                className="px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 cursor-pointer"
              >
                Choose Another Doctor
              </button>
            }
          />
        )}

        {/* Available Dates & Time Selection */}
        {!isLoading && !isError && schedules.length > 0 && (
          <div className="space-y-6">
            {/* Step 1: Select Date */}
            <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-blue-600" />
                    <span>Select Consultation Date</span>
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Showing all dates where Dr. {doctorName} has a scheduled OPD session.
                  </p>
                </div>
                <span className="text-xs font-semibold bg-blue-50 text-blue-700 px-3 py-1 rounded-full">
                  {schedules.length} Available Date{schedules.length > 1 ? 's' : ''}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {schedules.map((schedule) => {
                  const isSelected = selectedSchedule?.schedule_date === schedule.schedule_date;
                  const dateObj = new Date(`${schedule.schedule_date}T00:00:00`);
                  const dayName = dateObj.toLocaleDateString('en-US', { weekday: 'short' });
                  const formattedDate = dateObj.toLocaleDateString('en-US', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                  });

                  return (
                    <button
                      key={`${schedule.schedule_date}-${schedule.start_time}`}
                      type="button"
                      onClick={() => {
                        setSelectedSchedule(schedule);
                        setSelectedTime('');
                      }}
                      className={`text-left p-4 rounded-2xl border-2 transition-all cursor-pointer ${
                        isSelected
                          ? 'border-blue-600 bg-blue-50/70 shadow-xs ring-2 ring-blue-500/20'
                          : 'border-slate-200 bg-slate-50 hover:bg-white hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                          {dayName}
                        </span>
                        {isSelected && (
                          <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          </span>
                        )}
                      </div>
                      <p className="text-base font-black text-slate-900 mt-1">{formattedDate}</p>
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-blue-700 mt-2">
                        <Clock className="w-3.5 h-3.5" />
                        <span>{schedule.formatted_time}</span>
                      </div>
                      <div className="mt-2 text-[11px] text-slate-500">
                        {schedule.total_waiting} patient{schedule.total_waiting === 1 ? '' : 's'} ahead in queue
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Step 2: Select Time Slot */}
            {selectedSchedule && (
              <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs space-y-4">
                <div>
                  <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                    <Clock className="w-4 h-4 text-blue-600" />
                    <span>Choose Consultation Time Slot</span>
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    OPD Session Window: {selectedSchedule.formatted_time}
                  </p>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  {timeSlots.map((slot) => {
                    const isSlotSelected = selectedTime === slot.value;
                    return (
                      <button
                        key={slot.value}
                        type="button"
                        onClick={() => setSelectedTime(slot.value)}
                        className={`py-3 px-4 rounded-xl text-xs font-bold border transition-all text-center cursor-pointer ${
                          isSlotSelected
                            ? 'bg-slate-900 text-white border-slate-900 shadow-xs'
                            : 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100 hover:border-slate-300'
                        }`}
                      >
                        {slot.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Step 3: Booking Confirmation Box */}
            {selectedSchedule && (
              <div className="bg-gradient-to-r from-slate-900 to-blue-950 text-white rounded-3xl p-6 shadow-md flex flex-col sm:flex-row sm:items-center justify-between gap-5">
                <div className="space-y-1">
                  <span className="text-xs font-bold uppercase tracking-wider text-blue-300">
                    Booking Summary
                  </span>
                  <h3 className="text-lg font-black">
                    {doctorName} • {selectedSchedule.department_name}
                  </h3>
                  <p className="text-xs text-slate-300 flex items-center gap-2">
                    <span>
                      📅{' '}
                      {new Date(`${selectedSchedule.schedule_date}T00:00:00`).toLocaleDateString(
                        'en-US',
                        { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }
                      )}
                    </span>
                    <span>•</span>
                    <span>
                      ⏰{' '}
                      {selectedTime
                        ? timeSlots.find((s) => s.value === selectedTime)?.label
                        : 'First Available Slot'}
                    </span>
                  </p>
                </div>

                <button
                  type="button"
                  disabled={joinMutation.isPending}
                  onClick={() => joinMutation.mutate()}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-2xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-sm transition-all shadow-md cursor-pointer disabled:opacity-50 shrink-0"
                >
                  <Ticket className="w-4 h-4 text-slate-950" />
                  <span>
                    {joinMutation.isPending ? 'Generating Token...' : 'Confirm & Book Token'}
                  </span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* Success Modal */}
        <Modal
          isOpen={Boolean(joinedResult)}
          onClose={() => {
            if (joinedResult) navigate(`/ticket/${joinedResult.entry.id}`);
          }}
          title="OPD Queue Token Assigned"
          subtitle="Your digital consultation ticket has been registered in the hospital queue."
          footer={
            <button
              type="button"
              onClick={() => {
                if (joinedResult) navigate(`/ticket/${joinedResult.entry.id}`);
              }}
              className="w-full inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-2xl bg-slate-900 hover:bg-slate-800 text-white font-bold text-sm shadow-xs transition-all cursor-pointer"
            >
              <span>View Live Consultation Ticket</span>
              <ChevronRight className="w-4 h-4 text-blue-400" />
            </button>
          }
        >
          {joinedResult && (
            <div className="text-center py-4 space-y-4">
              <div className="w-16 h-16 rounded-3xl bg-emerald-50 border border-emerald-200 text-emerald-600 flex items-center justify-center mx-auto shadow-2xs">
                <CheckCircle2 className="w-9 h-9" />
              </div>

              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Your Digital Token
                </p>
                <p className="text-6xl font-black text-slate-900 mt-1 tracking-tight font-mono">
                  {joinedResult.entry.token_display}
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 text-left space-y-2 text-xs">
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Doctor:</span>
                  <span className="font-bold text-slate-900">{doctorName}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Date:</span>
                  <span className="font-bold text-slate-900">
                    {joinedResult.entry.appointment_date || selectedSchedule?.schedule_date}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Initial Status:</span>
                  <span className="font-bold text-emerald-700 bg-emerald-100 px-2.5 py-0.5 rounded-full">
                    {joinedResult.entry.status}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-3 p-3.5 rounded-2xl bg-blue-50/70 border border-blue-200 text-xs text-blue-800 text-left">
                <ShieldCheck className="w-5 h-5 text-blue-600 shrink-0" />
                <span>
                  Your appointment is entered into the official hospital queue. When you arrive, staff will mark your arrival using this token.
                </span>
              </div>
            </div>
          )}
        </Modal>
      </main>
    </div>
  );
}
