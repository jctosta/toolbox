# Brief: Due reminders

| Field | Value |
|---|---|
| slug | due-reminders |
| capability | reminders |
| rigor | full — external notifier, per-channel delivery, timing guarantee |
| status | approved |
| source | conversation |

## Original request
> None — originated in conversation

## Problem
A task with a due date is only useful if someone is told before it passes. Today the due date sits in the app and nobody sees it unless they happen to open the list, so shared tasks slip past their due time without anyone noticing.

## Options considered
1. **Scheduled reminder per task** — setting a due time schedules a reminder that fans out to the owner's channels. Trade-off: needs a scheduler and a delivery path we do not have yet.
2. **Daily digest** — one message each morning listing what is due. Trade-off: simpler, but a task due at 09:00 is announced too late to act on.
3. **Do less** — badge the list in-app only. Trade-off: still requires opening the app, which is the actual problem.

## Direction
Option 1. The problem is that nobody looks at the app, so anything that requires opening it does not solve it. A digest (option 2) stays available later as a second delivery kind (→ future).

## Scope
In:
- Setting a due time on a task schedules exactly one reminder
- Changing the due time reschedules rather than duplicating
- Delivery reaches every channel the owner has not muted, and reports what was skipped

Out:
- Recurring tasks and their reminders — separate feature (→ future)
- Snoozing a reminder from the notification itself (→ future)
- Per-collaborator reminders; only the owner is notified in v1 (→ future)

## Actors and entities
- Actors: Owner, Collaborator, Notifier
- Entities touched: Task, Reminder, Audit event
- Domain changes: None

## Related
- task-list (owns the Task this feature attaches a Reminder to)

## Open questions
| ID | Question | Owner | Blocking |
|---|---|---|---|
| Q-01 | Is a one-hour default lead time right, or should it vary by how far out the due date is? | user | no |

## Assumptions
- The owner's channel preferences already exist and are editable elsewhere (assumed)
