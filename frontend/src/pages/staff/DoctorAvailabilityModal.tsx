import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  X,
  Calendar,
  CheckCircle2,
  AlertCircle,
  Clock,
  Plus,
  CalendarDays,
} from 'lucide-react';
import { schedulesApi } from '../../api/schedules';
import { discoveryApi } from '../../api/discovery';
import { extractErrorMessage } from '../../api/client';
import type { DoctorScheduleResponse } from '../../types/api';

interface DoctorAvailabilityModalProps {
  isOpen: boolean;
  onClose: () => void;
  doctorId: string;
  doctorName: string;
  departmentId?: string;
}

export function DoctorAvailabilityModal({
  isOpen,
  onClose,
  doctorId,
  doctorName,
  departmentId,
}: DoctorAvailabilityModalProps) {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'calendar' | 'create' | 'batch'>('calendar');
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Single date schedule state
  const [scheduleDate, setScheduleDate] = useState(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split('T')[0];
  });
  const [startTime, setStartTime] = useState('09:00');
  const [endTime, setEndTime] = useState('13:00');
  const [status, setStatus] = useState<'AVAILABLE' | 'UNAVAILABLE'>('AVAILABLE');

  // Batch weekly schedule state
  const [batchStartDate, setBatchStartDate] = useState(() => {
    const today = new Date();
    return today.toISOString().split('T')[0];
  });
  const [batchEndDate, setBatchEndDate] = useState(() => {
    const nextWeek = new Date();
    nextWeek.setDate(nextWeek.getDate() + 6);
    return nextWeek.toISOString().split('T')[0];
  });

  // Query 1: Existing schedules from /api/v1/schedules
  const {
    data: schedules = [],
    isLoading: isSchedulesLoading,
    refetch: refetchSchedules,
  } = useQuery({
    queryKey: ['doctor-schedules', doctorId],
    queryFn: () => schedulesApi.getSchedules({ doctor_id: doctorId }),
    enabled: isOpen && Boolean(doctorId),
  });

  // Query 2: Availability list fallback
  const {
    data: _availabilityData,
    isLoading: isAvailLoading,
    refetch: refetchAvail,
  } = useQuery({
    queryKey: ['doctor-availability', doctorId],
    queryFn: () => discoveryApi.getDoctorAvailability(doctorId, 14),
    enabled: isOpen && Boolean(doctorId),
  });

  // Mutation: Create single date schedule
  const createScheduleMutation = useMutation({
    mutationFn: async () => {
      return schedulesApi.createSchedule({
        doctor_id: doctorId,
        department_id: departmentId || '',
        schedule_date: scheduleDate,
        start_time: startTime + ':00',
        end_time: endTime + ':00',
        status,
      });
    },
    onSuccess: (data) => {
      setActionError(null);
      setActionSuccess(`Schedule saved for ${data.schedule_date} (${data.start_time_formatted} – ${data.end_time_formatted})`);
      void queryClient.invalidateQueries({ queryKey: ['doctor-schedules', doctorId] });
      void queryClient.invalidateQueries({ queryKey: ['doctor-availability', doctorId] });
      refetchSchedules();
      refetchAvail();
      setActiveTab('calendar');
    },
    onError: (err) => {
      setActionError(extractErrorMessage(err));
      setActionSuccess(null);
    },
  });

  // Mutation: Batch weekly schedule
  const batchScheduleMutation = useMutation({
    mutationFn: async () => {
      const start = new Date(batchStartDate);
      const end = new Date(batchEndDate);
      const items = [];
      const curr = new Date(start);
      while (curr <= end) {
        items.push({
          schedule_date: curr.toISOString().split('T')[0],
          start_time: startTime + ':00',
          end_time: endTime + ':00',
          status: 'AVAILABLE',
        });
        curr.setDate(curr.getDate() + 1);
      }
      return schedulesApi.createBatchSchedule({
        doctor_id: doctorId,
        schedules: items,
      });
    },
    onSuccess: (data) => {
      setActionError(null);
      setActionSuccess(`Successfully created ${data.length} daily schedules across ${batchStartDate} to ${batchEndDate}!`);
      void queryClient.invalidateQueries({ queryKey: ['doctor-schedules', doctorId] });
      void queryClient.invalidateQueries({ queryKey: ['doctor-availability', doctorId] });
      refetchSchedules();
      refetchAvail();
      setActiveTab('calendar');
    },
    onError: (err) => {
      setActionError(extractErrorMessage(err));
      setActionSuccess(null);
    },
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-3xl max-w-2xl w-full p-6 sm:p-8 shadow-2xl relative border border-slate-200">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 p-2 text-slate-400 hover:text-slate-600 rounded-lg transition-colors cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-700 flex items-center justify-center font-bold">
            <Calendar className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-slate-900">Doctor Scheduling & Availability</h3>
            <p className="text-xs text-slate-500 font-medium">
              Manage OPD shifts for <span className="font-bold text-slate-800">{doctorName}</span>
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex gap-2 p-1 bg-slate-100 rounded-xl mb-6 text-xs font-bold">
          <button
            type="button"
            onClick={() => setActiveTab('calendar')}
            className={`flex-1 py-2 rounded-lg transition-all cursor-pointer ${
              activeTab === 'calendar' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Calendar & Shifts
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('create')}
            className={`flex-1 py-2 rounded-lg transition-all cursor-pointer ${
              activeTab === 'create' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Schedule Date
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('batch')}
            className={`flex-1 py-2 rounded-lg transition-all cursor-pointer ${
              activeTab === 'batch' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Weekly Batch Schedule
          </button>
        </div>

        {actionError && (
          <div className="mb-4 p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{actionError}</span>
          </div>
        )}

        {actionSuccess && (
          <div className="mb-4 p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-emerald-600" />
            <span>{actionSuccess}</span>
          </div>
        )}

        {/* TAB 1: Calendar View of Shifts */}
        {activeTab === 'calendar' && (
          <div className="space-y-4">
            <div className="text-xs text-slate-500 bg-slate-50 border border-slate-200 p-3 rounded-xl flex items-center justify-between">
              <span>
                Scheduled shifts automatically provision OPD queues. Patients can only book dates with active shifts.
              </span>
              <button
                type="button"
                onClick={() => setActiveTab('create')}
                className="inline-flex items-center gap-1 px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold text-xs shadow-xs cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Shift</span>
              </button>
            </div>

            {isSchedulesLoading && isAvailLoading ? (
              <div className="p-12 text-center">
                <div className="w-8 h-8 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                <p className="text-xs text-slate-500">Loading schedules...</p>
              </div>
            ) : (
              <div className="space-y-2.5 max-h-96 overflow-y-auto pr-1">
                {/* Display official DoctorSchedule records first if available */}
                {schedules.length > 0 ? (
                  schedules.map((sched: DoctorScheduleResponse) => {
                    const parsedDate = new Date(sched.schedule_date + 'T00:00:00');
                    const formattedDate = parsedDate.toLocaleDateString('en-US', {
                      weekday: 'short',
                      day: 'numeric',
                      month: 'short',
                      year: 'numeric',
                    });

                    return (
                      <div
                        key={sched.id}
                        className={`p-3.5 rounded-2xl border transition-all flex items-center justify-between ${
                          sched.status === 'AVAILABLE'
                            ? 'bg-emerald-50/50 border-emerald-200'
                            : 'bg-rose-50/50 border-rose-200'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                              sched.status === 'AVAILABLE'
                                ? 'bg-emerald-100 text-emerald-700'
                                : 'bg-rose-100 text-rose-700'
                            }`}
                          >
                            <CalendarDays className="w-5 h-5" />
                          </div>
                          <div>
                            <span className="text-xs font-bold text-slate-900 block">
                              {formattedDate}
                            </span>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className="text-xs font-semibold text-emerald-800 flex items-center gap-1">
                                <Clock className="w-3.5 h-3.5 text-emerald-600" />
                                <span>{sched.start_time_formatted} – {sched.end_time_formatted}</span>
                              </span>
                              <span className="text-[10px] px-2 py-0.5 rounded bg-white text-slate-600 border border-slate-200">
                                {sched.appointments_count || 0} booked
                              </span>
                            </div>
                          </div>
                        </div>

                        <span
                          className={`text-[11px] font-bold px-2.5 py-1 rounded-lg ${
                            sched.status === 'AVAILABLE'
                              ? 'bg-emerald-100 text-emerald-800'
                              : 'bg-rose-100 text-rose-800'
                          }`}
                        >
                          {sched.status}
                        </span>
                      </div>
                    );
                  })
                ) : (
                  <div className="text-center py-8 text-xs text-slate-500">
                    No custom shifts scheduled yet. Use "Schedule Date" or "Weekly Batch Schedule" to set clinic hours.
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: Schedule Specific Date */}
        {activeTab === 'create' && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              createScheduleMutation.mutate();
            }}
            className="space-y-4"
          >
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Consultation Date <span className="text-rose-500">*</span>
              </label>
              <input
                type="date"
                required
                min={new Date().toISOString().split('T')[0]}
                value={scheduleDate}
                onChange={(e) => setScheduleDate(e.target.value)}
                className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Start Time
                </label>
                <input
                  type="time"
                  required
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  End Time
                </label>
                <input
                  type="time"
                  required
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Availability Status
              </label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as 'AVAILABLE' | 'UNAVAILABLE')}
                className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="AVAILABLE">AVAILABLE (Patients can book)</option>
                <option value="UNAVAILABLE">UNAVAILABLE (Off duty / leave)</option>
              </select>
            </div>

            <div className="pt-4 flex justify-end gap-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setActiveTab('calendar')}
                className="px-4 py-2.5 border border-slate-300 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-100 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createScheduleMutation.isPending}
                className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-sm transition-all flex items-center gap-2 disabled:opacity-50 cursor-pointer"
              >
                {createScheduleMutation.isPending ? 'Saving Shift...' : 'Save Shift Schedule'}
              </button>
            </div>
          </form>
        )}

        {/* TAB 3: Weekly Batch Schedule */}
        {activeTab === 'batch' && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              batchScheduleMutation.mutate();
            }}
            className="space-y-4"
          >
            <div className="p-3.5 bg-blue-50 border border-blue-100 rounded-2xl text-xs text-blue-900">
              Quickly schedule a recurring or daily shift for <strong>{doctorName}</strong> across an entire week or custom date range.
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Start Date
                </label>
                <input
                  type="date"
                  required
                  min={new Date().toISOString().split('T')[0]}
                  value={batchStartDate}
                  onChange={(e) => setBatchStartDate(e.target.value)}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  End Date
                </label>
                <input
                  type="date"
                  required
                  min={batchStartDate}
                  value={batchEndDate}
                  onChange={(e) => setBatchEndDate(e.target.value)}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Shift Start Time
                </label>
                <input
                  type="time"
                  required
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Shift End Time
                </label>
                <input
                  type="time"
                  required
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>

            <div className="pt-4 flex justify-end gap-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setActiveTab('calendar')}
                className="px-4 py-2.5 border border-slate-300 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-100 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={batchScheduleMutation.isPending}
                className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-sm transition-all flex items-center gap-2 disabled:opacity-50 cursor-pointer"
              >
                {batchScheduleMutation.isPending ? 'Provisioning Week...' : 'Apply Weekly Schedule'}
              </button>
            </div>
          </form>
        )}

        <div className="mt-6 pt-4 border-t border-slate-100 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-bold transition-colors cursor-pointer"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
