# Test spec: Due reminders

| Field | Value |
|---|---|
| slug | due-reminders |
| status | skeletons-red |
| spec | ./spec.md |
| design | ./design.md |
| skeletons | up-front |
| framework | pytest |
| marker convention | `@pytest.mark.scenario("S-NN.M") + test_TNN_Ma_<name>` |

## Matrix
| Scenario | Test ID | Level | Fixture / setup | Asserts |
|---|---|---|---|---|
| S-01.1 | T-01.1a | integration | task with owner, no reminder, frozen clock | 201; reminder row status=SCHEDULED; fire_at = due_at - 60m; response carries fire_at; audit event "reminder scheduled" |
| S-01.1 | T-01.1b | unit | due time D, lead L | fire_at(D, L) == D - L, including across a DST boundary |
| S-01.2 | T-01.2a | integration | task with a SCHEDULED reminder | 200 rescheduled=true; same reminder id; fire_at moved; reminder count unchanged; audit event "reminder rescheduled" |
| S-01.3 | T-01.3a | integration | frozen clock; due time one minute behind it | no reminder row; task.due_at saved; response carries the past-time warning |
| S-02.1 | T-02.1a | integration | owner with push muted, email active; reminder SENDING; notifier fake | email delivered; push progress state=muted with muted-since; status SENT; audit event lists delivered + skipped |
| S-02.1 | T-02.1b | unit | ChannelPolicy with push muted | classify() returns push as muted with its muted-since, email as active |
| S-02.2 | T-02.2a | integration | owner with no muted channels; reminder SENDING | every channel delivered; delivery record skipped == [] with "nothing skipped" text |
| S-02.3 | T-02.3a | integration | notifier fake raises on the second channel | status SENDING; first channel delivered and stays delivered; progress shows failed + outstanding; no "reminder sent" audit event |
| X-01 | T-X01a | integration | two concurrent due-time writes, real Postgres | exactly one reminder row; one 201 and one 200 rescheduled |
| X-02 | T-X02a | integration | notifier fake sleeps 5s | API responds < 2s; outbox row exists |

## Fixtures to create
- `owner_with_channels(muted: list[str])` — owner plus channel preferences — T-02.1a, T-02.2a, T-02.3a
- `notifier_fake` — records calls, can be set to raise or sleep — T-02.1a, T-02.3a, T-X02a
- `run_outbox_once()` — drives the outbox worker synchronously — T-02.1a, T-02.2a

## Manual cases
- None

## Notes
- X-01 needs a real database; mark it `@pytest.mark.db` and skip on SQLite.
