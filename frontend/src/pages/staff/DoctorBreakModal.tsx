import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { queuesApi } from '../../api/queues';
import { Modal } from '../../components/Modal';
import { extractErrorMessage } from '../../api/client';
import { Coffee } from 'lucide-react';

interface Props {
  queueId: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function DoctorBreakModal({ queueId, onClose, onSuccess }: Props) {
  const [minutes, setMinutes] = useState('15');
  const [reason, setReason] = useState('Scheduled clinical rest');

  const startMutation = useMutation({
    mutationFn: () =>
      queuesApi.doctorBreakStart(queueId, {
        duration_minutes: parseInt(minutes, 10) || 15,
        reason: reason.trim() || undefined,
      }),
    onSuccess,
  });

  const endMutation = useMutation({
    mutationFn: () => queuesApi.doctorBreakEnd(queueId),
    onSuccess,
  });

  const error = startMutation.error ?? endMutation.error;

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title="Doctor Break Management"
      subtitle="Temporarily pause active consultations"
      consequence="Initiating a doctor break will adjust waiting patients' estimated arrival windows and notify the queue monitor."
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-slate-600 hover:text-slate-800 text-sm font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={endMutation.isPending}
            onClick={() => endMutation.mutate()}
            className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 font-semibold text-xs transition-colors border border-slate-200"
          >
            {endMutation.isPending ? 'Ending...' : 'End Break Early'}
          </button>
          <button
            type="button"
            disabled={startMutation.isPending}
            onClick={() => startMutation.mutate()}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 active:bg-amber-800 text-white font-semibold text-sm shadow-xs transition-all disabled:opacity-50"
          >
            <Coffee className="w-4 h-4" />
            <span>{startMutation.isPending ? 'Starting...' : 'Start Break'}</span>
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
            Break Duration (Minutes)
          </label>
          <input
            type="number"
            min="5"
            max="120"
            value={minutes}
            onChange={(e) => setMinutes(e.target.value)}
            className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-amber-500 focus:ring-2 focus:ring-amber-100 transition-all"
          />
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
            Reason / Operational Context
          </label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Lunch break, Clinical handover"
            className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-amber-500 focus:ring-2 focus:ring-amber-100 transition-all"
          />
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700">
            {extractErrorMessage(error)}
          </div>
        )}
      </div>
    </Modal>
  );
}
