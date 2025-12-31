# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a component tracking and test management system for the Heavy Photon Search (HPS) Silicon Vertex Tracker (SVT) detector at Jefferson Lab. It tracks physical components (modules, FEBs, cables, etc.), test results with associated data files, installation history across run periods, and component status/location.

## Development Commands

### Installation
```bash
pip install -e .
```

### Running Tests
```bash
# Run all tests
python -m pytest tests/

# Run with verbose output
python -m pytest tests/ -v

# Run a specific test
python -m pytest tests/test_basic.py::test_component_creation -v
```

### CLI Usage
```bash
# Initialize database (creates ~/.hps_svt_tracker/)
svt init

# Add a component
svt add --id HPK-SN123 --type module --manufacturer Hamamatsu --status incoming

# List components (with optional filters)
svt list
svt list --type module --status spare

# Show component details with test/installation history
svt show HPK-SN123

# Record a test result
svt test HPK-SN123 --type iv_curve --pass --voltage 60 --current 2.3e-6

# Install/remove components
svt install HPK-SN123 Layer1_top_axial --run-period "2025_spring_run"
svt install FLANGE-001 Flange_slot0 --run-period "2025_spring_run"
svt remove HPK-SN123 --reason "end_of_run"

# Update component location (separate from installation)
svt location HPK-SN123 "Clean Room"
svt location FLANGE-001 "JLab"

# Add maintenance log or comment
svt log HPK-SN123 "Component shows degradation" --type issue --severity warning
svt comment HPK-SN123 "Component working well"

# Assemble/disassemble modules from sensors and hybrids
svt add --id MODULE-001 --type module --status incoming
svt add --id SENSOR-001 --type sensor --status incoming
svt add --id HYBRID-001 --type hybrid --status incoming
svt assemble MODULE-001 --sensor SENSOR-001 --hybrid HYBRID-001 --notes "Assembled in clean room"
svt disassemble MODULE-001 --notes "Maintenance required"

### Automatic User Tracking
All commands that track "who" performed an action (`--tested-by`, `--installed-by`, `--removed-by`, `--logged-by`, `--assembled-by`, `--disassembled-by`) automatically use the current system username if not specified. You can still override by providing the option explicitly.

### Location Tracking
Component location is tracked independently from installation status. Installing a component does NOT change its location - you must use the `location` command explicitly to update where a component is physically located. Similarly, removing a component from its installed position does NOT change its location.

### Module Assembly
Modules are assembled from sensors and hybrids:
- Create separate components for the module, sensor, and hybrid
- Use `svt assemble` to attach sensor and/or hybrid to a module
- Sensors and hybrids remain independently trackable even when assembled
- A sensor/hybrid can only be assembled on one module at a time
- Use `svt disassemble` to remove sensor and hybrid from a module
- Assembly/disassembly events are logged in maintenance history
```

## Architecture

### Core Modules

**database.py** - SQLite database management with schema initialization
- `Database` class handles connections, schema creation, and backups
- Foreign keys enabled, row_factory set for dict-like access
- Default location: `~/.hps_svt_tracker/svt_components.db`
- Default test data: `~/.hps_svt_tracker/test_data/`

**models.py** - Data models and business logic
- `Component` - Represents detector components with CRUD operations
- `TestResult` - Test results with automatic file organization
- `install_component()` / `remove_component()` - Manage installation lifecycle
- `update_location()` - Update physical location (separate from installation)
- `assemble_module()` / `disassemble_module()` - Manage module assembly from sensors and hybrids
- Components have JSON attributes field for type-specific metadata
- Test files are automatically organized: `test_data/YYYY/component_id/timestamp_testtype_N.ext`

**cli.py** - Click-based command-line interface
- Uses Click's context passing pattern for database injection
- All commands support `--db-path` for custom database location
- Tabulate library for formatted output

### Database Schema

**components** - Main component registry
- Primary key: `id` (typically manufacturer serial number)
- Tracks current state: `installation_status`, `current_location`, `installed_position`
- Assembly tracking: `assembled_sensor_id`, `assembled_hybrid_id` (for modules)
- JSON field `attributes_json` for type-specific data
- Enforces valid types/statuses via CHECK constraints

**test_results** - Test history with measurements
- Foreign key to components
- Common measurements as indexed columns (voltage, current, noise, temperature)
- Complex data in `measurements_json`
- File paths stored as relative paths from `data_dir` for portability

**installation_history** - Installation/removal tracking
- Tracks position, dates, who installed/removed, run period
- `removal_date` NULL = currently installed

**connections** - Component interconnections (modules to FEBs, cables, etc.)

**maintenance_log** - Issues, repairs, maintenance records

### Component Types and Statuses

**Valid Types:** module, hybrid, sensor, feb, cable, optical_board, mpod_module, mpod_crate, flange_board, other

**Valid Statuses:** installed, spare, incoming, testing, qualified, failed, repair, degraded, retired, lost

**Module Assembly:** Modules are assembled from sensors and hybrids. The assembly relationship is tracked in the components table via foreign keys.

### Position Notation

**Layers 0-3:** `LayerN_{top/bottom}_{axial/stereo}`
Example: `Layer1_top_axial`, `Layer2_bottom_stereo`

**Layers 4-7:** `LayerN_{top/bottom}_{axial/stereo}_{slot/hole}`
Example: `Layer5_top_axial_slot`, `Layer6_bottom_stereo_hole`

**FEB Positions:** `FEBN` (e.g., `FEB1`, `FEB2`)

**Flange Board Positions:** `Flange_slotN` (slots 0-3)
Example: `Flange_slot0`, `Flange_slot1`, `Flange_slot2`, `Flange_slot3`
Note: Flange boards are installed in the vacuum flange, which bridges connections from inside vacuum to outside. There is only one flange with 4 slots numbered 0-3.

## Key Design Patterns

### Database Context Manager Pattern
All database operations use context managers:
```python
with db.get_connection() as conn:
    conn.execute(...)
    conn.commit()
```

### Dual Storage Strategy
- Simple/common measurements stored as indexed columns for efficient queries
- Complex/type-specific data stored as JSON for flexibility
- Example: `voltage_measured` column + `measurements_json` field

### File Organization
When test results include images/data files:
1. Files are copied to organized structure (not moved)
2. Paths stored as relative to `data_dir` for portability
3. Naming: `YYYYMMDD_HHMMSS_testtype_N.ext`

### Model Instantiation
Models can be created from database rows OR instantiated directly:
```python
# From database
component = Component.get('ID', db)

# Direct instantiation
component = Component(id='ID', type='module', installation_status='spare')
component.save(db)
```

## Testing

Tests use pytest with temporary databases via fixtures. The `temp_db` fixture creates isolated test environments with clean schema. Tests demonstrate basic CRUD operations and are good reference for model usage.

## Important Notes

- Database uses SQLite with foreign keys enabled - deletions may cascade
- All timestamps stored as ISO format strings for SQLite compatibility
- The `get_default_db()` function auto-initializes schema if database doesn't exist
- Component IDs should be unique and immutable (typically manufacturer serial numbers)
- Test file storage is copy-based to preserve originals
