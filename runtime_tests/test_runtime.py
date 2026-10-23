import os
from uuid import uuid4

import psycopg
import pytest
from platform_backend_core import Database, MigrationRunner
from platform_backend_core.testing import temporary_database

from platform_security.migrations import MIGRATIONS
from platform_security.store import Conflict, EnvironmentResolver, SecurityStore


@pytest.fixture
def database():
    dsn=os.environ.get('PLATFORM_TEST_DSN')
    if not dsn: pytest.skip('explicit disposable PostgreSQL DSN required')
    with temporary_database(dsn,prefix='sec_') as temp:
        MigrationRunner(temp.admin_dsn,namespace='security').apply(MIGRATIONS)
        temp.grant_schema('public')
        db=Database(temp.runtime_dsn)
        yield db,temp
        db.close()

def test_reference_only_and_unknown_resolution(database):
    db,_=database;s=SecurityStore(db);a,b=uuid4(),uuid4()
    row=s.put_reference(a,'mail','env','MAIL_TOKEN','outbound mail',None)
    assert row['reference']=='MAIL_TOKEN' and set(row)=={'name','provider','reference','purpose','rotated_at'}
    assert s.list_references(b)==[]
    for reference in ['../../.env','sk-proj-secret','https://host/token','TOKEN\nBAD']:
        with pytest.raises(ValueError):s.put_reference(a,'bad','env',reference,'purpose',None)
    with pytest.raises(ValueError):s.put_reference(a,'bad','file','TOKEN','purpose',None)
    r=EnvironmentResolver({'MAIL_TOKEN':'synthetic-fixture'})
    assert r.resolve('MAIL_TOKEN')=='synthetic-fixture'
    with pytest.raises(KeyError):r.resolve('UNKNOWN')

def test_audit_append_idempotent_and_immutable(database):
    db,temp=database;s=SecurityStore(db);w,actor=uuid4(),uuid4()
    first=s.append(w,actor,'key-1','reference.created','mail')
    assert s.append(w,actor,'key-1','reference.created','mail')==first
    with pytest.raises(Conflict):s.append(w,actor,'key-1','reference.deleted','mail')
    assert len(s.list_audit(w))==1 and s.list_audit(uuid4())==[]
    with db.transaction(w) as c:
        with pytest.raises(psycopg.Error):c.execute('UPDATE security_audit SET action=action')
    with db.transaction(w) as c:
        with pytest.raises(psycopg.Error):c.execute('DELETE FROM security_audit')
    assert s.list_audit(w)[0]['actor']==actor

def test_reference_and_audit_force_rls_reject_foreign_inserts(database):
    import psycopg
    db,_=database;workspace=uuid4()
    with db.transaction(workspace) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("INSERT INTO secret_references VALUES (%s,'foreign','env','TOKEN','purpose',NULL)",(uuid4(),))
    with db.transaction(workspace) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("INSERT INTO security_audit(workspace_id,id,actor,event_key,fingerprint,action,target) VALUES (%s,%s,%s,'foreign','fixture','test.created','fixture')",(uuid4(),uuid4(),uuid4()))

def test_audit_concurrent_dedupe_is_atomic(database):
    from concurrent.futures import ThreadPoolExecutor
    db,_=database;workspace,actor=uuid4(),uuid4();s=SecurityStore(db)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(lambda _:s.append(workspace,actor,'concurrent','fixture.created','fixture'),range(4)))
    assert len({r['id'] for r in rows})==1 and len(s.list_audit(workspace))==1
