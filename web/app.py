"""
Flask application factory for HPS SVT Tracker web interface
"""
from datetime import datetime
from flask import Flask, g, render_template
from hps_svt_tracker.database import Database, get_default_db
from .config import DevelopmentConfig


def _ordinal_suffix(day):
    """Return the ordinal suffix for a day number (st, nd, rd, th)."""
    if 11 <= day <= 13:
        return 'th'
    return {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')

# Display name mappings for component types
COMPONENT_TYPE_DISPLAY_NAMES = {
    'module': 'Module',
    'hybrid': 'Hybrid',
    'sensor': 'Sensor',
    'feb': 'Front End Board',
    'cable': 'Cable',
    'optical_board': 'Optical Board',
    'mpod_module': 'MPOD Module',
    'mpod_crate': 'MPOD Crate',
    'flange_board': 'Flange Board',
    'other': 'Other',
}


def create_app(config_class=DevelopmentConfig):
    """
    Create and configure the Flask application

    Args:
        config_class: Configuration class to use (DevelopmentConfig or ProductionConfig)

    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Database setup - create database instance before each request
    @app.before_request
    def setup_db():
        """Set up database connection in Flask request context"""
        if 'db' not in g:
            db_path = app.config.get('DB_PATH')
            data_dir = app.config.get('DATA_DIR')

            if db_path:
                g.db = Database(db_path=db_path, data_dir=data_dir)
            else:
                g.db = get_default_db()

    # Register blueprints
    from .routes.main import main_bp
    from .routes.components import components_bp
    from .routes.tests import tests_bp
    from .routes.files import files_bp
    from .routes.upload import upload_bp
    from .routes.reports import reports_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(components_bp, url_prefix='/components')
    app.register_blueprint(tests_bp, url_prefix='/tests')
    app.register_blueprint(files_bp, url_prefix='/files')
    app.register_blueprint(upload_bp, url_prefix='/upload')
    app.register_blueprint(reports_bp, url_prefix='/reports')

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        """Handle 404 errors"""
        return render_template('errors/404.html', error=e), 404

    @app.errorhandler(500)
    def server_error(e):
        """Handle 500 errors"""
        return render_template('errors/500.html', error=e), 500

    # Context processor to make common data available to all templates
    @app.context_processor
    def inject_common_data():
        """Inject commonly used data into template context"""
        return {
            'app_name': 'HPS SVT Tracker',
            'app_version': '0.1.0'
        }

    # Custom Jinja filter for display names
    @app.template_filter('display_type')
    def display_type_filter(type_name):
        """Convert internal component type name to human-readable display name"""
        return COMPONENT_TYPE_DISPLAY_NAMES.get(type_name, type_name)

    @app.template_filter('format_date')
    def format_date_filter(date_str, include_time=True):
        """
        Convert ISO date string to human-readable format.

        Args:
            date_str: ISO format date string (e.g., "2025-01-15T14:26:35")
            include_time: If True, include time portion (default True)

        Returns:
            Formatted string like "January 15th, 2025 14:26:35" or "January 15th, 2025"
        """
        if not date_str:
            return 'N/A'

        try:
            # Handle both "T" separator and space separator
            date_str = str(date_str).replace('T', ' ')
            # Parse the date string (handle with or without microseconds)
            if '.' in date_str:
                dt = datetime.strptime(date_str[:26], '%Y-%m-%d %H:%M:%S.%f')
            else:
                dt = datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')

            day = dt.day
            suffix = _ordinal_suffix(day)

            if include_time:
                return dt.strftime(f'%B {day}{suffix}, %Y %H:%M:%S')
            else:
                return dt.strftime(f'%B {day}{suffix}, %Y')
        except (ValueError, TypeError):
            # Return original if parsing fails
            return date_str

    return app
