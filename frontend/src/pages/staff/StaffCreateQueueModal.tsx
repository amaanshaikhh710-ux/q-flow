import { useState, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { X, CalendarDays, Plus, Building2, Lock } from 'lucide-react';
import { queuesApi } from '../../api/queues';
import { extractErrorMessage } from '../../api/client';
import type { StaffDoctorItem } from '../../api/discovery';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  hospitalName?: string;
  doctors: StaffDoctorItem[];
  defaultDate?: string;
  onCreated?: () => void;
}

export function StaffCreateQueueModal({
  isOpen,
  onClose,
  hospitalName,
  doctors,
  defaultDate,
  onCreated,
}: Props) {
  const [doctorId, setDoctorId] = useState(doctors.length > 0 ? doctors[0].id : '');
  const [scheduleDate, setScheduleDate] = useState(() => {
    if (defaultDate) return defaultDate;
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split('T')[0];
  });
  const [startTime, setStartTime] = useState('09:00');
  const [endTime, setEndTime] = useState('13:00');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setError(null);
      if (defaultDate) setScheduleDate(defaultDate);
      if (doctors.length > 0 && (!doctorId || !doctors.some((d) => d.id === doctorId))) {
        setDoctorId(doctors[0].id);
      }
    }
  }, [isOpen, defaultDate, doctors, doctorId]);

  const mutation = useMutation({
    mutationFn: async () => {
      return queuesApi.createQueue({
        doctor_id: doctorId,
        queue_date: scheduleDate,
        start_time: startTime + ':00',
        end_time: endTime + ':00',
      });
    },
    onSuccess: () => {
      setError(null);
      if (onCreated) onCreated();
      onClose();
    },
    onError: (err: any) => {
      setError(extractErrorMessage(err));
    },
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 sm:p-8 shadow-2xl relative border border-slate-200">
        <button onClick={onClose} className="absolute right-4 top-4 p-2 text-slate-400 hover:text-slate-600 rounded-lg">
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-700 flex items-center justify-center font-bold">
            <CalendarDays className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">+ Create OPD Queue</h3>
            <p className="text-xs text-slate-500">Create a date-specific OPD shift and queue for a doctor</p>
          </div>
        </div>

        {error && <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs mb-3">{error}</div>}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            setError(null);
            if (!doctorId) return setError('Please select a doctor');
            if (startTime >= endTime) return setError('Start time must be before end time');
            mutation.mutate();
          }}
          className="space-y-3"
        >
          {/* Hospital: automatically determined from staff credentials */}
          <div>
            <label className="text-xs font-bold text-slate-700 mb-1 flex items-center justify-between">
              <span>Hospital</span>
              <span className="text-[10px] text-slate-400 font-normal flex items-center gap-1">
                <Lock className="w-2.5 h-2.5" /> Staff Assigned
              </span>
            </label>
            <div className="relative">
              <input
                type="text"
                value={hospitalName || 'My Assigned Hospital'}
                disabled
                className="w-full pl-9 pr-3.5 py-2.5 bg-slate-100 border border-slate-300 rounded-xl text-sm font-semibold text-slate-700 cursor-not-allowed"
              />
              <Building2 className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            </div>
            <p className="text-[10px] text-slate-400 mt-1">
              Automatically determined from staff account ({hospitalName || 'Your Hospital'})
            </p>
          </div>

          <div>
            <label className="text-xs font-bold text-slate-700 mb-1 block">Doctor</label>
            <select
              value={doctorId}
              onChange={(e) => setDoctorId(e.target.value)}
              className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm"
            >
              {doctors.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} — {d.department_name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-bold text-slate-700 mb-1 block">Date</label>
            <input type="date" value={scheduleDate} onChange={(e) => setScheduleDate(e.target.value)} min={new Date().toISOString().split('T')[0]} className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-bold text-slate-700 mb-1 block">Start Time</label>
              <input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm" />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-700 mb-1 block">End Time</label>
              <input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm" />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-xl border">Cancel</button>
            <button type="submit" className="px-4 py-2 bg-emerald-600 text-white rounded-xl" disabled={mutation.isPending}>
              <Plus className="inline-block mr-2" /> {mutation.isPending ? 'Creating...' : 'Create Queue'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
