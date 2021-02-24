from .models import State
import pytest


@pytest.mark.django_db
def test_states_were_populated():
    assert State.objects.count() == 50
