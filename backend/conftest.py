import itertools

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Faculty, User

_counter = itertools.count(1)


@pytest.fixture(autouse=True)
def seeded(db):
    call_command("seed", verbosity=0)


@pytest.fixture
def faculty(db):
    return Faculty.objects.create(name="Kompyuter injiniringi", short_name="KI")


@pytest.fixture
def make_user(db, faculty):
    def factory(role=User.Role.STUDENT, **kwargs):
        n = next(_counter)
        kwargs.setdefault("username", f"user{n}")
        kwargs.setdefault("first_name", f"Ism{n}")
        kwargs.setdefault("faculty", faculty)
        kwargs.setdefault("course", 2)
        kwargs.setdefault("onboarded_at", timezone.now())
        return User.objects.create_user(role=role, password="pass12345", **kwargs)

    return factory


@pytest.fixture
def student(make_user):
    return make_user()


@pytest.fixture
def teacher(make_user):
    return make_user(role=User.Role.TEACHER)


@pytest.fixture
def api():
    def factory(user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    return factory
