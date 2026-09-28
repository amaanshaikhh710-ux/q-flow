# Q-FLOW — Notification System

## Channels
- Web/PWA real-time updates (WebSockets)
- **SMS — PRIMARY REQUIRED for MVP**
- **WhatsApp — POST-MVP**

## Provider architecture (FINAL FOR MVP)
- Core service interacts with an abstract notification interface (`NotificationProvider`).
- Development uses a **local/mock provider** that records and logs messages.
- Production/external gateway allows plugging in **Twilio** without altering queue or prediction logic.

## Meaningful-change threshold (FINAL FOR MVP)
Do not notify on small ETA movements. 
- **Threshold:** $\ge 10$ minutes change in the predicted consultation window (or explicit critical event).
- Threshold is **configurable in backend settings** rather than hardcoded.
- Trivial fluctuations do NOT trigger external notifications.

## Events
### Queue joined
Confirm token and initial ETA.

### ETA changed
If meaningful, show old/new window and reason where appropriate.

### Emergency/priority
Notify affected patients if their ETA meaningfully changes.

### Doctor delay/break
Notify when it materially affects the patient.

### Queue resumed
Notify where relevant.

### Recommended departure
Send departure window after queue + travel calculation is available.

### Arrival window changed
Send when queue/traffic changes materially affect the recommendation.

## SMS example
```text
Q-FLOW: Token 47. Est. consultation 4:10–4:25 PM. Recommended departure 3:30–3:40 PM.
```
This is an illustrative format only; final templates are TBD.

## WhatsApp
Can provide richer information: token, people ahead, consultation window, departure window and change reasons. Provider/template requirements TBD.

## Delivery flow
```text
Event → prediction → compare → meaningful? → select channel → send → record delivery state
```

## Failure handling
Notification failure must not block queue progression. Record failure and retry under provider-safe policy. Retry count/backoff TBD.

## Privacy
Do not put unnecessary medical information into SMS/WhatsApp. Q-FLOW does not require full medical records in the current scope.
