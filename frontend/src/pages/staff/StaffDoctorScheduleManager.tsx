import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Calendar,
  CheckCircle2,
  AlertCircle,
  Plus,
  Trash2,
  CalendarDays,
  Users,
} from 'lucide-react';
import { schedulesApi } from '../../api/schedules';
import { extractErrorMessage } from '../../api/client';
import { formatDoctorName } from '../../utils/format';
import type { StaffHospitalDetails } from '../../api/discovery';

interface StaffDoctorScheduleManagerProps {
  hospitalData?: StaffHospitalDetails;
  onOpenScheduleModal?: () => void;
  onScheduleUpdated?: () => void;
}

export function StaffDoctorScheduleManager({
  hospitalData,
  onOpenScheduleModal,
  onScheduleUpdated,
}: StaffDoctorScheduleManagerProps) {
  const queryClient = useQueryClient();
  const doctors = hospitalData?.doctors || [];
  const hospital = hospitalData?.hospital;

  const [subTab, setSubTab] = useState<'single' | 'weekly' | 'list'>('single');
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>(
    doctors.length > 0 ? doctors[0].id : ''
  );

  // Single date form state
  const [singleDate, setSingleDate] = useState<string>(() => {
    const today = new Date();
    return today.toISOString().split('T')[0];
  });
  const [singleStartTime, setSingleStartTime] = useState('09:00');
  const [singleEndTime, setSingleEndTime] = useState('13:00');
  const [singleStatus, setSingleStatus] = useState<'AVAILABLE' | 'UNAVAILABLE'>('AVAILABLE');

  // Weekly planner state: next 7 days
  const weekDays = useMemo(() => {
    const days = [];
    const now = new Date();
    for (let i = 0; i < 7; i++) {
      const d = new Date(now);
      d.setDate(now.getDate() + i);
      const iso = d.toISOString().split('T')[0];
      const weekday = d.toLocaleDateString('en-US', { weekday: 'long' });
      const formatted = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      days.push({ iso, weekday, formatted });
    }
    return days;
  }, []);

  const [weeklyShifts, setWeeklyShifts] = useState<
    Record<string, { status: 'AVAILABLE' | 'UNAVAILABLE'; startTime: string; endTime: string }>
  >(() => {
    const initial: Record<
      string,
      { status: 'AVAILABLE' | 'UNAVAILABLE'; startTime: string; endTime: string }
    > = {};
    const now = new Date();
    for (let i = 0; i < 7; i++) {
      const d = new Date(now);
      d.setDate(now.getDate() + i);
      const iso = d.toISOString().split('T')[0];
      initial[iso] = {
        status: i === 6 ? 'UNAVAILABLE' : 'AVAILABLE',
        startTime: '09:00',
        endTime: '13:00',
      };
    }
    return initial;
  });

  const [filterDoctorId, setFilterDoctorId] = useState<string>('ALL');
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(
    null
  );

  const selectedDoctor = useMemo(() => {
    return doctors.find((d) => d.id === selectedDoctorId) || doctors[0] || null;
  }, [doctors, selectedDoctorId]);

  // Query hospital schedules
  const {
    data: schedules = [],
    isLoading: isSchedulesLoading,
    refetch: refetchSchedules,
  } = useQuery({
    queryKey: ['staff-hospital-schedules', hospital?.id],
    queryFn: () => schedulesApi.getSchedules(),
    enabled: Boolean(hospital?.id),
  });

  // Filtered schedules for list view
  const filteredSchedules = useMemo(() => {
    if (filterDoctorId === 'ALL') return schedules;
    return schedules.filter((s) => s.doctor_id === filterDoctorId);
  }, [schedules, filterDoctorId]);

  // Mutation: Single schedule
  const createSingleMutation = useMutation({
    mutationFn: async () => {
      if (!selectedDoctor) throw new Error('Please select a doctor');
      return schedulesApi.createSchedule({
        doctor_id: selectedDoctor.id,
        department_id: selectedDoctor.department_id,
        schedule_date: singleDate,
        start_time: `${singleStartTime}:00`,
        end_time: `${singleEndTime}:00`,
        status: singleStatus,
      });
    },
    onSuccess: (data) => {
      setStatusMessage({
        type: 'success',
        text: `Schedule successfully saved for ${data.doctor_name} on ${data.schedule_date} (${data.start_time_formatted} – ${data.end_time_formatted}) as ${data.status}!`,
      });
      void queryClient.invalidateQueries({ queryKey: ['staff-hospital-schedules'] });
      void queryClient.invalidateQueries({ queryKey: ['available-doctors'] });
      refetchSchedules();
      onScheduleUpdated?.();
    },
    onError: (err) => {
      setStatusMessage({
        type: 'error',
        text: extractErrorMessage(err),
      });
    },
  });

  // Mutation: Batch weekly schedule
  const createBatchMutation = useMutation({
    mutationFn: async () => {
      if (!selectedDoctor) throw new Error('Please select a doctor');
      const items = Object.entries(weeklyShifts).map(([dateStr, shift]) => ({
        schedule_date: dateStr,
        start_time: `${shift.startTime}:00`,
        end_time: `${shift.endTime}:00`,
        status: shift.status,
      }));
      return schedulesApi.createBatchSchedule({
        doctor_id: selectedDoctor.id,
        schedules: items,
      });
    },
    onSuccess: (data) => {
      setStatusMessage({
        type: 'success',
        text: `Weekly schedule successfully saved for ${selectedDoctor?.name || 'Doctor'} (${data.length} dates configured)!`,
      });
      void queryClient.invalidateQueries({ queryKey: ['staff-hospital-schedules'] });
      void queryClient.invalidateQueries({ queryKey: ['available-doctors'] });
      refetchSchedules();
      onScheduleUpdated?.();
    },
    onError: (err) => {
      setStatusMessage({
        type: 'error',
        text: extractErrorMessage(err),
      });
    },
  });

  // Mutation: Delete schedule
  const deleteMutation = useMutation({
    mutationFn: async (scheduleId: string) => {
      return schedulesApi.deleteSchedule(scheduleId);
    },
    onSuccess: () => {
      setStatusMessage({
        type: 'success',
        text: 'Schedule shift successfully deleted.',
      });
      void queryClient.invalidateQueries({ queryKey: ['staff-hospital-schedules'] });
      void queryClient.invalidateQueries({ queryKey: ['available-doctors'] });
      refetchSchedules();
      onScheduleUpdated?.();
    },
    onError: (err) => {
      setStatusMessage({
        type: 'error',
        text: extractErrorMessage(err),
      });
    },
  });

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-2xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-cyan-600 bg-cyan-50 px-2.5 py-0.5 rounded-full border border-cyan-200">
                Staff OPD Rostering
              </span>
              <span className="text-xs font-semibold text-slate-500">
                Hospital: <strong className="text-slate-900">{hospital?.name || 'Assigned Facility'}</strong>
              </span>
            </div>
            <h2 className="text-xl font-black text-slate-900 mt-1.5 tracking-tight">
              Doctor Scheduling & Availability Management
            </h2>
            <p className="text-xs text-slate-500 mt-1 max-w-2xl">
              Configure date-specific shifts and weekly hours for doctors at{' '}
              <strong>{hospital?.name}</strong>. Doctors without an active schedule on a specific date
              will not be available for patient bookings.
            </p>
          </div>

          {/* Action & Sub-tabs switch */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => {
                if (onOpenScheduleModal) {
                  onOpenScheduleModal();
                } else {
                  setSubTab('single');
                }
              }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs shadow-md transition-all cursor-pointer shrink-0"
            >
              <Plus className="w-4 h-4" />
              <span>+ SCHEDULE DOCTOR OPD</span>
            </button>

            <div className="flex items-center gap-1.5 p-1 bg-slate-100 rounded-2xl border border-slate-200 shrink-0">
            <button
              type="button"
              onClick={() => {
                setSubTab('single');
                setStatusMessage(null);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                subTab === 'single'
                  ? 'bg-white text-slate-900 shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Single Date Shift
            </button>
            <button
              type="button"
              onClick={() => {
                setSubTab('weekly');
                setStatusMessage(null);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                subTab === 'weekly'
                  ? 'bg-white text-slate-900 shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Weekly Planning
            </button>
            <button
              type="button"
              onClick={() => {
                setSubTab('list');
                setStatusMessage(null);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                subTab === 'list'
                  ? 'bg-white text-slate-900 shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Active Schedules ({schedules.length})
            </button>
          </div>
        </div>
      </div>

        {/* Feedback Alerts */}
        {statusMessage && (
          <div
            className={`mt-4 p-3.5 rounded-2xl border text-xs flex items-start gap-2.5 ${
              statusMessage.type === 'success'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                : 'bg-rose-50 border-rose-200 text-rose-900'
            }`}
          >
            {statusMessage.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            )}
            <p className="flex-1 font-medium">{statusMessage.text}</p>
          </div>
        )}
      </div>

      {/* SUB-TAB 1: Single Date Shift */}
      {subTab === 'single' && (
        <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-2xs space-y-6">
          <div className="border-b border-slate-100 pb-4">
            <h3 className="text-base font-bold text-slate-900">Schedule Single Doctor Shift</h3>
            <p className="text-xs text-slate-500">
              Assign consulting hours or mark off-duty for a doctor on a specific date
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Doctor Selection */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                Select Hospital Doctor
              </label>
              <select
                value={selectedDoctorId}
                onChange={(e) => setSelectedDoctorId(e.target.value)}
                className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-xs font-semibold text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 transition-all cursor-pointer"
              >
                {doctors.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {formatDoctorName(doc.name)} — {doc.department_name}
                  </option>
                ))}
              </select>
              {selectedDoctor && (
                <div className="mt-2 p-3 rounded-xl bg-slate-50 border border-slate-200/70 text-xs text-slate-600 flex items-center justify-between">
                  <span>
                    Department: <strong className="text-slate-900">{selectedDoctor.department_name}</strong>
                  </span>
                  <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                    Assigned: {hospital?.name}
                  </span>
                </div>
              )}
            </div>

            {/* Date Selection */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                Consultation Date
              </label>
              <input
                type="date"
                value={singleDate}
                min={new Date().toISOString().split('T')[0]}
                onChange={(e) => setSingleDate(e.target.value)}
                className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-xs font-semibold text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 transition-all cursor-pointer"
              />
            </div>

            {/* Shift Timings */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                  Start Time
                </label>
                <input
                  type="time"
                  value={singleStartTime}
                  onChange={(e) => setSingleStartTime(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-xs font-semibold text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 transition-all cursor-pointer"
                />
              </div>
              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                  End Time
                </label>
                <input
                  type="time"
                  value={singleEndTime}
                  onChange={(e) => setSingleEndTime(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-xs font-semibold text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 transition-all cursor-pointer"
                />
              </div>
            </div>

            {/* Availability Status */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                Availability Status
              </label>
              <div className="grid grid-cols-2 gap-2.5">
                <button
                  type="button"
                  onClick={() => setSingleStatus('AVAILABLE')}
                  className={`px-3 py-2.5 rounded-xl border text-xs font-bold transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
                    singleStatus === 'AVAILABLE'
                      ? 'border-emerald-600 bg-emerald-50 text-emerald-900 ring-2 ring-emerald-100'
                      : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>AVAILABLE</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSingleStatus('UNAVAILABLE')}
                  className={`px-3 py-2.5 rounded-xl border text-xs font-bold transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
                    singleStatus === 'UNAVAILABLE'
                      ? 'border-rose-600 bg-rose-50 text-rose-900 ring-2 ring-rose-100'
                      : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
                  <span>UNAVAILABLE / OFF</span>
                </button>
              </div>
            </div>
          </div>

          <div className="border-t border-slate-100 pt-4 flex justify-end">
            <button
              type="button"
              disabled={createSingleMutation.isPending || !selectedDoctor}
              onClick={() => createSingleMutation.mutate()}
              className="px-6 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 active:bg-black text-white font-bold text-xs shadow-xs transition-all cursor-pointer disabled:opacity-50 flex items-center gap-2"
            >
              <Calendar className="w-4 h-4 text-cyan-400" />
              <span>{createSingleMutation.isPending ? 'Saving Schedule...' : 'SAVE OPD SCHEDULE'}</span>
            </button>
          </div>
        </div>
      )}

      {/* SUB-TAB 2: Weekly Planning */}
      {subTab === 'weekly' && (
        <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-2xs space-y-6">
          <div className="border-b border-slate-100 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-slate-900">Multi-Day Weekly Doctor Planner</h3>
              <p className="text-xs text-slate-500">
                Plan shift hours or mark days off across the upcoming 7 days for a doctor
              </p>
            </div>

            <div className="flex items-center gap-2">
              <label className="text-xs font-bold text-slate-700">Doctor:</label>
              <select
                value={selectedDoctorId}
                onChange={(e) => setSelectedDoctorId(e.target.value)}
                className="rounded-xl border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-900 bg-slate-50 focus:bg-white transition-all cursor-pointer"
              >
                {doctors.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.name} ({doc.department_name})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* 7-Day Grid */}
          <div className="space-y-3">
            {weekDays.map((day) => {
              const shift = weeklyShifts[day.iso] || {
                status: 'AVAILABLE',
                startTime: '09:00',
                endTime: '13:00',
              };
              const isAvail = shift.status === 'AVAILABLE';

              return (
                <div
                  key={day.iso}
                  className={`p-4 rounded-2xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                    isAvail
                      ? 'bg-slate-50/70 border-slate-200/80 hover:border-cyan-300'
                      : 'bg-rose-50/30 border-rose-200/60'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-10 h-10 rounded-xl flex flex-col items-center justify-center font-bold text-xs ${
                        isAvail ? 'bg-cyan-50 text-cyan-800' : 'bg-rose-100 text-rose-700'
                      }`}
                    >
                      <span className="text-[10px] leading-none uppercase">{day.weekday.slice(0, 3)}</span>
                      <span className="text-sm leading-none mt-0.5">{day.formatted.split(' ')[1]}</span>
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-slate-900">{day.weekday}</h4>
                      <p className="text-[11px] text-slate-500">{day.formatted} ({day.iso})</p>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-3">
                    {/* Status Toggle */}
                    <div className="inline-flex rounded-xl p-0.5 bg-slate-200/70 text-xs font-bold">
                      <button
                        type="button"
                        onClick={() =>
                          setWeeklyShifts((prev) => ({
                            ...prev,
                            [day.iso]: { ...shift, status: 'AVAILABLE' },
                          }))
                        }
                        className={`px-3 py-1 rounded-lg text-xs transition-all cursor-pointer ${
                          isAvail ? 'bg-white text-emerald-800 shadow-2xs' : 'text-slate-600'
                        }`}
                      >
                        AVAILABLE
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setWeeklyShifts((prev) => ({
                            ...prev,
                            [day.iso]: { ...shift, status: 'UNAVAILABLE' },
                          }))
                        }
                        className={`px-3 py-1 rounded-lg text-xs transition-all cursor-pointer ${
                          !isAvail ? 'bg-rose-600 text-white shadow-2xs' : 'text-slate-600'
                        }`}
                      >
                        OFF
                      </button>
                    </div>

                    {/* Time Inputs */}
                    {isAvail ? (
                      <div className="flex items-center gap-2">
                        <input
                          type="time"
                          value={shift.startTime}
                          onChange={(e) =>
                            setWeeklyShifts((prev) => ({
                              ...prev,
                              [day.iso]: { ...shift, startTime: e.target.value },
                            }))
                          }
                          className="rounded-lg border border-slate-300 px-2 py-1 text-xs font-mono font-bold bg-white text-slate-900"
                        />
                        <span className="text-slate-400 text-xs">to</span>
                        <input
                          type="time"
                          value={shift.endTime}
                          onChange={(e) =>
                            setWeeklyShifts((prev) => ({
                              ...prev,
                              [day.iso]: { ...shift, endTime: e.target.value },
                            }))
                          }
                          className="rounded-lg border border-slate-300 px-2 py-1 text-xs font-mono font-bold bg-white text-slate-900"
                        />
                      </div>
                    ) : (
                      <span className="text-xs font-bold text-rose-600 italic px-4">
                        Doctor is Off-Duty (No queue will be scheduled)
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="border-t border-slate-100 pt-4 flex justify-end">
            <button
              type="button"
              disabled={createBatchMutation.isPending || !selectedDoctor}
              onClick={() => createBatchMutation.mutate()}
              className="px-6 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 active:bg-black text-white font-bold text-xs shadow-xs transition-all cursor-pointer disabled:opacity-50 flex items-center gap-2"
            >
              <CalendarDays className="w-4 h-4 text-cyan-400" />
              <span>{createBatchMutation.isPending ? 'Saving Weekly Plan...' : 'Save 7-Day Weekly Schedule'}</span>
            </button>
          </div>
        </div>
      )}

      {/* SUB-TAB 3: Active Schedules List */}
      {subTab === 'list' && (
        <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-2xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900">Hospital Doctor Schedules</h3>
              <p className="text-xs text-slate-500">
                All saved date-specific shift records configured for {hospital?.name || 'this hospital'}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <label className="text-xs font-bold text-slate-600">Filter:</label>
              <select
                value={filterDoctorId}
                onChange={(e) => setFilterDoctorId(e.target.value)}
                className="rounded-xl border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-900 bg-slate-50 focus:bg-white cursor-pointer"
              >
                <option value="ALL">All Doctors ({doctors.length})</option>
                {doctors.map((d) => (
                  <option key={d.id} value={d.id}>
                    {formatDoctorName(d.name)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {isSchedulesLoading ? (
            <div className="py-12 text-center text-xs text-slate-400">Loading schedules...</div>
          ) : filteredSchedules.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                    <th className="py-3 px-3">Date</th>
                    <th className="py-3 px-3">Doctor</th>
                    <th className="py-3 px-3">Department</th>
                    <th className="py-3 px-3">Shift Hours</th>
                    <th className="py-3 px-3">Status</th>
                    <th className="py-3 px-3 text-center">Booked</th>
                    <th className="py-3 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                  {filteredSchedules.map((s) => {
                    const isAvailable = s.status === 'AVAILABLE';
                    return (
                      <tr key={s.id} className="hover:bg-slate-50/70 transition-colors">
                        <td className="py-3 px-3 font-semibold text-slate-900">
                          {s.schedule_date}
                        </td>
                        <td className="py-3 px-3">
                          <span className="font-bold text-slate-900 block">{formatDoctorName(s.doctor_name)}</span>
                        </td>
                        <td className="py-3 px-3 text-slate-600">{s.department_name}</td>
                        <td className="py-3 px-3 font-mono font-bold text-slate-900">
                          {s.start_time_formatted} – {s.end_time_formatted}
                        </td>
                        <td className="py-3 px-3">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-extrabold uppercase ${
                              isAvailable
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-rose-100 text-rose-800'
                            }`}
                          >
                            {s.status}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-center">
                          <span className="inline-flex items-center gap-1 font-bold text-slate-700 bg-slate-100 px-2 py-0.5 rounded-md">
                            <Users className="w-3 h-3 text-slate-500" />
                            <span>{s.appointments_count}</span>
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right">
                          <button
                            type="button"
                            onClick={() => deleteMutation.mutate(s.id)}
                            disabled={deleteMutation.isPending}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                            title="Delete this schedule"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-12 text-center text-xs text-slate-400">
              No schedules created yet. Use "Single Date Shift" or "Weekly Planning" above to configure doctor availability.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
