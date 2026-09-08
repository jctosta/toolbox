---
description: "Wire the gate into CI, git hooks and agent instructions"
argument-hint: "[path] [notes]"
---

Run the **enforce** phase of the quality-gate skill with these arguments: $ARGUMENTS

Follow the skill's dispatch rules for the enforce phase exactly: read only that phase's reference file, check the phase's input gate before producing anything, and stop for review when the phase's own instructions say to.
