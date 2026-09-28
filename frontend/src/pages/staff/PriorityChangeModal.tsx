import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { queueEntriesApi } from '../../api/queueEntries';
import { Modal } from '../../components/Modal';
import { extractErrorMessage } from '../../api/client';
import { ShieldAlert } from 'lucide-react';

interface Props {
  entryId: string;
  tokenDisplay: string;
  currentPriority: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function PriorityChangeModal({
  entryId,
  tokenDisplay,
  currentPriority,
  onClose,
  onSuccess,
}: Props) {
  const [priorityClass, setPriorityClass] = useState(
    currentPriority === 'NORMAL' ? 'PRIORITY' : 'NORMAL'
  );
  const [reason, setReason] = useState('Clinical triage adjustment');

  const mutation = useMutation({
    mutationFn: () =>
      queueEntriesApi.updatePriority(entryId, {
        priority_class: priorityClass,
        reason: reason.trim() || undefined,
      }),
    onSuccess,
  });

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={`Change Priority (${tokenDisplay})`}
      subtitle="Adjust patient triage classification"
      consequence="Modifying priority class will re-rank the waiting list. Affected patients will receive updated ETAs and dynamic forecasts."
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
            <ShieldAlert className="w-4 h-4" />
            <span>{mutation.isPending ? 'Updating...' : 'Update Priority'}</span>
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
            New Priority Classification
          </label>
          <select
            value={priorityClass}
            onChange={(e) => setPriorityClass(e.target.value)}
            className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
          >
            <option value="NORMAL">NORMAL — Standard Order</option>
            <option value="PRIORITY">PRIORITY — Senior / Fast-Track</option>
            <option value="EMERGENCY">EMERGENCY — Urgent Triage</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
            Clinical Justification
          </label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Elderly patient, infant, mobility issues"
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
