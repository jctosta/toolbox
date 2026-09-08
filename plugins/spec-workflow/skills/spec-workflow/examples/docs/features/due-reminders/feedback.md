# Feedback: due-reminders

Review comments on the artifacts in this folder. Open items are addressed in the `feedback` phase; resolved items keep their resolution line.

## F-01 [spec.md] [S-02.1] resolved
2026-09-08 · reviewer
> AND push is skipped

Skipped how? The owner needs to tell "you muted this" apart from "we could not reach it", or every muted channel reads as a bug.

Resolution: S-02.1 now records the muted channel with the time it was muted; T-02.1a asserts the muted-since value; design.md gives ChannelPolicy the "since when" responsibility.

## F-02 [spec.md] [REQ-01] resolved
2026-09-08 · reviewer

Should collaborators get the reminder too? No — keep to the owner, just confirm it in the brief.

Resolution: Confirmed out of scope; brief already lists per-collaborator reminders as future.

## F-03 [wireframes/due-date-form.html] [] resolved
2026-09-08 · reviewer

The picker should say when the reminder will actually fire, not just accept a due time. Otherwise the lead time is invisible until it arrives.

Resolution: due-date-form.html now shows the computed fire time under the picker (S-01.1); no spec change — the fire time was already in the THEN lines.
