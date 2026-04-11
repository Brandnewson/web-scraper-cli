# Delivery Gates

Use this checklist at the **start and end of every implementation step**.

## Assessment Priorities (from rubric)

1. **Testing & Test Coverage (20%)**
2. **Code Quality & Documentation (10%)**
3. **Version Control & Git Practices (5%)**

## Step Start Gate (read before coding)

- Confirm the step objective and acceptance behavior.
- Confirm tests to be written first (including edge cases).
- Confirm which docs/code comments/README updates are needed for this step.
- Confirm the intended commit scope (one logical change only).

## Step End Gate (must pass before moving on)

### 1) Testing & Coverage

- Tests for the step were written before implementation.
- Tests failed first for expected reasons, then passed after implementation.
- Edge/failure-path tests are included (not just happy path).
- Coverage check run and recorded where relevant:
  - `pytest --cov=src --cov-report=term-missing`

### 2) Code Quality & Documentation

- Code structure follows module boundaries from `ARCHITECTURE.md`.
- Data structures are appropriate and typed.
- Inline comments added only where logic is non-obvious.
- Documentation updated where needed:
  - `README.md` for usage/setup/output changes
  - `docs/ENGINEERING_RATIONALE.md` for design choices
  - `docs/WORKLOG.md` for phase evidence

### 3) Git Practices

- Change is incremental and focused.
- Commit message uses: `type(scope): description`.
- No unrelated files included.
- Generated artifacts are excluded via `.gitignore`.

## Evidence Format (quick log)

For each step, log in `docs/WORKLOG.md`:

- `Why`
- `What`
- `Validation` (tests + coverage + benchmark if relevant)
- `Notes` (deferrals, risks, follow-ups)

