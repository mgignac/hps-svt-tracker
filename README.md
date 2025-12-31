# HPS SVT Component Tracker

A component tracking and test management system for the Heavy Photon Search Silicon Vertex Tracker detector at Jefferson Lab.

## Features

- Track all SVT components (modules, FEBs, cables, power systems, etc.)
- Record test results with measurements and images
- Maintain installation history across run periods
- Track component status and location
- Store images and data files in organized structure
- Command-line interface for all operations

## Installation

```bash
cd hps_svt_tracker
pip install -e .
```

This will install the `svt` command-line tool.

## Quick Start

### Initialize the Database

```bash
svt init
```

This creates the database at `~/.hps_svt_tracker/svt_components.db` and the test data directory at `~/.hps_svt_tracker/test_data/`.

### Add a Component

```bash
# Add a module
svt add --id HPK-SN123456 --type module --manufacturer Hamamatsu \
        --location "Clean Room" --status incoming

# Add a FEB
svt add --id FEB-042 --type feb --serial FEB-042-2024 \
        --manufacturer SLAC --status spare
```

### List Components

```bash
# List all components
svt list

# Filter by type
svt list --type module

# Filter by status
svt list --status spare
```

### View Component Details

```bash
svt show HPK-SN123456
```

This shows:
- Component information
- Test history
- Installation history

### Record a Test Result

```bash
svt test HPK-SN123456 --type iv_curve \
     --pass \
     --voltage 60 \
     --current 2.3e-6 \
     --temp -9.0 \
     --images /path/to/iv_curve.png \
     --tested-by "Jane Doe" \
     --notes "Normal operation"
```

### Install a Component

```bash
svt install HPK-SN123456 Layer1_top_axial \
    --run-period "2025_spring_run" \
    --installed-by "John Doe"
```

### Remove a Component

```bash
svt remove HPK-SN123456 \
    --reason "end_of_run" \
    --removed-by "John Doe" \
    --location "Clean Room Storage"
```

## Module Assembly Workflow

Modules are assembled from separate sensor and hybrid components. This section demonstrates the complete workflow from component creation through assembly, testing, installation, and eventual disassembly.

### Step 1: Create Individual Components

First, create the module shell and its constituent parts:

```bash
# Create the module component (empty shell)
svt add --id MODULE-L1-001 --type module --manufacturer HPK \
        --status incoming --location "Clean Room"

# Create the sensor
svt add --id SENSOR-S12345 --type sensor --manufacturer HPK \
        --status incoming --location "Clean Room"

# Create the hybrid
svt add --id HYBRID-H67890 --type hybrid --manufacturer SLAC \
        --status incoming --location "Clean Room"
```

### Step 2: Assemble the Module

Attach the sensor and hybrid to the module:

```bash
# Assemble sensor and hybrid onto module
svt assemble MODULE-L1-001 \
    --sensor SENSOR-S12345 \
    --hybrid HYBRID-H67890 \
    --assembled-by "Jane Doe" \
    --notes "Assembled in clean room, epoxy cure time 24hrs"
```

You can also assemble components separately:

```bash
# Attach only sensor first
svt assemble MODULE-L1-001 --sensor SENSOR-S12345

# Attach hybrid later
svt assemble MODULE-L1-001 --hybrid HYBRID-H67890
```

### Step 3: Test the Assembled Module

Record test results for the assembled module:

```bash
# IV curve test
svt test MODULE-L1-001 --type iv_curve \
     --pass \
     --voltage 60 \
     --current 2.3e-6 \
     --temp -9.0 \
     --images /path/to/iv_curve.png \
     --notes "All channels functional"

# Noise test
svt test MODULE-L1-001 --type noise_test \
     --pass \
     --noise 1580 \
     --images /path/to/noise_scan.png

# Update status after qualification
svt add --id MODULE-L1-001 --status qualified
```

### Step 4: Install in Detector

Once qualified, install the module:

```bash
svt install MODULE-L1-001 Layer1_top_axial \
    --run-period "2025_spring_run" \
    --installed-by "John Doe"
```

### Step 5: Track During Operations

Add maintenance logs and comments during the run:

```bash
# Log observations
svt log MODULE-L1-001 "Monitoring noise levels" --type observation

# Add comment
svt comment MODULE-L1-001 "Performance stable after 2 weeks"
```

### Step 6: Remove from Detector

At end of run period or for maintenance:

```bash
svt remove MODULE-L1-001 \
    --reason "end_of_run" \
    --removed-by "Jane Doe" \
    --location "Clean Room"
```

### Step 7: Disassemble if Needed

Disassemble the module for repair, component reuse, or retirement:

```bash
svt disassemble MODULE-L1-001 \
    --disassembled-by "Jane Doe" \
    --notes "Sensor reuse for new module, hybrid shows degradation"
```

After disassembly:
- The sensor and hybrid are detached but remain in the database
- Both can be reassembled onto different modules or retired
- Assembly/disassembly history is preserved in maintenance logs

### View Complete Module History

Check the full lifecycle of the module:

```bash
svt show MODULE-L1-001
```

This displays:
- Current assembly state (which sensor/hybrid attached)
- All test results
- Installation history
- Maintenance logs including assembly/disassembly events

### View Summary Statistics

```bash
svt summary
```

## Component Types

Supported component types:
- `module` - Silicon detector modules (assembled from sensor + hybrid)
- `sensor` - Silicon sensors (can be assembled onto modules)
- `hybrid` - Readout hybrids (can be assembled onto modules)
- `feb` - Front End Boards
- `cable` - Signal/power cables
- `optical_board` - Optical transmission boards
- `mpod_module` - MPOD power supply modules
- `mpod_crate` - MPOD crates
- `flange_board` - Flange boards
- `other` - Other components

## Installation Status Values

- `installed` - Currently in the detector
- `spare` - Ready to deploy
- `incoming` - New, not yet tested/qualified
- `testing` - Currently under test
- `qualified` - Tested and approved for installation
- `failed` - Not functional
- `repair` - Being repaired
- `degraded` - Functional but performance declining
- `retired` - Permanently removed from service
- `lost` - Missing/unaccounted for

## Module Position Notation

**Layers 0-3:**
- Format: `LayerN_det_{axial/stereo}`
- Examples: `Layer0_top_axial`, `Layer1_bottom_stereo`

**Layers 4-7:**
- Format: `LayerN_det_{axial/stereo}_side`
- Examples: `Layer4_top_axial_slot`, `Layer5_bottom_stereo_hole`

Where:
- `N` = layer number (0-7)
- `det` = `top` or `bottom`
- `{axial/stereo}` = `axial` or `stereo`
- `side` = `slot` or `hole` (layers 4-7 only)

**FEB Positions:**
- Format: `FEBN` where N is the FEB number
- Examples: `FEB1`, `FEB2`, `FEB3`

## Database Location

By default, the database and test data are stored in:
- Database: `~/.hps_svt_tracker/svt_components.db`
- Test data: `~/.hps_svt_tracker/test_data/`

You can use a different location with the `--db-path` option:

```bash
svt --db-path /path/to/my/database.db list
```

## Test Data Organization

When you record test results with images, they are automatically organized:

```
test_data/
├── 2024/
│   └── HPK-SN123456/
│       ├── 20241115_143022_iv_curve_0.png
│       └── 20241115_143022_iv_curve_data.csv
└── 2025/
    └── FEB-042/
        └── 20250103_091500_calibration_0.png
```

Images and data files are:
- Organized by year and component ID
- Named with timestamp and test type
- Stored with relative paths (portable)

## Advanced Usage

### Python API

You can also use the package programmatically:

```python
from hps_svt_tracker import Component, TestResult, get_default_db

# Get database
db = get_default_db()

# Create a component
module = Component(
    id='HPK-SN789',
    type='module',
    manufacturer='Hamamatsu',
    installation_status='spare',
    current_location='Storage',
    attributes={
        'hybrid_serial': 'HYB-123',
        'sensor_serial': 'SENS-456',
        'channel_count': 512
    }
)
module.save(db)

# Record a test
test = TestResult(
    component_id='HPK-SN789',
    test_type='noise_test',
    pass_fail=True,
    measurements={
        'mean_noise': 1600,
        'max_noise': 2100,
        'bad_channels': [47, 128]
    },
    tested_by='Jane Doe'
)
test.save(db)

# Query components
all_modules = Component.list_all(component_type='module', db=db)
spare_modules = Component.list_all(status='spare', db=db)
```

## Backup

The database is a single SQLite file. To backup:

```bash
cp ~/.hps_svt_tracker/svt_components.db backup_20250101.db
```

Or use the Python API:

```python
from hps_svt_tracker import get_default_db

db = get_default_db()
backup_path = db.backup_database('/path/to/backup.db')
```

Remember to also backup the test_data directory!

## Development

Run tests:
```bash
python -m pytest tests/
```

## Support

For issues or questions, contact the HPS collaboration.

## License

[Add license information]
