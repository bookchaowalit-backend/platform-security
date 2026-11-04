"""Edge hardening: no public schema or metrics, and per-client rate limits that count failed auth.

Offline: the database is never reached.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_http import auth

from platform_security import _edge
from platform_security.app import create_app


class _NoDatabase:
    def ready(self):
        return False

    def close(self):
        pass


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    c = _Clock()
    monkeypatch.setattr(_edge, '_now', c)
    return c


@pytest.fixture
def client(clock):
    verifier, headers = auth()
    with TestClient(create_app(_NoDatabase(), verifier)) as c:
        yield c, headers


@pytest.mark.parametrize('path', ['/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc', '/metrics'])
def test_schema_and_metrics_are_not_public(client, path):
    c, _ = client
    assert c.get(path).status_code == 404


def test_health_stays_public(client):
    c, _ = client
    assert c.get('/healthz').status_code == 200


def test_failed_auth_is_throttled_per_client(client, clock):
    c, _ = client
    ip = {'X-Real-IP': '203.0.113.7'}
    bad = {**ip, 'Authorization': 'Bearer not-a-token'}
    for _ in range(_edge.FAILURE_BURST):
        assert c.get('/v1/audit', headers=bad).status_code == 401
    blocked = c.get('/v1/audit', headers=bad)
    assert blocked.status_code == 429 and int(blocked.headers['retry-after']) >= 1
    # Once locked out, even a valid request from the same client waits.
    assert c.get('/healthz', headers=ip).status_code == 429
    # Another client is unaffected.
    assert c.get('/v1/audit', headers={'X-Real-IP': '198.51.100.9', 'Authorization': 'Bearer x'}).status_code == 401
    # The failure budget refills over time.
    clock.now += _edge.FAILURE_REFILL_SECONDS
    assert c.get('/v1/audit', headers=bad).status_code == 401


def test_request_rate_is_bounded_per_client(client, clock):
    c, _ = client
    ip = {'X-Real-IP': '203.0.113.8'}
    for _ in range(_edge.REQUEST_BURST):
        assert c.get('/healthz', headers=ip).status_code == 200
    assert c.get('/healthz', headers=ip).status_code == 429
    clock.now += 1 / _edge.REQUEST_RATE
    assert c.get('/healthz', headers=ip).status_code == 200


def test_successful_auth_does_not_spend_the_failure_budget(client):
    c, headers = client
    h = {**headers('audit:read', uuid4()), 'X-Real-IP': '203.0.113.9'}
    # Store is unreachable, so the call fails server-side, but auth passed: not a failure.
    for _ in range(_edge.FAILURE_BURST + 2):
        assert c.get('/v1/audit', headers=h).status_code != 429


def test_client_table_is_bounded(clock):
    limiter = _edge.Limiter()
    for i in range(_edge.MAX_CLIENTS + 50):
        limiter.admit(f'10.0.{i // 256}.{i % 256}')
    assert len(limiter.clients) == _edge.MAX_CLIENTS
