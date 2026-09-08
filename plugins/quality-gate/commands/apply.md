---
description: "Write the tailored .qlty/qlty.toml and prove it runs"
argument-hint: "[path] [notes]"
---

Run the **apply** phase of the quality-gate skill with these arguments: $ARGUMENTS

Follow the skill's dispatch rules for the apply phase exactly: read only that phase's reference file, check the phase's input gate before producing anything, and stop for review when the phase's own instructions say to.
