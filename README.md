td — task daemon
=================

minimal, text-first, daily driver. no projects, no tags, no friction.

```
td add "review PR #242"
td add "call mom" --every "mon 9am"
td ls
td do 3
td week
```

files
-----
- `~/.td/tasks.yaml` — single source of truth
- `~/.td/done.yaml` — completed (auto-archived weekly)

philosophy
----------
- plain text you can grep
- recurring syntax you can read: `every mon 9am`, `every fri`, `every 1st`
- `td ls` = today + overdue. `td week` = 7-day view. `td all` = everything.
- one keystroke to defer, done, delete. no confirmation prompts.