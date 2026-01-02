"""
Flask application factory for HPS SVT Tracker web interface
"""
from flask import Flask, g, render_template
from hps_svt_tracker.database import Database, get_default_db
from .config import DevelopmentConfig


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

    app.register_blueprint(main_bp)
    app.register_blueprint(components_bp, url_prefix='/components')
    app.register_blueprint(tests_bp, url_prefix='/tests')
    app.register_blueprint(files_bp, url_prefix='/files')

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

    return app
