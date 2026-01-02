"""
Flask configuration for HPS SVT Tracker web interface
"""
import os


class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-CHANGE-IN-PRODUCTION'

    # Database configuration
    DB_PATH = os.environ.get('SVT_DB_PATH')  # None = use default ~/.hps_svt_tracker/
    DATA_DIR = os.environ.get('SVT_DATA_DIR')

    # Security
    SESSION_COOKIE_SECURE = True  # HTTPS only
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Pagination
    ITEMS_PER_PAGE = 50


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # Allow HTTP in dev
    TEMPLATES_AUTO_RELOAD = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False

    @property
    def SECRET_KEY(self):
        """Force SECRET_KEY from environment in production"""
        key = os.environ.get('SECRET_KEY')
        if not key:
            raise ValueError("SECRET_KEY must be set in production!")
        return key


# Configuration dictionary for easy access
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
