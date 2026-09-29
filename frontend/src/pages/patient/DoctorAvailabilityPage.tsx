import { useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  CalendarDays,
  Clock,
  CheckCircle2,
  AlertCircle,
  Stethoscope,
  ChevronRight,
  Calendar,
} from 'lucide-react';
import { schedulesApi } from '../../api/schedules';
import { queuesApi } from '../../api/queues';
import { PageHeader } from '../../components/PageHeader';
import { extractErrorMessage } from '../../api/client';
import type { AvailableDoctorItem } from '../../types/api';

export default function DoctorAvailabilityPage() {
  const { doctorId } = useParams<{ doctorId: string }>();
  const [params] = useSearchParams();
  const navigate = useNavigate();

  const hospitalId = params.get('hospitalId') || undefined;
  const departmentId = params.get('departmentId') || undefined;

  const [selectedSchedule, setSelectedSchedule] = useState<AvailableDoctorItem | null>(null);
  const [selectedTime, setSelectedTime] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Fetch real doctor schedule availability directly from database API
  const {
    data: availabilityData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['doctor-schedule-availability', doctorId, hospitalId, departmentId],
    queryFn: () => schedulesApi.getDoctorAvailability(doctorId!, hospitalId, departmentId),
    enabled: Boolean(doctorId && doctorId !== ':doctorId'),
    staleTime: 5_000,
    refetchInterval: 10_000,
  });

  const schedules: AvailableDoctorItem[] = availabilityData?.schedules || [];
  const doctorName = availabilityData?.doctor_name || 'Doctor';

  // Format date helper: e.g. "24 September 2026"
  const formatDateTitle = (dateStr: string) => {
    try {
      const [y, m, d] = dateStr.split('-').map(Number);
      const dt = new Date(y, m - 1, d);
      const now = new Date();
      now.setHours(0, 0, 0, 0);

      const target = new Date(dt);
      target.setHours(0, 0, 0, 0);

      const diffDays = Math.round((target.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

      const formatted = dt.toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      });

      if (diffDays === 0) return `Today, ${formatted}`;
      if (diffDays === 1) return `Tomorrow, ${formatted}`;
      return formatted;
    } catch {
      return dateStr;
    }
  };

  // Generate 30-minute time slots within the doctor's scheduled shift
  const timeSlots = useMemo(() => {
    if (!selectedSchedule) return [];
    const [sh, sm] = (selectedSchedule.start_time || '09:00:00').split(':').map(Number);
    const [eh, em] = (selectedSchedule.end_time || '13:00:00').split(':').map(Number);

    const result: { value: string; label: string }[] = [];
    for (let m = sh * 60 + sm; m < eh * 60 + em; m += 30) {
      const hour = Math.floor(m / 60);
      const min = m % 60;
      const val = `${String(hour).padStart(2, '0')}:${String(min).padStart(2, '0')}:00`;
      const period = hour >= 12 ? 'PM' : 'AM';
      const dispHour = hour % 12 || 12;
      const label = `${dispHour}:${String(min).padStart(2, '0')} ${period}`;
      result.push({ value: val, label });
    }
    return result;
  }, [selectedSchedule]);

  // Book Appointment Mutation
  const bookMutation = useMutation({
    mutationFn: async () => {
      if (!selectedSchedule) throw new Error('Please select an available date');
      return queuesApi.join(
        selectedSchedule.queue_id || undefined,
        selectedSchedule.schedule_date,
        selectedTime || undefined,
        {
          doctor_id: doctorId,
          hospital_id: hospitalId || undefined,
          department_id: departmentId || undefined,
        }
      );
    },
    onSuccess: (resp) => {
      navigate(`/ticket/${resp.entry.id}`);
    },
    onError: (err) => {
      setErrorMessage(extractErrorMessage(err));
    },
  });

  const handleSelectDate = (sched: AvailableDoctorItem) => {
    setSelectedSchedule(sched);
    setSelectedTime('');
    setErrorMessage(null);
  };

  if (!doctorId || doctorId === ':doctorId') {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
        <PageHeader title="Doctor Not Found" backTo="/hospitals" />
        <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8">
          <div className="p-6 bg-white rounded-2xl border text-center">
            <AlertCircle className="w-8 h-8 text-rose-500 mx-auto mb-2" />
            <p className="text-sm text-slate-600">Please select a doctor from the hospital directory.</p>
          </div>
        </main>
      </div>
    );
  }

  const backUrl = departmentId
    ? `/doctors/${departmentId}${hospitalId ? `?hospitalId=${hospitalId}` : ''}`
    : hospitalId
    ? `/departments/${hospitalId}`
    : '/hospitals';

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <PageHeader
        title={`Book appointment with ${doctorName}`}
        subtitle="Dates and shift hours are strictly derived from real hospital OPD schedules."
        backTo={backUrl}
      />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6 animate-fade-up">
        {/* Clinician Summary Header */}
        <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-cyan-50 border border-cyan-200 text-cyan-700 flex items-center justify-center font-bold shrink-0">
              <Stethoscope className="w-7 h-7" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-black uppercase tracking-wider bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded">
                  Hospital Roster Verified
                </span>
                <span className="text-xs text-slate-500 font-semibold">
                  OPD Outpatient
                </span>
              </div>
              <h1 className="text-xl font-black text-slate-900 mt-1">
                {doctorName}
              </h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Specialist Clinician • Verified Hospital Staff Schedule
              </p>
            </div>
          </div>

          <div className="text-right sm:border-l sm:border-slate-100 sm:pl-6">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block">
              Available Clinic Days
            </span>
            <span className="text-2xl font-black text-cyan-600">
              {schedules.length}
            </span>
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="bg-white rounded-3xl p-12 border border-slate-200 text-center">
            <div className="w-8 h-8 border-2 border-cyan-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-xs font-semibold text-slate-500">
              Loading doctor's scheduled clinic dates...
            </p>
          </div>
        )}

        {/* Error State */}
        {isError && (
          <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-xs flex items-center justify-between">
            <span>{extractErrorMessage(error)}</span>
            <button
              onClick={() => refetch()}
              className="px-3 py-1 bg-rose-600 text-white rounded-lg font-bold"
            >
              Retry
            </button>
          </div>
        )}

        {/* No Scheduled Dates State */}
        {!isLoading && !isError && schedules.length === 0 && (
          <div className="bg-white rounded-3xl p-12 border border-slate-200 text-center space-y-3">
            <div className="w-14 h-14 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto">
              <CalendarDays className="w-7 h-7" />
            </div>
            <h2 className="text-base font-bold text-slate-900">
              No Scheduled Dates Available
            </h2>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              {doctorName} currently does not have any active future clinic shifts scheduled by the hospital staff.
              Doctors are available only on days with an official staff schedule.
            </p>
            <div className="pt-2">
              <button
                type="button"
                onClick={() => navigate(-1)}
                className="px-4 py-2 rounded-xl bg-slate-900 text-white text-xs font-bold hover:bg-slate-800 transition-colors"
              >
                Choose Another Doctor
              </button>
            </div>
          </div>
        )}

        {/* AVAILABLE DATES SECTION */}
        {!isLoading && !isError && schedules.length > 0 && (
          <div className="space-y-6">
            <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-2xs space-y-4">
              <div>
                <span className="text-[10px] font-black uppercase tracking-wider text-cyan-600 bg-cyan-50 px-2 py-0.5 rounded border border-cyan-200">
                  Select Clinic Date
                </span>
                <h2 className="text-lg font-black text-slate-900 mt-1">
                  AVAILABLE DATES
                </h2>
                <p className="text-xs text-slate-500">
                  Showing only dates where {doctorName} has an active staff-created OPD shift.
                </p>
              </div>

              {/* Date Cards Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3.5">
                {schedules.map((sched) => {
                  const isSelected = selectedSchedule?.schedule_date === sched.schedule_date;
                  return (
                    <button
                      key={sched.schedule_date}
                      type="button"
                      onClick={() => handleSelectDate(sched)}
                      className={`p-4 rounded-2xl border-2 text-left transition-all cursor-pointer flex flex-col justify-between gap-3 ${
                        isSelected
                          ? 'border-emerald-600 bg-emerald-50/70 shadow-sm ring-2 ring-emerald-100'
                          : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/60'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <Calendar className={`w-4 h-4 ${isSelected ? 'text-emerald-700' : 'text-slate-500'}`} />
                          <span className={`font-bold text-xs ${isSelected ? 'text-emerald-950 font-black' : 'text-slate-900'}`}>
                            {formatDateTitle(sched.schedule_date)}
                          </span>
                        </div>
                        {isSelected && (
                          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                        )}
                      </div>

                      <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                        <span className="text-xs font-mono font-bold text-emerald-800 flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5 text-emerald-600" />
                          <span>{sched.formatted_time || `${sched.start_time} – ${sched.end_time}`}</span>
                        </span>
                        <span className="text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
                          Available
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* TIME SELECTION & APPOINTMENT CONFIRMATION CARD */}
            {selectedSchedule && (
              <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200/90 shadow-2xs space-y-6 animate-fade-up">
                <div className="border-b border-slate-100 pb-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                      <span className="text-[10px] font-black uppercase tracking-wider bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded">
                        Selected Shift
                      </span>
                      <h3 className="text-lg font-black text-slate-900 mt-1">
                        {doctorName}
                      </h3>
                      <p className="text-xs font-semibold text-slate-700 mt-0.5">
                        {formatDateTitle(selectedSchedule.schedule_date)} • {selectedSchedule.formatted_time}
                      </p>
                    </div>

                    <div className="p-3 bg-emerald-50 rounded-2xl border border-emerald-200/70 text-right">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 block">
                        Clinic Timings
                      </span>
                      <span className="text-xs font-black text-emerald-950 font-mono">
                        {selectedSchedule.formatted_time}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Slot Selection */}
                <div>
                  <label className="text-xs font-bold text-slate-800 uppercase tracking-wider block mb-2">
                    Choose an available appointment time
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2">
                    {timeSlots.map((slot) => {
                      const isTimeSelected = selectedTime === slot.value;
                      return (
                        <button
                          key={slot.value}
                          type="button"
                          onClick={() => {
                            setSelectedTime(slot.value);
                            setErrorMessage(null);
                          }}
                          className={`py-2 px-3 rounded-xl text-xs font-mono font-bold transition-all cursor-pointer text-center ${
                            isTimeSelected
                              ? 'bg-emerald-600 text-white shadow-xs ring-2 ring-emerald-200'
                              : 'bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200'
                          }`}
                        >
                          {slot.label}
                        </button>
                      );
                    })}
                  </div>
                  <p className="text-[11px] text-slate-400 mt-2">
                    Select a 30-minute consultation window within Dr. {doctorName.replace(/^Dr\.\s*/i, '')}'s scheduled clinic hours.
                  </p>
                </div>

                {/* Error Banner */}
                {errorMessage && (
                  <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-xs flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                    <span className="font-semibold">{errorMessage}</span>
                  </div>
                )}

                {/* Action Confirmation Button */}
                <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-slate-100">
                  <div className="text-xs text-slate-500">
                    Your appointment ticket will be placed in Dr. {doctorName.replace(/^Dr\.\s*/i, '')}'s date queue.
                  </div>

                  <button
                    type="button"
                    disabled={!selectedTime || bookMutation.isPending}
                    onClick={() => bookMutation.mutate()}
                    className="w-full sm:w-auto px-8 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white font-bold text-xs shadow-md transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    <span>
                      {bookMutation.isPending
                        ? 'Confirming Appointment...'
                        : 'CONFIRM APPOINTMENT'}
                    </span>
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
