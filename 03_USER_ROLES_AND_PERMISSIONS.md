# Q-FLOW — User Roles and Permissions

## Roles
1. Patient
2. Attendant/Family Viewer (POST-MVP)
3. OPD Staff / Reception
4. Hospital Administrator
5. Backend/System Service

## Patient
**View:** own token, queue status, people ahead where allowed, consultation window, travel/departure guidance, notification history, ETA-change explanations.

**Create:** account, queue join, approved travel/location input, leave request.

**Update:** own permitted profile/travel/arrival state.

**Cannot:** reorder queue, insert emergency, pause queue, edit consultation records, modify another patient, overwrite prediction.

## Attendant / Family Viewer (POST-MVP)
Deferred to post-MVP. If implemented later, can view a patient’s shared queue/ETA information with explicit authorization. Cannot mutate queue state.

## OPD Staff / Reception
**View:** authorized hospital/departments, doctors, concurrent queues, queue entries, consultation state, event history and operational prediction signals.

**Create/control:** next patient, consultation start/completion, priority/emergency insertion, pause/resume, doctor delay/break, no-show, temporary leave/return, and staff requeue.

**Cannot:** directly fabricate model output, modify unrelated hospital data, or bypass event recording.

## Hospital Administrator
**View:** hospital-level queues, analytics, queue-health signals, model/evaluation information where exposed, and what-if simulation if implemented.

**Configure:** exact configuration permissions TBD.

**Cannot:** silently rewrite historical events.

## System service
Handles authentication, authorization enforcement, queue transitions, prediction, notification dispatch, WebSocket broadcasting, persistence and event logging.

## Doctor
Doctor is a domain entity whose availability and consultation events affect the queue. The current product has **no separate Doctor Dashboard**. Adding direct doctor controls requires a documented decision and updates to requirements/API/UI/changelog.
