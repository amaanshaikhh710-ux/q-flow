import { useState, useEffect, useMemo } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  X,
  Calendar,
  Clock,
  Stethoscope,
  Building2,
  CheckCircle2,
  AlertCircle,
  Lock,
} from 'lucide-react';
import { schedulesApi } from '../../api/schedules';
import { extractErrorMessage } from '../../api/client';
import type { StaffDoctorItem } from '../../api/discovery';

interface StaffDoctorScheduleModalProps {
  isOpen: boolean;
  onClose: () => void;
  hospitalName?: string;
  doctors: StaffDoctorItem[];
  defaultDoctorId?: string;
  defaultDate?: string;
  onSaved?: () => void;
}

export function StaffDoctorScheduleModal({
  isOpen,
  onClose,
  hospitalName,
  doctors,
  defaultDoctorId,
  defaultDate,
  onSaved,
}: StaffDoctorScheduleModalProps) {
  const queryClient = useQueryClient();

  const [doctorId, setDoctorId] = useState<string>(
    defaultDoctorId || (doctors.length > 0 ? doctors[0].id : '')
  );

  const [scheduleDate, setScheduleDate] = useState<string>(() => {
    if (defaultDate) return defaultDate;
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split('T')[0];
  });

  const [startTime, setStartTime] = useState('09:00');
  const [endTime, setEndTime] = useState('13:00');
  const [status, setStatus] = useState<'AVAILABLE' | 'UNAVAILABLE'>('AVAILABLE');
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Sync state when modal opens
  useEffect(() => {
    if (isOpen) {
      setError(null);
      setSuccessMsg(null);
      if (defaultDate) {
        setScheduleDate(defaultDate);
      } else {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        setScheduleDate(tomorrow.toISOString().split('T')[0]);
      }
      if (defaultDoctorId && doctors.some((d) => d.id === defaultDoctorId)) {
        setDoctorId(defaultDoctorId);
      } else if (doctors.length > 0 && (!doctorId || !doctors.some((d) => d.id === doctorId))) {
        setDoctorId(doctors[0].id);
      }
    }
  }, [isOpen, defaultDate, defaultDoctorId, doctors]);

  const selectedDoctor = useMemo(() => {
    return doctors.find((d) => d.id === doctorId) || doctors[0] || null;
  }, [doctors, doctorId]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!selectedDoctor) throw new Error('Please select an existing hospital doctor');
      if (startTime >= endTime) throw new Error('Start time must be strictly earlier than end time');

      return schedulesApi.createSchedule({
        doctor_id: selectedDoctor.id,
        department_id: selectedDoctor.department_id,
        schedule_date: scheduleDate,
        start_time: startTime.length === 5 ? `${startTime}:00` : startTime,
        end_time: endTime.length === 5 ? `${endTime}:00` : endTime,
        status,
      });
    },
    onSuccess: (data) => {
      setSuccessMsg(`OPD Schedule saved for ${data.doctor_name} on ${data.schedule_date} (${data.start_time_formatted} – ${data.end_time_formatted})`);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ['staff-hospital-schedules'] });
      void queryClient.invalidateQueries({ queryKey: ['staff-queues-for-date'] });
      void queryClient.invalidateQueries({ queryKey: ['available-doctors'] });
      void queryClient.invalidateQueries({ queryKey: ['staff-hospital-data'] });
      if (onSaved) onSaved();
      setTimeout(() => {
        onClose();
      }, 700);
    },
    onError: (err) => {
      setError(extractErrorMessage(err));
      setSuccessMsg(null);
    },
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);

    if (!selectedDoctor) {
      setError('Please select a doctor');
      return;
    }
    if (!scheduleDate) {
      setError('Please select a schedule date');
      return;
    }
    if (startTime >= endTime) {
      setError('Start time must be strictly earlier than end time');
      return;
    }
    saveMutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl relative border border-slate-200">
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 p-2 text-slate-400 hover:text-slate-600 rounded-xl transition-colors cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-3.5 mb-6">
          <div className="w-12 h-12 rounded-2xl bg-cyan-50 border border-cyan-200 text-cyan-700 flex items-center justify-center font-bold shrink-0">
            <Calendar className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-black uppercase tracking-wider bg-cyan-100 text-cyan-800 px-2 py-0.5 rounded">
                Hospital OPD Roster
              </span>
              <span className="text-[10px] text-slate-400 font-semibold flex items-center gap-1">
                <Lock className="w-2.5 h-2.5" /> Staff Isolated
              </span>
            </div>
            <h2 className="text-lg font-black text-slate-900 mt-0.5">
              + SCHEDULE DOCTOR OPD
            </h2>
            <p className="text-xs text-slate-500 font-medium">
              Create an official date-specific clinic session for patients to book
            </p>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-xs mb-4 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <span className="font-semibold">{error}</span>
          </div>
        )}

        {/* Success Alert */}
        {successMsg && (
          <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-2xl text-emerald-900 text-xs mb-4 flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <span className="font-semibold">{successMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Hospital (Enforced from Staff credentials) */}
          <div>
            <label className="text-xs font-bold text-slate-700 mb-1 flex items-center justify-between">
              <span>Hospital</span>
              <span className="text-[10px] text-slate-400 font-normal">
                {hospitalName ? 'Assigned Facility' : 'Current Hospital'}
              </span>
            </label>
            <div className="relative">
              <input
                type="text"
                value={hospitalName || 'My Assigned Hospital'}
                disabled
                className="w-full pl-9 pr-3.5 py-2.5 bg-slate-100 border border-slate-200 rounded-xl text-xs font-bold text-slate-700 cursor-not-allowed"
              />
              <Building2 className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            </div>
          </div>

          {/* Doctor Selection (Only existing doctors from staff's hospital) */}
          <div>
            <label className="text-xs font-bold text-slate-700 mb-1 block">
              Doctor
            </label>
            <div className="relative">
              <select
                value={doctorId}
                onChange={(e) => setDoctorId(e.target.value)}
                className="w-full pl-9 pr-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-xs font-bold text-slate-900 focus:outline-hidden focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 transition-all cursor-pointer"
              >
                {doctors.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.name}
                  </option>
                ))}
              </select>
              <Stethoscope className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            </div>
          </div>

          {/* Department (Auto-populated from doctor's department) */}
          <div>
            <label className="text-xs font-bold text-slate-700 mb-1 block">
              Department
            </label>
            <input
              type="text"
              value={selectedDoctor?.department_name || 'General Medicine'}
              disabled
              className="w-full px-3.5 py-2.5 bg-slate-100 border border-slate-200 rounded-xl text-xs font-bold text-slate-700 cursor-not-allowed"
            />
          </div>

          {/* Date Picker */}
          <div>
            <label className="text-xs font-bold text-slate-700 mb-1 block">
              Date
            </label>
            <input
              type="date"
              value={scheduleDate}
              min={new Date().toISOString().split('T')[0]}
              onChange={(e) => setScheduleDate(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-xs font-bold text-slate-900 focus:outline-hidden focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 transition-all cursor-pointer"
            />
          </div>

          {/* Start Time & End Time */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-bold text-slate-700 mb-1 flex items-center gap-1">
                <Clock className="w-3 h-3 text-cyan-600" />
                <span>Start Time</span>
              </label>
              <input
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-xs font-bold text-slate-900 focus:outline-hidden focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 transition-all cursor-pointer"
              />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-700 mb-1 flex items-center gap-1">
                <Clock className="w-3 h-3 text-cyan-600" />
                <span>End Time</span>
              </label>
              <input
                type="time"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-xs font-bold text-slate-900 focus:outline-hidden focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 transition-all cursor-pointer"
              />
            </div>
          </div>

          {/* Availability Status */}
          <div>
            <label className="text-xs font-bold text-slate-700 mb-1 block">
              Status
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setStatus('AVAILABLE')}
                className={`px-3 py-2 rounded-xl border text-xs font-bold transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
                  status === 'AVAILABLE'
                    ? 'border-emerald-600 bg-emerald-50 text-emerald-900 ring-2 ring-emerald-100'
                    : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'
                }`}
              >
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                <span>AVAILABLE</span>
              </button>
              <button
                type="button"
                onClick={() => setStatus('UNAVAILABLE')}
                className={`px-3 py-2 rounded-xl border text-xs font-bold transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
                  status === 'UNAVAILABLE'
                    ? 'border-rose-600 bg-rose-50 text-rose-900 ring-2 ring-rose-100'
                    : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'
                }`}
              >
                <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
                <span>UNAVAILABLE / OFF</span>
              </button>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl border border-slate-300 hover:bg-slate-50 text-slate-700 font-semibold text-xs transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saveMutation.isPending}
              className="px-6 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 active:bg-black text-white font-bold text-xs shadow-md transition-all cursor-pointer disabled:opacity-50 flex items-center gap-2"
            >
              <Calendar className="w-4 h-4 text-cyan-400" />
              <span>{saveMutation.isPending ? 'Saving Record...' : 'SAVE OPD SCHEDULE'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
