import os

from .base import *  # noqa: F401,F403

DEBUG = True

# Locally, runserver serves static files straight from static/ and doesn't
# understand WhiteNoise's hashed filenames, so this stays off in dev.
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "False") == "True"
