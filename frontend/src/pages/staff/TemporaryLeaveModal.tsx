import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { queueEntriesApi } from '../../api/queueEntries';
import { Modal } from '../../components/Modal';
import { extractErrorMessage } from '../../api/client';
import { LogOut } from 'lucide-react';

interface Props {
  entryId: string;
  tokenDisplay: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function TemporaryLeaveModal({
  entryId,
  tokenDisplay,
  onClose,
  onSuccess,
}: Props) {
  const [reason, setReason] = useState('Laboratory / Diagnostic test');

  const mutation = useMutation({
    mutationFn: () => queueEntriesApi.leave(entryId, reason.trim() || undefined),
    onSuccess,
  });

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={`Mark Temporary Leave (${tokenDisplay})`}
      subtitle="Patient stepping away temporarily"
      consequence="Marking temporary leave removes the patient from the immediate call pool while preserving their queue seniority upon authorized return."
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
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-900 text-white font-semibold text-sm shadow-xs transition-all disabled:opacity-50"
          >
            <LogOut className="w-4 h-4" />
            <span>{mutation.isPending ? 'Updating...' : 'Authorize Temporary Leave'}</span>
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
            Leave Reason / Purpose
          </label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Blood sample collection, X-Ray, Pharmacy"
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
