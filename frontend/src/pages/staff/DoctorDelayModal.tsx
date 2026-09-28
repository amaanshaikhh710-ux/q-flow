import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { queuesApi } from '../../api/queues';
import { Modal } from '../../components/Modal';
import { extractErrorMessage } from '../../api/client';
import { Clock } from 'lucide-react';

interface Props {
  queueId: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function DoctorDelayModal({ queueId, onClose, onSuccess }: Props) {
  const [minutes, setMinutes] = useState('15');
  const [reason, setReason] = useState('Doctor delayed in morning rounds');

  const mutation = useMutation({
    mutationFn: () =>
      queuesApi.doctorDelay(queueId, {
        delay_minutes: parseInt(minutes, 10) || 15,
        reason: reason.trim() || undefined,
      }),
    onSuccess,
  });

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title="Record Doctor Delay"
      subtitle="Shift consultation starts forward"
      consequence="Recording a clinician delay will shift all downstream patients' estimated consultation windows later by the specified duration."
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
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-semibold text-sm shadow-xs transition-all disabled:opacity-50"
          >
            <Clock className="w-4 h-4" />
            <span>{mutation.isPending ? 'Applying Delay...' : 'Apply Doctor Delay'}</span>
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
            Delay Amount (Minutes)
          </label>
          <input
            type="number"
            min="5"
            max="180"
            value={minutes}
            onChange={(e) => setMinutes(e.target.value)}
            className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
          />
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
            Operational Reason
          </label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Ward rounds running long, transit delay"
            className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
          />
        </div>

        {mutation.isError && (
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700">
            {extractErrorMessage(mutation.error)}
          </div>
        )}
      </div>
    </Modal>
  );
}
