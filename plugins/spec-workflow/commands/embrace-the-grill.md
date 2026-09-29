---
description: "Upgrade an existing spec-workflow repo to work with mattpocock-skills"
argument-hint: "[notes]"
---

Run the **embrace-the-grill** phase of the spec-workflow skill with these arguments: $ARGUMENTS

Follow the skill's dispatch rules for the embrace-the-grill phase exactly: read only that phase's reference file, check the phase's input gate before producing anything, and stop for review when the phase's own instructions say to.

If the loaded skill doesn't list the embrace-the-grill phase, stop: it is older than this command. Tell the user to update the spec-workflow plugin, or check which copy `--plugin-dir` loaded.
