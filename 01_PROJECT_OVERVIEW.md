# Q-FLOW — Project Overview

## Identity
- Project: Q-FLOW
- Team: Initiator
- Domain: Healthcare & MedTech
- Problem Statement: The Waitlist Nobody Sees
- PS No.: CX0308
- Positioning: **A Dynamic, Uncertainty-Aware OPD Queue Forecasting & Arrival Optimization System.**

## Problem
OPD visits are difficult to plan because consultation timing changes with the live queue, service duration, priority insertions, doctor interruptions, no-shows and other operational events. Existing digital queues and wait-time products already provide tokens, queue progress, notifications and, in some cases, prediction/travel features. Therefore Q-FLOW is not defined as a token app, booking app, generic AI wait predictor, or Google Maps integration.

## Objective
Continuously forecast when a patient is likely to be consulted, represent uncertainty honestly as a time window, adapt to live queue events, combine the forecast with traffic-aware travel time, and recommend a useful departure/arrival window. Give OPD staff one control center for multiple doctors and concurrent queues.

## Target users
- Patients
- Attendants/families
- OPD Staff / Reception
- Hospital administrators

Doctors are service providers whose availability and consultation activity affect queues; the current architecture does **not** include a separate Doctor Dashboard.

## Core journey
**Get Token / Join Queue → Predict → Travel → Leave → Update → Arrive**

## End-to-end flow
```text
Hospital
  ↓
OPD Staff / Reception Control Center
  ↓
Multiple doctors / concurrent queues
  ↓
Live queue events
  ↓
Q-FLOW queue state + prediction engine
  ↓
Patient-specific consultation window
  ↓
Traffic-aware travel time
  ↓
Departure / arrival optimization
  ↓
Web/PWA + WhatsApp + SMS
```

## Major capabilities
### Queue
- Multiple doctors and concurrent queues
- Token/join flow
- Live queue movement
- Event history

### Prediction
- Robust baseline when data is limited
- Historical service patterns
- Service-duration prediction
- Current-session/live correction
- Uncertainty-aware ETA windows
- Disruption-aware recalculation

### Events and edge cases
- Emergency/priority insertion
- Doctor delay/break/interruption
- Queue pause/resume
- No-show
- Temporary leave and return
- Unusually long consultations/outliers
- Queue slowdown/shock

### Arrival optimization
- Traffic-aware travel time through the agreed Google Routes API direction
- Recommended departure window
- Safe arrival window
- Objective concept: reduce physical waiting while controlling lateness risk

### Explainability and operations
- “Why did my ETA change?”
- Reception Control Center operational stats (MVP)
- Queue-health advanced analytics (POST-MVP)
- What-if simulation (POST-MVP)

### Notifications
- Web/PWA (WebSockets)
- SMS (required MVP; mock provider first, Twilio pluggable)
- WhatsApp (POST-MVP)

## Differentiation
Q-FLOW does not claim that individual pieces are globally new. Its proposed differentiation is the combination of dynamic patient-specific forecasting, live event-driven queue reconstruction, disruption/outlier classification, uncertainty-aware ETA ranges, traffic-aware arrival optimization, explainable ETA changes, multi-user OPD operations, and hospital operational intelligence.

## Explicit scope boundary
Out of scope for the current product: full EMR, prescriptions, insurance, payments, bed management, appointment marketplace, AI medical chatbot, disease prediction, a full medical-record platform, and a separate Doctor Dashboard.

## Implementation status
The conversation establishes a detailed plan, not completed software. No feature is COMPLETE unless implementation and tests later establish it.
