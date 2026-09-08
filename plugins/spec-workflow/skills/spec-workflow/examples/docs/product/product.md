# Product: Tally (example excerpt)

| Field | Value |
|---|---|
| status | active |
| updated | 2026-09-08 |

## Vision
Someone sharing a to-do list with other people can trust that a task with a due date will reach whoever owns it, on the channel they actually read, without anyone having to check the app.

## Actors
- **Owner** — the person a task belongs to; wants to be reminded on the channel they read, and not on the ones they muted.
- **Collaborator** — someone the list is shared with; can create tasks and set due dates on them.
- **Notifier** — external email and push provider; delivers the reminders.

## Jobs to be done
1. Owner can put a due date on a task and know a reminder is set.
2. Owner can choose which channels reminders reach them on.
3. Owner can see whether a reminder actually arrived, and why it did not.

## Non-goals
- Calendar sync — different product surface (→ future)
- Time tracking or estimates (→ never)

## Constraints
- Stack: Python (FastAPI), Postgres, self-hosted
- Integrations: transactional email and push provider
- Operational: single developer, v1 in 6 weeks

## Capability map
| Capability | Responsibility | Status |
|---|---|---|
| tasks | Task creation, editing and completion | planned |
| reminders | Scheduling and delivery of due-date reminders | planned |
| activity | Record of what happened to a task and when | planned |

## Feature roadmap
| Slug | Capability | Rigor | Priority | Release |
|---|---|---|---|---|
| due-reminders | reminders | full | P1 | v1 |
| task-list | tasks | lite | P1 | v1 |
| activity-log | activity | full | P2 | v1 |

## v1 demo scenario
An owner sets a due date on a task and sees the reminder time confirmed. When it fires, the reminder goes out on email and push but skips the channel they muted, and the delivery view shows which channels were reached and which were skipped. The activity log shows both events.

## Assumptions
- Reminders fire one hour before the due time unless the owner changes the lead time (assumed)
