"""Only domain validation maps to 422; any other ValueError is a server bug (redacted 500).

Offline: the store is replaced or fails before touching the database.
"""
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_http import auth

from platform_security import store as store_module
from platform_security.app import create_app
from platform_security.store import InvalidInput, SecurityStore


class _NoDatabase:
    def ready(self):
        return False

    def close(self):
        pass

    def transaction(self, workspace):
        raise AssertionError('database must not be reached')


@pytest.fixture
def client():
    verifier, headers = auth()
    with TestClient(create_app(_NoDatabase(), verifier)) as c:
        yield c, headers('references:read references:write audit:read audit:write', uuid4())


def _store():
    return SecurityStore(_NoDatabase())


def test_invalid_input_is_a_value_error():
    assert issubclass(InvalidInput, ValueError)


@pytest.mark.parametrize('call', [
    lambda: store_module.identifier('Bad Name'),
    lambda: store_module.reference('env', '../TOKEN'),
    lambda: store_module.reference('file', 'TOKEN'),
    lambda: _store().put_reference(uuid4(), 'ok', 'env', 'TOKEN', 'bad\npurpose', None),
    lambda: _store().put_reference(uuid4(), 'ok', 'env', 'TOKEN', 'purpose', datetime(2026, 10, 29)),
    lambda: _store().list_references(uuid4(), 0),
    lambda: _store().append(uuid4(), uuid4(), 'bad key!', 'read', 'secret'),
    lambda: _store().list_audit(uuid4(), 101),
])
def test_store_validation_raises_invalid_input(call):
    with pytest.raises(InvalidInput):
        call()


def test_non_uuid_actor_is_a_server_bug_not_invalid_input():
    # The actor always comes from the verified token; any other value is a programming error.
    with pytest.raises(TypeError):
        _store().append(uuid4(), 'not-a-uuid', 'key', 'read', 'secret')


def test_domain_validation_returns_422(client):
    c, h = client
    body = {'provider': 'env', 'reference': 'TOKEN', 'purpose': 'purpose'}
    response = c.put('/v1/secret-references/Bad', headers=h, json=body)
    assert response.status_code == 422
    assert response.json() == {'detail': 'Invalid metadata'}
    assert c.put('/v1/secret-references/ok', headers=h, json=body | {'provider': 'file'}).status_code == 422
    assert c.post('/v1/audit', headers=h, json={'action': 'Bad Action', 'target': 'secret'}).status_code == 422


def test_unexpected_value_error_is_redacted_500(client, monkeypatch):
    def broken(self, workspace, limit=100, after=''):
        raise ValueError('secret-bearing internal detail')

    monkeypatch.setattr(SecurityStore, 'list_references', broken)
    c, h = client
    response = c.get('/v1/secret-references', headers=h)
    assert response.status_code == 500
    assert 'secret-bearing' not in response.text
    assert response.json() == {'detail': 'internal server error'}
