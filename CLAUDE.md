# CLAUDE.md

## Project
- What we are building: a Litechat clone. A web app that gives regular users metered, pay-as-you-go access to LLMs from multiple providers, through the proxy at https://proxy.litechat.ai (docs: https://proxy.litechat.ai/docs).
- Stack: Python 3.11, Django (latest stable 5.x), SQLite, Django built-in auth and admin, server-rendered Django templates. No frontend framework. No other packages unless the human approves.
- Always use the virtual environment in ./venv. Run Python as venv/bin/python and pip as venv/bin/pip. Keep requirements.txt up to date.

## Ground rules
- I (the human) will not write code. You write all code. I will just make strategic decisions (what to build, scope, tradeoffs). You make tactical decisions (how to build it).
- Never read, cat, open, or print .env or any API key. Refer to keys only by environment variable name (PROXY_OPENAI_API_KEY, PROXY_ANTHROPIC_API_KEY, PROXY_GOOGLE_API_KEY). Never hardcode keys in code, docs, fixtures, or commits. Redact keys from any captured responses or logs.
- Scope each piece of work to fit one Conventional Commit (feat:, fix:, docs:, chore:, build:, refactor:, test:, style:). Tell me (the human) how you scoped it. If the work cannot fit one commit, stop and ask before continuing.
- After each change, suggest a commit message. You may make the commit.
- Protect the codebase. Never delete files or folders, reset or drop the database, run git reset --hard, git push --force, git rebase, or delete branches unless the human explicitly asks.
- Do not assume dependencies or integrations exist. Before planning, check installed packages (venv/bin/pip list), settings.py, urls.py, and existing apps. If something is missing, say so and ask before installing it.
- Do not guess the proxy's API shapes. Check the proxy docs and capture real sample responses before building against them.
- Do not start the dev server yourself (it blocks). Use venv/bin/python manage.py check and tests instead. Ask the human to run the server and report back.
- Use ./TODO.md as the todo list.
- If you find surprising or unintuitive behavior, record it in doc/wiki/footguns/.
- Write all docs in plain, simple English with short sentences.

## Workflow: study -> plan -> execute plan -> rendezvous -> sync docs

- "study <topic>": Run `date +%s` to get the unix timestamp. Write doc/study/<timestamp>_<topic>.md. Cover: the request, the current state of the codebase, feasibility, options and tradeoffs, your recommendation, and open questions for the human. Do not write to any other file. Commit it with a docs: commit.
- Lines starting with NOTE: in a study were added by me (the human). Treat them as decisions.
- "plan <topic>": Run `date +%s`. Write doc/plan/<timestamp>_<topic>.md as a checklist (- [ ] items) of small, concrete, testable steps, based on the study if one exists. For each step list the files to touch, how to test it, and the commit message. Commit it with a docs: commit. Then stop and wait for the human to approve.
- "execute plan <plan file>": Create a new branch from main named feat/<topic> (or fix/<topic>). Do the steps in order. Tick each box in the plan doc as you finish it. Run migrations and venv/bin/python manage.py check after each step. Commit per step with Conventional Commits. If the plan turns out wrong, stop and ask.
- "rendezvous": Finish the plan. Make sure the codebase works: check, migrate, and tests pass. Merge the branch into main with git merge --no-ff. Tell me (the human) exactly what to click to test it in the browser. Remind the human to run "sync docs".
- "sync docs": Update doc/wiki/ so it matches the code: overview.md (what the app does, how to run it), architecture.md (apps, models, URLs, templates), and one file per feature in doc/wiki/features/. Update TODO.md. Commit with a docs: commit.
- "collect-commit": Look at all uncommitted work and commit it in one or more sensible Conventional Commits.
