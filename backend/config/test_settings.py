import os
import tempfile

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-that-is-long-enough-for-hs256")

from .settings import *  # noqa: E402,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MEDIA_ROOT = tempfile.mkdtemp(prefix="talenthub-media-")
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}  # noqa: F405
