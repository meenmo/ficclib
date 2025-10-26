# Technical Documentation - EUR Swap Curve System

This directory contains comprehensive technical documentation for the EUR interest rate swap curve construction system.

---

## Document Index

### Core Workflows (Read in Order)

| # | Document | Description | Status |
|---|----------|-------------|--------|
| 00 | [System Overview](00_SYSTEM_OVERVIEW.md) | Architecture, data flow, components | ✅ Complete |
| 01 | [Conventions](01_conventions.md) | Day count, calendars, adjustments | ✅ Complete |
| 02 | [OIS Bootstrap](02_ois_bootstrap.md) | Step 1: Discount curve construction | ✅ Complete |
| 03 | [IBOR Bootstrap](03_ibor_bootstrap.md) | Step 2: Projection curve construction | ✅ Complete (Updated 2025) |
| 04 | [Forward Rates](04_forward_rates.md) | Step 3: Forward rate calculation | ✅ Complete (Updated 2025) |

### Deep Dives (Reference)

| # | Document | Description | Status |
|---|----------|-------------|--------|
| 05 | [Schedule Generation](05_schedule_generation.md) | Payment schedules, stub handling | ✅ Complete (Updated 2025) |
| 06 | [Interpolation](06_interpolation.md) | Step-forward, linear methods | ✅ Complete (Updated 2025) |

### Implementation Notes

| # | Document | Description | Status |
|---|----------|-------------|--------|
| 08 | [QuantLib Integration](07_quantlib_integration.md) | Phase 1 replacement details | 🚧 In Progress |
| 09 | [Precision Engineering](08_precision_engineering.md) | Accuracy tuning techniques | 🚧 In Progress |

---

## Quick Start

**New to the system?** Read in this order:
1. [System Overview](00_SYSTEM_OVERVIEW.md) - Get the big picture
2. [Conventions](01_conventions.md) - Understand market standards
3. [OIS Bootstrap](02_ois_bootstrap.md) - See how discount curves work
4. [IBOR Bootstrap](03_ibor_bootstrap.md) - See how projection curves work
5. [Forward Rates](04_forward_rates.md) - See how forwards are calculated

**Need specific details?** Jump to:
- Schedule generation issues → [Schedule Generation](05_schedule_generation.md)
- Interpolation questions → [Interpolation](06_interpolation.md)
- QuantLib implementation → [QuantLib Integration](07_quantlib_integration.md)

---

## Documentation Standards

Each document follows this structure:

1. **Purpose** - What this component does
2. **Key Concepts** - Theory and definitions
3. **Implementation** - How it works in code
4. **Usage Examples** - Practical code snippets
5. **Testing** - How to validate
6. **Known Issues** - Current limitations
7. **References** - Related docs and external links

**Code References:**
- All file paths are absolute from project root
- Line numbers reference current codebase
- Examples use real test data

---

## Contributing

When updating documentation:

1. **Keep examples up-to-date** with code changes
2. **Update cross-references** when moving content
3. **Add new sections** at appropriate level of detail
4. **Run tests** to verify code examples work
5. **Update README.md** status markers

---

## Document Status Legend

- ✅ **Complete** - Fully documented, up-to-date
- 🚧 **In Progress** - Partially documented, being written
- 📝 **Planned** - Not yet started
- ⚠️ **Needs Update** - Outdated, requires revision

---

## Version History

**v1.0 (2025-10-10):**
- Initial documentation structure
- Core workflows (00-02) complete
- Deep dives in progress

---

*For system implementation details, see code in `/Users/meenmo/Documents/workspace/swap/engine/`*
