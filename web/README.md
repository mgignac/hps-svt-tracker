# HPS SVT Tracker Web Interface

A Flask-based web interface for viewing and managing HPS Silicon Vertex Tracker component data.

## Quick Start

### 1. Install Dependencies

```bash
# Activate your virtual environment
source .venv/bin/activate

# Install web dependencies
pip install -r requirements-web.txt
```

### 2. Run Development Server

```bash
# From the project root directory
python run_dev.py
```

The web interface will be available at: **http://localhost:5000**

## Features (Phase 1 - Read-Only)

- **Dashboard**: Statistics overview with component counts and recent test activity
- **Component List**: Browse all components with filtering by type and status
- **Component Detail**: View comprehensive component information including:
  - Basic info (type, serial number, manufacturer, status, location)
  - Test history with pass/fail results
  - Installation history across run periods
  - Maintenance logs
  - Component connections
  - Module assembly information (for sensors, hybrids, and modules)
- **Test Detail**: View detailed test results with measurements and associated files
- **File Serving**: Securely view test data files (images, CSV files, etc.)

## Project Structure

```
web/
├── __init__.py
├── app.py              # Flask application factory
├── config.py           # Configuration (Dev/Prod)
├── routes/             # Route blueprints
│   ├── main.py         # Dashboard
│   ├── components.py   # Component views
│   ├── tests.py        # Test result views
│   └── files.py        # Secure file serving
├── templates/          # Jinja2 templates
│   ├── base.html       # Base template with Bootstrap
│   ├── index.html      # Dashboard
│   ├── components/     # Component templates
│   ├── tests/          # Test templates
│   └── errors/         # Error pages
└── static/
    ├── css/
    │   └── style.css   # Custom styling
    └── js/
```

## Routes

| Route | Description |
|-------|-------------|
| `/` | Dashboard with statistics |
| `/components` | List all components (with filters) |
| `/components/<id>` | Component detail page |
| `/tests/<id>` | Test result detail page |
| `/files/<path>` | Serve test data files |

## Configuration

### Environment Variables

- `SECRET_KEY`: Flask secret key (required in production)
- `SVT_DB_PATH`: Custom database path (optional, defaults to `~/.hps_svt_tracker/svt_components.db`)
- `SVT_DATA_DIR`: Custom test data directory (optional, defaults to `~/.hps_svt_tracker/test_data/`)

### Development Configuration

Located in `web/config.py`:
- Debug mode enabled
- Session cookies allow HTTP
- Template auto-reload enabled

### Production Configuration

For production deployment:

```bash
export SECRET_KEY='your-secure-secret-key-here'
export FLASK_ENV=production

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 'web.app:create_app()'
```

## Database Integration

The web interface reuses the existing `hps_svt_tracker` package:
- `Database` class for connection management
- `Component` and `TestResult` models for data access
- All helper functions (`get_maintenance_logs()`, `get_connections_for_component()`, etc.)

No database code is duplicated - routes are thin wrappers that call existing model methods.

## Security Features (Phase 1)

- **Read-only**: All routes are GET-only, no write operations
- **Path validation**: Prevents directory traversal attacks when serving files
- **Secure sessions**: HttpOnly, SameSite cookies configured
- **Error handling**: Custom 404/500 pages

## Future Phases

### Phase 2: Authentication (Before Public Deployment)
- Jefferson Lab LDAP/SSO integration
- Protected file access
- Session management

### Phase 3: Write Operations
- Add component forms
- Record test results with file upload
- Update component status/location
- Add maintenance logs
- CSRF protection
- Role-based access control (viewer, editor, admin)

## Deployment

### Development
```bash
python run_dev.py
```

### Production (with Nginx + Gunicorn)

1. Install Gunicorn (already in requirements-web.txt)

2. Run Gunicorn:
```bash
gunicorn -w 4 -b 127.0.0.1:8000 'web.app:create_app()'
```

3. Configure Nginx as reverse proxy (see plan file for nginx config)

4. Set up systemd service for auto-restart

## Styling

Uses Bootstrap 5 with custom CSS for:
- HPS-themed navigation bar
- Component status badges (installed, spare, testing, etc.)
- Test result indicators (pass/fail)
- Responsive design for mobile devices

## Troubleshooting

**Import errors**: Make sure you're in the project root directory and the virtual environment is activated.

**Database not found**: The web interface uses the default database location (`~/.hps_svt_tracker/`). Run `svt init` first if you haven't already.

**Port already in use**: Change the port in `run_dev.py` or kill the process using port 5000.

## Support

For issues or questions, refer to the main project `CLAUDE.md` file or the implementation plan at `~/.claude/plans/`.
