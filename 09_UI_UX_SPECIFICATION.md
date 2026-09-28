# Q-FLOW — UI/UX Specification

## Product visual direction
Use the established Q-FLOW visual language where appropriate: dark navy/black base, purple/blue/cyan neon accents, clean grid, large headings, rounded panels, meaningful diagrams/UI, minimal clutter. Usability takes priority over decorative effects.

## Patient screens
### Registration/Login
Identity, phone/email, password/auth, errors; SMS verification if chosen.

### Hospital Selection
Hospital list/search, address, relevant OPD availability.

### Department/Doctor/OPD Selection
Department, doctor, current queue/session status. Multiple doctors must be visible.

### Join Queue
Selected hospital/department/doctor, join action, token, applicable priority information. Patient cannot self-declare emergency under current assumptions.

### Live Queue
Token, people ahead where permitted, serving state, consultation window, last update, ETA-change reason, travel time, recommended departure/arrival window.

### ETA Explanation
Show only actual reasons, e.g. priority insertion, doctor interruption, service-speed change.

### Leave / Update
Temporary leave request and return instructions. Exact position policy TBD.

### Arrival / Check-in
Patient arrival action.

### Notifications
History and current updates from web/SMS/WhatsApp.

## Staff screens
### Login
Secure staff authentication.

### Reception Control Center
One control center showing multiple doctors/queues concurrently. Each queue needs serving token, waiting count, ETA and controls for next/priority/pause where authorized.

### Queue Detail
Ordered entries, status, priority, prediction, active events, event history.

### Patient Management
Call, start/complete consultation, no-show, temporary leave/return.

### Emergency Handling
Clear PRIORITY/EMERGENCY action with confirmation/reason capture if required.

### Doctor Delay/Break
Start/end break, delay, unavailable/available. All actions create events.

### Queue Health
If implemented: queue growth, service speed, ETA volatility, backlog, priority count. No fabricated score.

## Admin
Potential hospital configuration, analytics, queue health and what-if simulation. MVP scope TBD.

## Real-time UX
Queue changes update without full refresh. Reconnect must resynchronize from authoritative server state. Avoid noisy animation.

## Responsive
Patient UI: mobile-first PWA. Staff: desktop/tablet optimized.

## Accessibility
Readable contrast, non-color-only status, clear labels, practical keyboard support.

## Explicit UI rule
Do **not** create a separate Doctor Dashboard.
