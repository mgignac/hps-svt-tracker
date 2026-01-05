"""
Flask application factory for HPS SVT Tracker web interface
"""
from flask import Flask, g, render_template
from hps_svt_tracker.database import Database, get_default_db
from .config import DevelopmentConfig

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

    return app
