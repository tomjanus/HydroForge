# HydroForge AI Development Workflow Guidelines

This workflow integrates the best practices from **Matt Pocock's Skills**, **Addy Osmani's Skills**, and established engineering patterns to enable agentic AI development, architecture improvement, TDD, issue tracking, commits, and Sphinx documentation.

## Overview

This workflow provides a complete system for:
- **Agentic AI development** with proper seams and domain language
- **Test-Driven Development (TDD)** using the red-green-refactor loop
- **Issue and ticket tracking** using GitHub issues
- **Atomic commits** with descriptive messages
- **Architecture improvement** using domain modeling and ADRs
- **Sphinx documentation** setup and maintenance
- **Quality gates** via CI/CD

---

## 1. Repository Setup

### 1.1 Initialize the Skill System

Before using any engineering skills, run the setup skill to configure the repository:

```bash
# This will scaffold the configuration the engineering skills assume
# It reads the current repo state and asks you to confirm choices

# Key files it creates/edits:
# - AGENTS.md or CLAUDE.md (adds ## Agent skills block)
# - docs/agents/issue-tracker.md
# - docs/agents/triage-labels.md (if triage skill installed)
# - docs/agents/domain.md
# - docs/agents/GLOSSARY.md
# - .scratch/ directory for a local issue tracker (only if not using GitHub)
```

### 1.2 Issue Tracker Configuration

This repository uses **GitHub issues** as its issue tracker. The conventions
live in `docs/agents/issue-tracker.md`, and the canonical triage labels are
`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and
`wontfix` (see `docs/agents/triage-labels.md`).

Use the `gh` CLI for issue operations, for example:

```bash
gh issue list --state open
gh issue view <number> --comments
gh issue comment <number> --body "..."
```

Specs may also be stored in `spec/` when a change needs a longer design
document. Do not maintain a parallel local markdown tracker under `.scratch/`.

### 1.3 Domain Documentation

Create `GLOSSARY.md` at the repo root to establish shared vocabulary:

```markdown
# Glossary

| Term | Definition |
|------|-----------|
| [domain concept] | [definition] |
```

Also create `docs/adr/` directory for Architecture Decision Records (ADRs).

---

## 2. Test-Driven Development (TDD) Workflow

Follow the **red-green-refactor** loop strictly. Never write production code without a failing test.

### 2.1 The TDD Cycle

```text
    RED                GREEN              REFACTOR
Write a test that fails  →  Write minimal code to make it pass  →  Clean up implementation
     │                      │                        │
     ▼                      ▼                        ▼
Test FAILS           Test PASSES         Tests still PASS
```

### 2.2 Step-by-Step Process

**Step 1: RED — Write a Failing Test**
- Write a test that exercises the public interface, not internals
- Test must fail with current code
- Use the repository's test framework (pytest based on `pyproject.toml`)
- Place tests in `tests/` directory following existing naming conventions

**Step 2: GREEN — Make It Pass**
- Write minimum code to pass the test
- Don't over-engineer; simplicity is key
- Run tests after each change to confirm they pass

**Step 3: REFACTOR — Clean Up**
- Improve code structure without changing behavior
- Extract shared logic, improve naming, remove duplication
- Run tests after each refactor step
- **Never** refactor as part of the red-green loop — refactoring belongs to the review stage

### 2.3 HydroForge-Specific Guidelines

- **Tests verify behavior through public interfaces** — never test private methods
- **Test names read like specifications** — e.g., `test_cannot_create_task_with_empty_title`
- **Use the test pyramid**: most unit tests (smallest), fewer integration tests, minimal E2E
- **Small tests first**: single process, no I/O, no network (milliseconds)
- **Real implementations preferred over mocks** — use fakes/stubs only at boundaries

### 2.4 Bug Fix Pattern (Prove-It Pattern)

When a bug is reported:
1. Write a test that demonstrates the bug (should FAIL)
2. Implement the fix
3. Test PASSES → bug fixed, regression guarded
4. Run full test suite to confirm no regressions

---

## 3. Issue and Ticket Tracking

### 3.1 Tracer-Bullet Ticket Breakdown

Break work into vertical slices using the **to-tickets** skill process:

1. **Gather context** — read any specs, understand the codebase
2. **Explore codebase** — understand current state, find seams
3. **Draft vertical slices** — each ticket is a complete path through all layers
4. **Quiz the user** — present proposed breakdown, get approval
5. **Publish tickets** — create GitHub issues (see `docs/agents/issue-tracker.md`)

### 3.2 Ticket Template (GitHub issue)

```markdown
# <Ticket title>

**What to build:** the end-to-end behaviour this ticket makes work, from the user's perspective

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Acceptance criterion 1
- [ ] Acceptance criterion 2
```

### 3.3 Vertical Slice Rules

- Each slice cuts a **narrow but COMPLETE** path through every layer (schema, API, UI, tests)
- A completed slice is **demoable or verifiable on its own**
- Each slice is sized to fit in a single context window
- Work in **vertical slices**, NOT horizontal slices of one layer

### 3.4 Frontie Work

- Work the **frontier**: any ticket whose blockers are all done
- For a linear chain, work top to bottom
- **Never** close or modify parent issues

---

## 4. Architecture Improvement

### 4.1 Domain Modeling

Before implementing, use the **domain-modeling** skill to:
- Build and sharpen the project's domain model
- Write or update `GLOSSARY.md`
- Record ADRs for important decisions

### 4.2 Architecture Review Process

Use the **code-review-and-quality** skill's 5-axis review:

**1. Correctness** — Does the code do what it claims? Match spec? Handle edge cases?

**2. Readability & Simplicity** — Descriptive names? Straightforward control flow? No "clever" tricks?

**3. Architecture** — Follow existing patterns? Clean module boundaries? No circular dependencies? Feature logic in the right layer?

**4. Security** — Input validated? Secrets out of code? Authentication checked?

**5. Performance** — No N+1 queries? No unbounded loops? No synchronous ops that should be async?

### 4.3 ADRs (Architecture Decision Records)

Create ADRs for significant architectural decisions in `docs/adr/`:

```markdown
# 0001-use-epanet-for-simulation.md

## Status
Proposed

## Context
We need to choose a simulation engine for WDN models.

## Decision
Use EPANET as the simulation engine.

## Consequences
- Pro: industry standard, well-documented
- Con: Python bindings are limited
```

---

## 5. Git Workflow and Versioning

### 5.1 Core Principles

- **Trunk-Based Development**: Keep `main` always deployable
- **Short-lived feature branches**: merge within 1-3 days
- **Atomic commits**: each commit does one logical thing
- **Descriptive messages**: explain the *why*, not just the *what*

### 5.2 Commit Format

```
<type>: <short description>

<optional body explaining why, not what>
```

**Types**: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

### 5.3 Branch Naming

```
feature/<short-description>   → feature/task-creation
fix/<short-description>       → fix/duplicate-tasks
chore/<short-description>     → chore/update-deps
refactor/<short-description>  → refactor/auth-module
```

### 5.4 Worktree Pattern for Parallel AI Agents

```bash
# Create worktrees for parallel work
git worktree add ../project-feature-a feature/task-creation
git worktree add ../project-feature-b feature/user-settings

# Each worktree is a separate directory with its own branch
# Agents can work in parallel without interfering

# When done, merge and clean up
git worktree remove ../project-feature-a
```

### 5.5 Pre-Commit Hygiene

**Before every commit:**
1. `git diff --staged` — check what you're about to commit
2. `git diff --staged -i -G'password|secret|api_key|token' --name-only` — ensure no secrets
3. Run repository tests
4. Run linting
5. Run type checking

**Change Summary Pattern** (after each feature): 
```markdown
CHANGES MADE:
- src/path/to/file.py: [description]

THINGS I DIDN'T TOUCH (intentionally):
- [list of intentionally unchanged files]

POTENTIAL CONCERNS:
- [any concerns identified]
```

### 5.6 Commit Checklist

For every commit:
- [ ] Commit does one logical thing
- [ ] Message explains the why, follows type conventions
- [ ] Tests pass before committing
- [ ] No secrets in the diff
- [ ] No formatting-only changes mixed with behavior changes
- [ ] `.gitignore` covers standard exclusions

---

## 6. Spec-Driven Development

### 6.1 When to Use Specs

- Starting a new project or feature
- Requirements are ambiguous or incomplete
- The change touches multiple files or modules
- Architectural decisions are involved
- Task would take more than 30 minutes

### 6.2 The Spec Workflow (4 Phases)

```
SPECIFY → PLAN → TASKS → IMPLEMENT
```

**Phase 0: Scope Check** — Does the requirement bundle several independently testable capabilities? If so, create a capability map first.

**Phase 1: Specify** — Write a structured spec covering:
- Objective — what we're building and why
- Commands — build, test, lint, dev commands
- Project structure
- Code style with examples
- Testing strategy
- Boundaries (Always/Ask First/Never)
- Success criteria

**Phase 2: Plan** — Generate technical implementation plan with dependency graph

**Phase 3: Tasks** — Break plan into discrete implementable tasks with acceptance criteria

**Phase 4: Implement** — Execute tasks one at a time, following TDD

### 6.3 Spec Template

See `.opencode/skills/spec-driven-development/SKILL.md` for the full template, but the spec should always include:
- Objective
- Tech stack
- Commands (build, test, lint, dev)
- Project structure
- Code style
- Testing strategy
- Boundaries
- Success criteria (specific, testable conditions)

---

## 7. Planning and Task Breakdown

### 7.1 Planning Process

1. **Enter Plan Mode** — Read-only: understand the codebase, identify patterns, map dependencies. **Do NOT write code.**
2. **Identify Dependency Graph** — Map what depends on what, build foundations first
3. **Slice Vertically** — Build one complete feature path at a time (not horizontal slicing)
4. **Write Tasks** — Each task has description, acceptance criteria, verification step, dependencies, files touched, estimated scope
5. **Order and Checkpoint** — Arrange tasks by dependencies, add checkpoints after every 2-3 tasks

### 7.2 Task Template

```markdown
## Task [N]: [Short descriptive title]

**Description:** One paragraph explaining what this task accomplishes.

**Acceptance criteria:**
- [ ] [Specific, testable condition]
- [ ] [Specific, testable condition]

**Verification:**
- [ ] Tests pass: [repository's test command]
- [ ] Build succeeds: [repository's build command]
- [ ] Manual check: [description]

**Dependencies:** [Task numbers this depends on, or "None"]

**Files likely touched:**
- src/path/to/file.py
- tests/path/to/test.py

**Estimated scope:** Small (1-2 files) | Medium (3-5 files) | Large (5+ files)
```

### 7.3 Task Sizing Guidelines

| Size | Files | Scope | Example |
|------|-------|-------|---------|
| **XS** | 1 | Single function or config change | Add a validation rule |
| **S** | 1-2 | One component or endpoint | Add a new API endpoint |
| **M** | 3-5 | One feature slice | User registration flow |
| **L** | 5-8 | Too large — break it down further | — |
| **XL** | 8+ | **Must break down further** | — |

**Break down further if:**
- Would take more than one focused session (2+ hours)
- Cannot describe acceptance criteria in 3 or fewer bullet points
- Touches two or more independent subsystems
- You find yourself writing "and" in the task title

### 7.4 Output Files

- **Plan document**: `tasks/plan.md` — markdown with design decisions, risks, open questions
- **Task list**: `tasks/todo.md` — checklist-style, default target

---

## 8. CI/CD and Quality Gates

### 8.1 Quality Gate Pipeline

Every change goes through these gates before merge:

```text
Pull Request Opened
    ▼
┌──────────────────┐
│ FORMAT CHECK     │  black --check .
│   ↓ pass         │
│ LINT CHECK       │  flake8 --config=.flake8 .
│   ↓ pass         │
│ TYPE CHECK       │  mypy .
│   ↓ pass         │
│ UNIT TESTS       │  pytest
│   ↓ pass         │
│ BUILD PACKAGE    │  python -m build
│   ↓ pass         │
│ INSTALL CHECK    │  pip install --no-deps --target "$RUNNER_TEMP/hydroforge-wheel-install" dist/*.whl
└──────────────────┘
    ▼
  Ready for review
```

**No gate can be skipped.** If a gate fails, fix the cause rather than disabling
the check or excluding files without justification.

### 8.2 CI Configuration (GitHub Actions)

The repository's actual workflow is `.github/workflows/ci.yml`. It runs the
following jobs:

- `lint-test`: `black --check .`, `flake8 --config=.flake8 .`, `mypy .`, and
  `pytest` on Python 3.12
- `build`: builds an sdist and wheel and verifies installation of the wheel
- `publish`: uploads to PyPI on pushes to `main` when `PYPI_TOKEN` is configured

Run the same checks locally with:

```bash
black --check .
flake8 --config=.flake8 .
mypy .
pytest
python -m build
```

### 8.3 Branch Protection Rules

- Required reviews: at least 1 approval before merge
- Required status checks: CI must pass before merge
- Branch protection: no force-pushes to main
- Auto-merge: if all checks pass and approved, merge automatically

### 8.4 CI Optimization

When pipeline exceeds 10 minutes, apply these strategies (in order of impact):
1. Cache dependencies (use `actions/cache` for pip cache)
2. Run jobs in parallel (split lint, typecheck, test, build)
3. Only run what changed (use path filters)
4. Optimize the test suite (remove slow tests from critical path)
5. Use larger runners

---

## 9. Documentation with Sphinx

### 9.1 Sphinx Documentation Setup

HydroForge already has a spec document at `spec/0001-uncertainty-scenario-generation.md`. To add Sphinx documentation:

```bash
# Install Sphinx
pip install sphinx sphinx-rtd-theme

# Initialize Sphinx docs
sphinx-quickstart docs/docs/  # answer the prompts

# Or add to existing structure
sphinx-autobuild docs/ docs/_build/html
```

### 9.2 Documentation Workflow

1. **Create reStructuredText files** in `docs/` directory
2. **Update `conf.py`** with project metadata
3. **Build documentation** to verify:
   ```bash
   sphinx-build -b html docs/ docs/_build/html
   ```
4. **Link to code elements** using Sphinx cross-references
5. **Keep documentation synchronized** with code when behavior changes

### 9.3 Documentation Best Practices

- **Document "what" and "why", not "how"** — obvious implementation details shouldn't be documented
- **Public APIs**: concise docstrings explaining inputs, outputs, important assumptions, and exceptions
- **Keep documentation synchronized** with code when behavior changes
- **Use Sphinx auto-summary** for module documentation
- **Document assumptions, limitations, and reproducibility requirements** for scientific code

### 9.4 Sphinx Document Structure Example

```rst
.. _hydroforge-overview:

Overview
--------

HydroForge is an uncertainty injection and scenario generation framework for water distribution network (WDN) model simulations.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   usage
   api
   contributions

Installation
------------

.. code-block:: bash

   pip install hydroforge-tools

Usage
-----

.. code-block:: python

   import hydroforge
   
   # Create a simple network
   network = hydroforge.Network(...)
   
   # Add uncertainties
   network.add_uncertainty(...)
```

### 9.5 ADRs in Documentation

Keep Architecture Decision Records both as files in `docs/adr/` and referenced from the documentation. Each ADR should explain:
- The decision and its status (Proposed, Accepted, Deprecated, Superseded)
- The context and problem being solved
- The decision and its consequences
- Any alternatives considered

---

## 10. Full Development Workflow (End-to-End)

Here's the complete flow from idea to shipped code:

### 10.1 Starting a New Feature

1. **Create a spec** (if feature is non-trivial) using spec-driven-development pattern
2. **Break down into tasks** using planning-and-task-breakdown
3. **Create tickets** in GitHub issues

### 10.2 Implementing a Feature (Vertical Slice)

1. **Select a ticket** from the frontier (no blockers)
2. **Write a failing test** (RED) — public interface, behavior-focused
3. **Write minimum code** to make test pass (GREEN)
4. **Run full test suite** to confirm
5. **Refactor** — clean up implementation, improve structure
6. **Commit** with atomic, descriptive message
7. **Update ticket** status to resolved
8. **Push and create PR**

### 10.3 Pull Request Process

1. **Ensure CI passes** locally before pushing
2. **Fill PR template** (based on matt_pocock_skills/pr skill):
   - Summary with diagram/diff-sketch/tree
   - Evidence (before/after test results)
   - Merge danger (one-way or two-way door)
   - Blast radius assessment
3. **Request code review** using the 5-axis review (code-review-and-quality skill)
4. **Address review feedback** — make separate commits for separate concerns
5. **Once approved**, merge (squash or rebase to keep history clean)

### 10.4 Release Process

1. **Version bump** following semantic versioning (git-workflow-and-versioning skill)
2. **Add changelog entry** (grouped by Added/Changed/Fixed/Deprecated/Removed)
3. **Tag the release**: `git tag -a v1.4.0 -m "Release 1.4.0"`
4. **Push tag**: `git push origin v1.4.0`
5. **Deploy** and monitor

---

## 11. Troubleshooting and Common Patterns

### 11.1 Common Rationalizations & Realities

| Rationalization | Reality |
|----------------|---------|
| "I'll write tests after the code works" | You won't. Tests after the fact test implementation, not behavior. |
| "This is too simple to test" | Simple code gets complicated. Tests document expected behavior. |
| "Tests slow me down" | Tests slow you down now, but speed you up every time you change code later. |
| "I tested it manually" | Manual testing doesn't persist. Tomorrow's change might break it with no way to know. |
| "The code is self-explanatory" | Tests ARE the specification. They document what the code should do. |
| "It's just a prototype" | Prototypes become production code. Tests from day one prevent "test debt" crisis. |
| "CI is too slow" | Optimize the pipeline, don't skip it. A 5-minute pipeline prevents hours of debugging. |
| "This change is trivial, skip CI" | Trivial changes break builds. CI is fast for trivial changes anyway. |
| "I'll clean it up later" | Later never comes. The review is the quality gate. |
| "AI-generated code is probably fine" | AI code needs more scrutiny, not less. It's confident and plausible, even when wrong. |

### 11.2 Red Flags to Watch For

- Large uncommitted changes accumulating
- Commit messages like "fix", "update", "misc"
- Formatting changes mixed with behavior changes
- No `.gitignore` in the project
- Committing `node_modules/`, `.env`, or build artifacts
- Long-lived branches that diverge significantly from main
- Force-pushing to shared branches
- A breaking change shipped under a minor or patch version bump
- A release with no tag, or a version number hand-edited out of sync with the tag
- A user-facing release with no changelog entry, or a changelog that's just dumped commit messages
- A feature PR with retries, queues, or external calls and zero new telemetry
- Log lines built by string interpolation instead of structured fields
- No correlation/request ID — each log line is an orphan
- Metrics labeled with user IDs, raw URLs, or error message text (cardinality bomb)
- Latency tracked as an average with no percentiles
- Alerts that fire daily and get acknowledged without action
- Alerts on causes (CPU, memory) paging humans while user-facing error rate is unmonitored
- Secrets, tokens, or full request bodies appearing in logs
- "It works on my machine" as the only evidence a production feature is healthy

---

## 12. Repository-Specific Conventions for HydroForge

### 12.1 Project Structure

```
HydroForge/
├── src/hydroforge/          # Main source code
│   ├── __init__.py
│   ├── cli.py               # Command-line interface
│   ├── auxiliary/           # Shared utilities and I/O
│   ├── uncertainty/         # Uncertainty injection
│   ├── sampling/            # Sampling methods
│   ├── measurements/        # Sensor models
│   └── wdn_modelling/       # WDN-specific functionality
│       ├── backends/
│       ├── epanetfile_io/
│       ├── graphs/
│       ├── modifiers/
│       ├── networks/
│       └── measurement_placement/
├── tests/                   # Test directory (pytest-based)
│   ├── base_networks/       # EPANET input files for testing
│   └── test_*.py            # Test files
├── examples/                # Runnable examples grouped by module
├── data/                    # Example/case-study inputs
├── spec/                    # Specification documents
├── docs/                    # Agent documentation (issue tracker, domain, triage)
├── .github/workflows/       # CI: lint, type check, tests, build, publish
├── .gitignore               # Git ignores
├── pyproject.toml           # Project config (pytest, deps)
├── requirements.txt         # Python dependencies
├── AGENTS.md                # Agent skills configuration
└── WORKFLOW_GUIDELINES.md   # This file
```

### 12.2 Testing Configuration

From `pyproject.toml`:
- Test framework: pytest
- Coverage: `--cov=hydroforge --cov-report=term-missing`
- Markers: `slow`, `integration`, `unit`
- norecursedirs: `.*`, `build`, `dist`, `CVS`, `_darcs`, `*.egg`, `venv`, `env`, `__pycache__`

### 12.3 Code Style

- Follow existing patterns in the codebase
- Use descriptive names, no `temp`, `data`, `result` without context
- Keep functions focused (single responsibility)
- Maximum ~100 lines per function, ~300 lines per commit

### 12.4 Scientific Computing Guidelines

- **Preserve units explicitly** where relevant
- **Check dimensions and physical consistency**
- **Consider numerical stability** — avoid catastrophic cancellation
- **Document non-obvious numerical choices** and assumptions
- **Distinguish clearly between**: model parameters, calibration parameters, observations, synthetic data, assumptions, random variables, derived quantities
- **Use deterministic seeds** when stochastic behavior is involved
- **Record important configuration parameters** for reproducibility
- **Separate input data from generated results**

---

## 13. Getting Started Checklist

### First Time Setup

- [ ] Read `AGENTS.md` and confirm the `## Agent skills` block is current
- [ ] Read `GLOSSARY.md` and `docs/agents/domain.md` for project terminology
- [ ] Confirm GitHub issue tracker access with `gh auth status`
- [ ] Read `docs/agents/issue-tracker.md` and `docs/agents/triage-labels.md`
- [ ] Create an ADR only when an architectural decision needs to be recorded

### Daily Development

- [ ] Start work from the frontier of the issue tracker
- [ ] Write a failing test before any production code (RED)
- [ ] Make the test pass with minimum code (GREEN)
- [ ] Refactor, then run tests again
- [ ] Commit with atomic, descriptive message
- [ ] Update ticket status
- [ ] Push and create PR
- [ ] Address review feedback
- [ ] Merge when CI passes

### Before Each Release

- [ ] Version bump (semantic versioning)
- [ ] Changelog entry with human-readable impact
- [ ] Tag the release
- [ ] Deploy and monitor
- [ ] Run full test suite
- [ ] Verify documentation is current

---

## 14. Skill Integration Summary

This workflow integrates skills from three repositories:

### From Matt Pocock's Skills (`/home/lepton/Documents/git_projects/matt_pocock_skills/`)
- **TDD** — Test-driven development with red-green-refactor loop
- **to-tickets** — Break work into tracer-bullet tickets
- **pr** — PR body template and best practices
- **setup-matt-pocock-skills** — Repository configuration (issue tracker, triage labels, domain docs)
- **domain-modeling** — Build and sharpen domain models
- **codebase-design** — Vocabulary for interface depth, seams, leverage, locality
- **triage** — Issue triage and labeling
- **to-spec** — Convert tickets to specs

### From Addy Osmani's Skills (`/home/lepton/Documents/git_projects/addy_osmani_skills/`)
- **git-workflow-and-versioning** — Trunk-based development, atomic commits, branch naming
- **test-driven-development** — Comprehensive TDD with test pyramids, DAMP over DRY
- **spec-driven-development** — Spec before coding with 4-phase workflow
- **planning-and-task-breakdown** — Break work into ordered tasks with acceptance criteria
- **code-review-and-quality** — 5-axis review (correctness, readability, architecture, security, performance)
- **ci-cd-and-automation** — Quality gate pipelines, GitHub Actions, deployment strategies
- **observability-and-instrumentation** — Structured logging, metrics, tracing, alerting
- **constraint-driven-development** — Dependency management and upgrade discipline

### Combined Workflow Benefits

- **Agentic**: Clear seams, domain language, and ticket system enable AI agents to work independently
- **TDD**: Red-green-refactor loop ensures tests guide implementation
- **Quality**: 5-axis code review + CI quality gates catch issues early
- **Architecture**: Domain modeling + ADRs keep architecture clean and documented
- **Trackability**: Local markdown tracker + descriptive commits + changelog = full audit trail
- **Shippable**: Sphinx documentation + release process = professional-grade delivery
