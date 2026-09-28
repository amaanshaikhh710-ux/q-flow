import { useState, useMemo } from 'react';
import { useMutation } from '@tanstack/react-query';
import { queuesApi } from '../../api/queues';
import { queueEntriesApi } from '../../api/queueEntries';
import { Modal } from '../../components/Modal';
import { extractErrorMessage } from '../../api/client';
import type { QueueEntryResponse } from '../../types/api';
import { Zap, ShieldAlert, UserPlus, AlertCircle } from 'lucide-react';

interface Props {
  queueId: string;
  waitingEntries?: QueueEntryResponse[];
  onClose: () => void;
  onSuccess: () => void;
}

export default function EmergencyModal({
  queueId,
  waitingEntries = [],
  onClose,
  onSuccess,
}: Props) {
  // Mode: 'ELEVATE' = elevate existing patient in queue by token; 'WALK_IN' = new emergency patient
  const [mode, setMode] = useState<'ELEVATE' | 'WALK_IN'>(
    waitingEntries.length > 0 ? 'ELEVATE' : 'WALK_IN'
  );

  const [selectedEntryId, setSelectedEntryId] = useState<string>(
    waitingEntries[0]?.id || ''
  );
  const [tokenInput, setTokenInput] = useState('');
  const [patientUserId, setPatientUserId] = useState('');
  const [reason, setReason] = useState('Acute clinical triage elevation');

  // Match token if typed manually
  const matchedEntryByToken = useMemo(() => {
    if (!tokenInput.trim()) return null;
    const clean = tokenInput.trim().toUpperCase();
    return waitingEntries.find(
      (e) =>
        e.token_display.toUpperCase() === clean ||
        `Q${String(e.token_number).padStart(3, '0')}` === clean ||
        String(e.token_number) === clean
    );
  }, [tokenInput, waitingEntries]);

  // Mutation for elevating an existing waiting patient
  const elevateMutation = useMutation({
    mutationFn: (targetEntryId: string) =>
      queueEntriesApi.updatePriority(targetEntryId, {
        priority_class: 'EMERGENCY',
        reason: reason.trim() || undefined,
      }),
    onSuccess,
  });

  // Mutation for inserting a new walk-in emergency patient
  const insertMutation = useMutation({
    mutationFn: (targetUserId: string) =>
      queuesApi.insertEmergency(queueId, {
        patient_user_id: targetUserId.trim(),
        reason: reason.trim() || undefined,
      }),
    onSuccess,
  });

  const isPending = elevateMutation.isPending || insertMutation.isPending;
  const currentError = elevateMutation.error || insertMutation.error;

  const handleSubmit = () => {
    if (mode === 'ELEVATE') {
      const targetId = matchedEntryByToken ? matchedEntryByToken.id : selectedEntryId;
      if (targetId) {
        elevateMutation.mutate(targetId);
      }
    } else {
      // Check if user entered a token into patientUserId field
      const tokenMatch = waitingEntries.find(
        (e) =>
          e.token_display.toUpperCase() === patientUserId.trim().toUpperCase() ||
          String(e.token_number) === patientUserId.trim()
      );
      if (tokenMatch) {
        elevateMutation.mutate(tokenMatch.id);
      } else {
        insertMutation.mutate(patientUserId.trim());
      }
    }
  };

  const isSubmitDisabled =
    isPending ||
    (mode === 'ELEVATE' && !selectedEntryId && !matchedEntryByToken) ||
    (mode === 'WALK_IN' && !patientUserId.trim());

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title="Emergency Consultation Triage"
      subtitle="Immediate clinician priority insertion"
      consequence="This will place the emergency patient immediately at the head of the waiting line. All downstream patients' consultation windows will be dynamically recalculated and reforecasted."
      isDestructive={true}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="px-4 py-2 rounded-xl text-slate-600 hover:text-slate-800 text-sm font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isSubmitDisabled}
            onClick={handleSubmit}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 active:bg-red-800 text-white font-semibold text-sm shadow-xs transition-all disabled:opacity-50 cursor-pointer"
          >
            <Zap className="w-4 h-4" />
            <span>{isPending ? 'Processing...' : 'Confirm Emergency Insert'}</span>
          </button>
        </>
      }
    >
      <div className="space-y-4">
        {/* Mode Selector Tabs */}
        <div className="grid grid-cols-2 gap-2 p-1 bg-slate-100 rounded-xl border border-slate-200 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setMode('ELEVATE')}
            className={`flex items-center justify-center gap-1.5 py-2 rounded-lg transition-all ${
              mode === 'ELEVATE'
                ? 'bg-white text-red-700 shadow-2xs font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Elevate Waiting Patient</span>
          </button>
          <button
            type="button"
            onClick={() => setMode('WALK_IN')}
            className={`flex items-center justify-center gap-1.5 py-2 rounded-lg transition-all ${
              mode === 'WALK_IN'
                ? 'bg-white text-red-700 shadow-2xs font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <UserPlus className="w-3.5 h-3.5" />
            <span>New Walk-in Patient</span>
          </button>
        </div>

        {mode === 'ELEVATE' ? (
          <div className="space-y-3">
            {waitingEntries.length > 0 ? (
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
                  Select Waiting Patient / Token *
                </label>
                <select
                  value={matchedEntryByToken ? matchedEntryByToken.id : selectedEntryId}
                  onChange={(e) => {
                    setSelectedEntryId(e.target.value);
                    setTokenInput('');
                  }}
                  className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-red-500 focus:ring-2 focus:ring-red-100 transition-all font-sans"
                >
                  {waitingEntries.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.token_display} — Position #{entry.position ?? '—'} (Current:{' '}
                      {entry.priority_class})
                    </option>
                  ))}
                </select>

                <div className="mt-2.5">
                  <span className="text-[11px] text-slate-400 block mb-1">
                    Or type token number directly:
                  </span>
                  <input
                    type="text"
                    value={tokenInput}
                    onChange={(e) => setTokenInput(e.target.value)}
                    placeholder="e.g. Q006"
                    className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm font-mono text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-red-500 focus:ring-2 focus:ring-red-100 transition-all uppercase"
                  />
                  {matchedEntryByToken && (
                    <p className="mt-1 text-xs text-emerald-600 font-semibold flex items-center gap-1">
                      <span>✓ Matched token {matchedEntryByToken.token_display} in waiting queue</span>
                    </p>
                  )}
                  {tokenInput.trim() && !matchedEntryByToken && (
                    <p className="mt-1 text-xs text-amber-600 font-medium">
                      Token not found in waiting queue. Please select from the dropdown above.
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-3.5 rounded-xl bg-slate-100 border border-slate-200 text-xs text-slate-600">
                No patients are currently waiting in this queue. Switch to "New Walk-in Patient" to admit an emergency arrival.
              </div>
            )}
          </div>
        ) : (
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
              Patient Identifier or Token *
            </label>
            <input
              type="text"
              value={patientUserId}
              onChange={(e) => setPatientUserId(e.target.value)}
              required
              placeholder="e.g. Q006 or registered patient UUID"
              className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm font-mono text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-red-500 focus:ring-2 focus:ring-red-100 transition-all"
            />
            <p className="mt-1 text-[11px] text-slate-400">
              Entering an existing token (e.g. Q006) will automatically elevate that waiting patient to Emergency priority.
            </p>
          </div>
        )}

        {/* Clinical Reason */}
        <div>
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
            Triage Reason / Clinical Note *
          </label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
            placeholder="e.g. Acute chest pain, respiratory distress, trauma"
            className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-red-500 focus:ring-2 focus:ring-red-100 transition-all"
          />
        </div>

        {currentError && (
          <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600 mt-0.5" />
            <div>
              <span className="font-bold">Triage Error: </span>
              <span>{extractErrorMessage(currentError)}</span>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
