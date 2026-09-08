---
description: "Decide which qlty checks and thresholds this project should run"
argument-hint: "[path] [notes]"
---

Run the **propose** phase of the quality-gate skill with these arguments: $ARGUMENTS

Follow the skill's dispatch rules for the propose phase exactly: read only that phase's reference file, check the phase's input gate before producing anything, and stop for review when the phase's own instructions say to.
