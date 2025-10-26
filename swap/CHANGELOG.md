# Changelog

All notable changes to the EUR Interest Rate Swap Pricing Engine will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-10-26

### Added
- Initial public release of EUR interest rate swap pricing engine
- Dual-curve framework with OIS discounting and IBOR projection
- Professional refactoring for public branch
- Comprehensive technical documentation
- MIT License
- README with quick start guide

### Changed
- Refactored codebase to professional standards
- Applied consistent naming conventions (snake_case, PascalCase, UPPER_CASE)
- Reorganized oversized modules into logical submodules
- Replaced print statements with proper logging
- Added type hints throughout codebase
- Fixed import ordering and removed unused imports
- Improved docstrings and code documentation

### Removed
- Unused imports and dead code
- Backup files (daycount_custom_backup.py, calendars_custom_backup.py)
- Obsolete TODOs and noisy comments

### Fixed
- Import ordering across all modules
- Code quality issues (lambda assignments, zip strict parameters)
- Line length violations
- Module-level imports positioning

### Technical
- All tests passing (npv, par_swap_spread)
- Bloomberg SWPM-matching precision maintained
- QuantLib integration validated
