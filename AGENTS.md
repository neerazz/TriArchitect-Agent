# Repository Guidelines

## Project Structure & Module Organization
- `resources/` holds the current research artifacts (`implementation_bluprint.md` and the architecture docx). Keep these as the single source of truth for the TriArchitect concept.
- Add runnable code under `src/` with subpackages for each agent (Archeologist, Architect, Validator) and shared typed-graph utilities. Mirror the layout in `tests/` (e.g., `tests/architect/test_planner.py`).
- Place small runnable demos in `examples/` and keep large datasets or generated outputs in a git-ignored `tmp/`.

## Build, Test, and Development Commands
- Create an isolated environment before installing anything: `python -m venv .venv; .\.venv\Scripts\Activate.ps1` (PowerShell) or `source .venv/bin/activate` (bash).
- When dependencies are added, pin them in `requirements.txt` and install with `python -m pip install -r requirements.txt`.
- Run the test suite with `python -m pytest`; use `python -m pytest tests/architect -k planner` to scope while iterating.
- Format on save using `ruff format` (or `python -m ruff format`) and lint with `ruff check` to keep imports and style consistent.

## Coding Style & Naming Conventions
- Target Python 3.11+. Use 4-space indentation, type hints on public functions, and `__all__` only when you need to curate exports.
- Modules: lowercase with underscores (`typed_graph.py`); classes: PascalCase (`TypedMigrationGraph`); tests: `test_<module>.py` with fixtures named `*_factory`.
- Keep functions small; prefer pure helpers in `src/shared/` and isolate I/O at the edge.

## Testing Guidelines
- Use `pytest` with descriptive names: `test_valid_plan_reaches_consensus`. One behavior per test; include negative cases for consensus failures and graph mutation rollbacks.
- Aim for >=80% coverage once the suite exists; tag slow integration runs with `@pytest.mark.slow`.
- Seed randomness (`random.seed(0)`) inside tests and prefer deterministic fixtures over network calls.

## Commit & Pull Request Guidelines
- Use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`). Keep subjects <=72 chars; include a short rationale in the body when behavior changes.
- PRs should link an issue or task, summarize the change, list test commands run, and attach screenshots for any doc/diagram updates in `resources/`.
- Keep commits scoped: one logical change per commit; rebase onto main before opening a PR.

## Security & Configuration Tips
- Never commit secrets or API keys. Load runtime config from environment variables or a local `.env` that stays untracked.
- Review dependencies for supply-chain risk before pinning; prefer hashes in `requirements.txt` once the stack stabilizes.
- Validate any generated artifacts before sharing externally; the consensus/typed-graph concepts in `resources/` should match the implemented code path.
