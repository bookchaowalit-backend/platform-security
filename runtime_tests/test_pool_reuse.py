"""Real single-connection pool regression after successful and conflicting traffic."""
import os
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from platform_backend_core import Database, MigrationRunner
from platform_backend_core.testing import temporary_database
from psycopg import sql
from test_http import auth

from platform_security.app import create_app
from platform_security.migrations import MIGRATIONS
from platform_security.store import Conflict, SecurityStore


@pytest.fixture
def pooled():
    with temporary_database(os.environ['PLATFORM_TEST_DSN'],prefix='reuse_secu_') as temp:
        MigrationRunner(temp.admin_dsn,namespace='security').apply(MIGRATIONS)
        temp.grant_schema()
        with psycopg.connect(temp.admin_dsn) as conn:
            conn.execute(sql.SQL('REVOKE UPDATE,DELETE,TRUNCATE ON security_audit FROM {}').format(sql.Identifier(temp.runtime_role)))
        database=Database(temp.runtime_dsn,min_size=1,max_size=1)
        verifier,headers=auth()
        try:
            yield database,verifier,headers
        finally:
            database.close()


def assert_repeated_ready(database,store):
    for _ in range(3):
        assert database.ready() is True
        assert store.ready() is True


def test_store_pool_reuse_after_audit_conflict_and_isolation(pooled):
    database,_,_=pooled
    store=SecurityStore(database);workspace,foreign,actor=uuid4(),uuid4(),uuid4()
    assert_repeated_ready(database,store)
    store.put_reference(workspace,'fixture','env','FIXTURE_REFERENCE','Fixture metadata',None)
    assert len(store.list_references(workspace))==1 and store.list_references(foreign)==[]
    row=store.append(workspace,actor,'fixture','reference.created','fixture')
    assert store.append(workspace,actor,'fixture','reference.created','fixture')['id']==row['id']
    with pytest.raises(Conflict):store.append(workspace,actor,'fixture','reference.deleted','fixture')
    assert len(store.list_audit(workspace))==1 and store.list_audit(foreign)==[]
    with pytest.raises(psycopg.errors.InsufficientPrivilege), database.transaction(workspace) as conn:
        conn.execute('UPDATE security_audit SET action=action')
    assert_repeated_ready(database,store)


def test_http_pool_reuse_after_success_and_conflict(pooled):
    database,verifier,headers=pooled
    own=headers('references:read references:write audit:read audit:write',uuid4(),uuid4())
    foreign=headers('references:read audit:read',uuid4())
    with TestClient(create_app(database,verifier)) as client:
        assert client.get('/readyz').status_code==200
        body={'provider':'env','reference':'FIXTURE_REFERENCE','purpose':'Fixture metadata'}
        assert client.put('/v1/secret-references/fixture',headers=own,json=body).status_code==200
        assert len(client.get('/v1/secret-references',headers=own).json())==1
        assert client.get('/v1/secret-references',headers=foreign).json()==[]
        event={'action':'reference.created','target':'fixture'}
        assert client.post('/v1/audit',headers=own,json=event).status_code==200
        assert client.post('/v1/audit',headers=own,json=event|{'action':'reference.deleted'}).status_code==409
        assert len(client.get('/v1/audit',headers=own).json())==1
        assert client.get('/v1/audit',headers=foreign).json()==[]
        assert client.put('/v1/secret-references/fixture',headers=own,json=body|{'value':'synthetic'}).status_code==422
        for _ in range(3):
            assert client.get('/readyz').status_code==200
            assert database.ready() is True
