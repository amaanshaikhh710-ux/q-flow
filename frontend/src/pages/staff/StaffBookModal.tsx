import { useState, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  X,
  UserPlus,
  Phone,
  User,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import { queuesApi } from '../../api/queues';
import { extractErrorMessage } from '../../api/client';
import { formatDoctorName } from '../../utils/format';
import type { PriorityClass, QueueJoinResponse } from '../../types/api';

interface QueueOption {
  queue_id: string;
  queue_name: string;
  doctor_name: string;
  total_waiting: number;
}

interface StaffBookModalProps {
  isOpen: boolean;
  onClose: () => void;
  queues: QueueOption[];
  defaultQueueId?: string;
  defaultDate?: string;
  onSuccess?: (response: QueueJoinResponse) => void;
}

export function StaffBookModal({
  isOpen,
  onClose,
  queues,
  defaultQueueId,
  defaultDate,
  onSuccess,
}: StaffBookModalProps) {
  const [selectedQueueId, setSelectedQueueId] = useState<string>(
    defaultQueueId || (queues.length > 0 ? queues[0].queue_id : '')
  );
  const [patientName, setPatientName] = useState('');
  const [patientPhone, setPatientPhone] = useState('');
  const [bookingSource, setBookingSource] = useState<'WALK_IN' | 'PHONE' | 'STAFF'>('WALK_IN');
  const [priorityClass, setPriorityClass] = useState<PriorityClass>('NORMAL');
  const [appointmentDate, setAppointmentDate] = useState<string>(
    defaultDate || new Date().toISOString().split('T')[0]
  );
  const [appointmentTime, setAppointmentTime] = useState<string>('');
  const [notes, setNotes] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successResponse, setSuccessResponse] = useState<QueueJoinResponse | null>(null);

  useEffect(() => {
    if (isOpen) {
      if (defaultQueueId) setSelectedQueueId(defaultQueueId);
      if (defaultDate) setAppointmentDate(defaultDate);
      setErrorMessage(null);
      setSuccessResponse(null);
    }
  }, [isOpen, defaultQueueId, defaultDate]);

  const bookMutation = useMutation({
    mutationFn: async () => {
      return queuesApi.staffBook(selectedQueueId, {
        patient_name: patientName.trim(),
        patient_phone: patientPhone.trim() || undefined,
        booking_source: bookingSource,
        priority_class: priorityClass,
        appointment_date: appointmentDate || undefined,
        appointment_time: appointmentTime || undefined,
        notes: notes.trim() || undefined,
      });
    },
    onSuccess: (data) => {
      setSuccessResponse(data);
      if (onSuccess) {
        onSuccess(data);
      }
    },
    onError: (err) => {
      setErrorMessage(extractErrorMessage(err));
    },
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    if (!selectedQueueId) {
      setErrorMessage('Please select an active queue.');
      return;
    }
    if (!patientName.trim()) {
      setErrorMessage('Patient name is required.');
      return;
    }
    bookMutation.mutate();
  };

  const handleResetAndBookAnother = () => {
    setPatientName('');
    setPatientPhone('');
    setNotes('');
    setSuccessResponse(null);
    setErrorMessage(null);
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 sm:p-8 shadow-2xl relative border border-slate-200">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 p-2 text-slate-400 hover:text-slate-600 rounded-lg transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {successResponse ? (
          <div className="text-center py-4">
            <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-1">Appointment Booked!</h3>
            <p className="text-sm text-slate-500 mb-6">
              Patient has been added to the queue sequence.
            </p>

            {/* Token Highlight Box */}
            <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-6 mb-6 max-w-xs mx-auto">
              <span className="text-xs uppercase font-bold text-emerald-700 tracking-wider block mb-1">
                Allocated Token
              </span>
              <span className="text-4xl font-extrabold text-emerald-900 block mb-2">
                {successResponse.entry.token_display}
              </span>
              <span className="text-xs text-emerald-700 font-semibold">
                Status: {successResponse.entry.status} • Position #{successResponse.entry.position ?? '1'}
              </span>
            </div>

            <div className="flex gap-3 justify-center">
              <button
                onClick={handleResetAndBookAnother}
                className="px-4 py-2 border border-slate-300 rounded-xl text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Book Another Patient
              </button>
              <button
                onClick={onClose}
                className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-bold shadow-sm"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold">
                <UserPlus className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900">Add Walk-in / Phone Patient</h3>
                <p className="text-xs text-slate-500">Atomic allocation into the official OPD queue</p>
              </div>
            </div>

            {errorMessage && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            {/* Queue Selector */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Target OPD Queue <span className="text-rose-500">*</span>
              </label>
              <select
                value={selectedQueueId}
                onChange={(e) => setSelectedQueueId(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                {queues.map((q) => (
                  <option key={q.queue_id} value={q.queue_id}>
                    {q.queue_name} — {formatDoctorName(q.doctor_name)} ({q.total_waiting} waiting)
                  </option>
                ))}
              </select>
            </div>

            {/* Patient Name */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Patient Full Name <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                <input
                  type="text"
                  required
                  placeholder="e.g. Rahul Sharma"
                  value={patientName}
                  onChange={(e) => setPatientName(e.target.value)}
                  className="w-full pl-10 pr-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>

            {/* Patient Phone */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Contact Phone <span className="text-slate-400 font-normal">(Optional)</span>
              </label>
              <div className="relative">
                <Phone className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                <input
                  type="tel"
                  placeholder="+91 98765 43210"
                  value={patientPhone}
                  onChange={(e) => setPatientPhone(e.target.value)}
                  className="w-full pl-10 pr-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>

            {/* Booking Source & Priority */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Source
                </label>
                <select
                  value={bookingSource}
                  onChange={(e) => setBookingSource(e.target.value as any)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs font-semibold text-slate-900"
                >
                  <option value="WALK_IN">Walk-in Desk</option>
                  <option value="PHONE">Phone Booking</option>
                  <option value="STAFF">Reception Desk</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Priority
                </label>
                <select
                  value={priorityClass}
                  onChange={(e) => setPriorityClass(e.target.value as PriorityClass)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs font-semibold text-slate-900"
                >
                  <option value="NORMAL">Normal</option>
                  <option value="PRIORITY">Priority (Elderly/Infant)</option>
                  <option value="EMERGENCY">Emergency</option>
                </select>
              </div>
            </div>

            {/* Appointment Date */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Appointment Date <span className="text-rose-500">*</span>
              </label>
              <input
                type="date"
                required
                min={new Date().toISOString().split('T')[0]}
                value={appointmentDate}
                onChange={(e) => setAppointmentDate(e.target.value)}
                className="w-full px-3.5 py-2 bg-white border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
              <p className="text-[11px] text-slate-400 mt-1">
                Walk-ins default to today. Phone appointments can select today or upcoming available dates.
              </p>
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Appointment Time
                </label>
                <input
                  type="time"
                  value={appointmentTime}
                  onChange={(e) => setAppointmentTime(e.target.value)}
                  className="w-full px-3.5 py-2 bg-white border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  Must fall within the doctor's saved shift; the server validates it.
                </p>
              </div>
            </div>

            {/* Notes */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Check-in Notes <span className="text-slate-400 font-normal">(Optional)</span>
              </label>
              <textarea
                rows={2}
                placeholder="Chief complaint or triage notes..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full px-3.5 py-2 bg-white border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="pt-3 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2.5 border border-slate-300 rounded-xl text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={bookMutation.isPending}
                className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-sm flex items-center gap-2 disabled:opacity-50"
              >
                {bookMutation.isPending ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Allocating Token...</span>
                  </>
                ) : (
                  <span>Book & Allocate Token</span>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
