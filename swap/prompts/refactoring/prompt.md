You are a senior Financial Engineer specialized in Python. Perform a pre-publish refactor of this repository to prepare a public branch.

# 0) Guardrails (no behavioral drift)
- Tests and golden outputs must remain identical after refactor.
- MUST PASS:
  - pricer/swap/.venv/bin/python -m pricer.swap.test.npv
  - pricer/swap/.venv/bin/python -m pricer.swap.test.par_swap_spread
- If any change worsens tests, lints, or outputs, REVERT it immediately and note it in the report.

# 1) Versioning & metadata
- Set engine version to **1.0.0**
- Ensure LICENSE, README, and a minimal CHANGELOG entry for this refactor.

# 2) Remove unused code
- Delete unused functions/classes/vars/imports (static analysis with ruff F401/F841 + vulture).
- If uncertain, deprecate with a thin shim and `logging.warning` (do not break public API).

# 3) Naming consistency (professional)
- Enforce professional naming:
  - snake_case: functions/variables
  - PascalCase: classes
  - UPPER_CASE: constants
- Normalize legacy names (e.g., `pay_freq` → `payment_frequency`) with project-wide updates.
- Produce a rename map (old → new, rationale).

# 4) Imports: order & hygiene
- Order imports: stdlib / third-party / first-party; blank line between groups; alphabetical within groups.
- Remove unused imports; avoid wildcard imports.
- Enforce with `ruff --select F401,I` and `isort` (profile=black).

# 5) Structure & file size
- Keep modules succinct: target **≤ 150–200 lines per file**.
- If longer, split by responsibility into submodules; create folders and `__init__.py` as needed.
- Maintain a clean public surface via `__all__`.

# 6) Logging > print
- Replace all `print` with `logging` (module-level logger via `logging.getLogger(__name__)`).
- Use appropriate levels: debug/info/warning/error; avoid noisy logs in hot paths.

# 7) Object-oriented design
- Prefer cohesive classes with single, clear purpose; move free functions into relevant classes as appropriate.
- Encapsulate curve/pricing concerns (e.g., CurveBuilder, DiscountCurve, ForwardCurve, SwapPricer).
- Keep methods purposeful and minimal; no god objects.

# 8) Types, docs, professionalism
- Add/complete type hints; one-line module docstrings; concise, useful comments only.
- Remove obsolete TODOs and noisy comments.

# 9) Deliverables (TECHNICAL NOTES UPDATE)
Update the technical notes under `pricer/swap/technical_notes` to fully reflect the refactored source code and conventions. Files to revise:
- 00_SYSTEM_OVERVIEW.md
- 01_conventions.md
- 02_ois_bootstrap.md
- 03_ibor_bootstrap.md
- 04_forward_rates.md
- 05_schedule_generation.md
- 06_interpolation.md
- 07_quantlib_integration.md
- 08_precision_engineering.md
- README.md

Requirements for each note:
- Synchronize code snippets with the updated modules/classes/methods (correct imports, names, and signatures).
- Include KaTeX-compatible math for all formulas; verify correctness and fix any defects (dimensions, compounding basis, ACT/360 vs ACT/365F, log-DF vs zero-rate interpolation, stub handling).
- Provide minimal runnable examples (where applicable) referencing the public API (no private internals).
- Cross-link sections (e.g., from conventions → interpolation → bootstrapping) for learning flow.
- Add tables/figures as needed (e.g., schedule examples, DF vs maturity) and annotate edge cases (spot lag, TARGET holidays, stubs).
- Ensure readers without deep background can follow: define symbols before use; include a short “intuition” paragraph per key formula.
- Validate every numerical example against the current tests/outputs (npv, par swap spread).

# Commands (adapt as needed)
- ruff check . --select F,E,I,B --fix

# Output now
1) Proposed refactor plan (high-level)
2) Initial rename map candidates
3) List of oversized files to split with intended new module names
4) Confirmation of version set to 1.0.0
5) Checklist of technical notes updated with a brief change summary per file