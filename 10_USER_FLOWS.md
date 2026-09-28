# Q-FLOW — User Flows

## Normal patient
```text
Open → Select hospital → Select department/doctor → Join queue → Get token
→ Monitor queue → Prediction updates → Departure guidance → Travel
→ Arrive/check in → Called → Consultation → Completed
```

## Temporary leave (Staff-Managed Re-queueing)
```text
WAITING → leave request/event → TEMPORARILY_LEFT (excluded from call sequence)
→ queue continues → patient returns → RETURNED → staff executes STAFF_REQUEUES → WAITING
→ ETA recalculated
```
Staff decides and executes re-queueing. No automatic position preservation or pushing to back of queue.

## Emergency
Staff records priority/emergency → backend validates → event stored → queue ordering changes → affected predictions recalculate → WebSocket updates → notification decision.

## Doctor delay
Staff records delay/break → doctor availability changes → queue progression affected → ETA recalculated → affected patients updated.

## Long consultation
Consultation starts → actual elapsed time becomes live queue state → divergence from expected service detected → live correction/uncertainty adjusts → classifier labels if appropriate → completed event stores actual duration in `consultations` and `queue_events`. Training treatment differs by classification.

## No-show
Patient does not respond → staff marks NO_SHOW → event stored → patient removed from active service path → downstream ETA recalculated.

## Multiple doctors
```text
Hospital
 ├─ Doctor A → Queue A
 ├─ Doctor B → Queue B
 └─ Doctor C → Queue C
```
Staff operates authorized queues from one control center.

## Queue completion
Last eligible patient completes → session/queue completes → new joins disabled → history retained → patient sees completed state.

## ETA change
```text
Event → recalculate → compare old/new → shift >= 10 minutes?
                         ├─ no (<10 min)  → UI update (WebSockets)
                         └─ yes (>=10 min) → trigger notification abstraction (SMS/mock)
```

## Travel update
Patient supplies/permits origin → travel request → Google Routes API → travel interval → arrival optimizer → departure window → patient update.
