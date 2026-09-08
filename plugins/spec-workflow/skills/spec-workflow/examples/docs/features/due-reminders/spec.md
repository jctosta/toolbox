# Spec: Due reminders

| Field | Value |
|---|---|
| slug | due-reminders |
| status | approved |
| brief | ./brief.md |

## Requirements

## REQ-01: Reminder scheduling
The system SHALL schedule exactly one reminder for a task when a due time is set on it, and reschedule that reminder when the due time changes.

| Actors | Preconditions | Postconditions |
|---|---|---|
| Owner, Collaborator | task exists and has an owner; no reminder for the task is SCHEDULED or SENDING (INV-01) | a Reminder for the task exists in SCHEDULED with a fire time; the owner can see when it will fire |

### S-01.1 Main flow — reminder scheduled
- GIVEN a task with an owner and no reminder
- WHEN a due time is set on the task
- THEN a Reminder for the task is created in SCHEDULED
- AND the Reminder fires one lead time before the due time
- AND the scheduled fire time is shown to the person who set the due time
- AND an audit event "reminder scheduled" is recorded for the Reminder

### S-01.2 Alternative — due time changed
- GIVEN a task whose Reminder is SCHEDULED
- WHEN the due time is changed
- THEN the existing Reminder is moved to the new fire time
- AND no second Reminder is created for the task
- AND an audit event "reminder rescheduled" is recorded

### S-01.3 Exception — due time already past
- GIVEN a task with an owner and no reminder
- WHEN a due time earlier than the current moment is set
- THEN no Reminder is created
- AND the due time is still saved on the task
- AND the person who set it is told the time has already passed

## REQ-02: Reminder delivery
The system SHALL deliver a fired reminder to every channel the owner has not muted, reporting the muted channels rather than treating them as failures.

| Actors | Preconditions | Postconditions |
|---|---|---|
| Owner, Notifier | Reminder is SENDING | every unmuted channel has been delivered; Reminder SENT; the owner can see which channels were skipped |

### S-02.1 Main flow — delivery with a muted channel
- GIVEN an owner who has muted push and left email unmuted, and a Reminder that is SENDING
- WHEN the Reminder is delivered
- THEN the reminder reaches the owner by email
- AND push is skipped and recorded as muted with the time it was muted
- AND the Reminder moves to SENT
- AND an audit event "reminder sent" listing delivered and skipped channels is recorded

### S-02.2 Alternative — no muted channels
- GIVEN an owner with no muted channels and a Reminder that is SENDING
- WHEN the Reminder is delivered
- THEN the reminder reaches the owner on every channel
- AND the delivery record states that nothing was skipped

### S-02.3 Exception — one channel fails
- GIVEN a Reminder that is SENDING for an owner with two unmuted channels
- WHEN delivery to one channel fails
- THEN the Reminder remains SENDING
- AND the channel already delivered stays delivered
- AND the failure and the channels still outstanding are visible to the owner
- AND no audit event "reminder sent" is recorded

## Cross-cutting constraints
- X-01: Setting a due time twice on the same task within the same second produces exactly one Reminder (idempotent under concurrent edits).
- X-02: Setting a due time is acknowledged to the person who set it within 2 seconds at p95 regardless of notifier latency.

## Data and state changes
- Entities created: Reminder, Audit event
- Entities modified: Task — due time set or changed
- Lifecycle transitions used: Reminder: SCHEDULED → SENDING (out of scope, the scheduler), SENDING → SENT
- Invariants relied on: INV-01, INV-02
- Invariants introduced: None

## Removed
- None
