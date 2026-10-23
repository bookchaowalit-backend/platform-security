import os
import time
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from platform_backend_core import Database, MigrationRunner, TokenVerifier
from platform_backend_core.testing import temporary_database

from platform_security.app import create_app
from platform_security.migrations import MIGRATIONS


def auth():
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    verifier=TokenVerifier(issuer='fixture',audience='fixture',public_key=public)
    def headers(scopes,workspace=None,actor=None):
        now=int(time.time())
        token=jwt.encode({'iss':'fixture','aud':'fixture','sub':str(actor or uuid4()),'ws':str(workspace or uuid4()),'iat':now,'exp':now+300,'jti':str(uuid4()),'scope':scopes},key,algorithm='RS256')
        return {'Authorization':'Bearer '+token,'Idempotency-Key':'fixture-key'}
    return verifier,headers

@pytest.fixture
def setup():
    dsn=os.environ.get('PLATFORM_TEST_DSN')
    if not dsn:pytest.skip('explicit PostgreSQL DSN required')
    with temporary_database(dsn,prefix='sech_') as temp:
        verifier,headers=auth()
        db=Database(temp.runtime_dsn)
        yield temp,db,verifier,headers
        db.close()

def test_missing_schema_is_not_ready(setup):
    _temp,db,verifier,_headers=setup
    with TestClient(create_app(db,verifier)) as c:
        assert c.get('/readyz').status_code==503
        assert c.get('/healthz').status_code==200

def test_secret_value_rejected_audit_identity_bound_and_permissions(setup):
    import psycopg
    from psycopg import sql
    temp,db,verifier,headers=setup
    MigrationRunner(temp.admin_dsn,namespace='security').apply(MIGRATIONS);temp.grant_schema('public')
    with TestClient(create_app(db,verifier)) as c:
        assert c.get('/readyz').status_code==503
        with psycopg.connect(temp.admin_dsn) as admin:
            admin.execute(sql.SQL('REVOKE UPDATE,DELETE,TRUNCATE ON security_audit FROM {}').format(sql.Identifier(temp.runtime_role)))
        assert c.get('/readyz').status_code==200
        w,actor=uuid4(),uuid4();h=headers('references:read references:write audit:read audit:write',w,actor)
        body={'provider':'env','reference':'MAIL_TOKEN','purpose':'outbound','value':'SYNTHETIC_VALUE'}
        response=c.put('/v1/secret-references/mail',headers=h,json=body)
        assert response.status_code==422 and 'SYNTHETIC_VALUE' not in response.text
        del body['value'];assert c.put('/v1/secret-references/mail',headers=h,json=body).status_code==200
        assert c.get('/v1/secret-references',headers=headers('references:read')).json()==[]
        assert c.post('/v1/audit',headers=h,json={'action':'reference.created','target':'mail','actor':str(uuid4())}).status_code==422
        response=c.post('/v1/audit',headers=h,json={'action':'reference.created','target':'mail'})
        assert response.status_code==200 and response.json()['actor']==str(actor)
        assert c.post('/v1/audit',headers=h,json={'action':'reference.deleted','target':'mail'}).status_code==409
        assert c.get('/v1/audit',headers=headers('')).status_code==403


def test_applied_migration_checksum_required(setup):
    import psycopg
    temp,db,verifier,_headers=setup
    MigrationRunner(temp.admin_dsn,namespace='security').apply(MIGRATIONS);temp.grant_schema('public')
    with psycopg.connect(temp.admin_dsn) as admin:
        admin.execute("DELETE FROM platform_schema_migrations WHERE namespace=%s",('security',))
    with TestClient(create_app(db,verifier)) as c:
        assert c.get('/readyz').status_code==503


@pytest.mark.parametrize('kind,target,privilege',[('TABLE', 'secret_references', 'SELECT'), ('TABLE', 'secret_references', 'INSERT'), ('TABLE', 'secret_references', 'UPDATE'), ('TABLE', 'security_audit', 'SELECT'), ('TABLE', 'security_audit', 'INSERT'), ('SCHEMA', 'public', 'USAGE'), ('TABLE', 'platform_schema_migrations', 'SELECT')])
def test_readiness_requires_each_effective_privilege(setup,kind,target,privilege):
    import psycopg
    from psycopg import sql
    temp,db,verifier,_headers=setup
    MigrationRunner(temp.admin_dsn,namespace='security').apply(MIGRATIONS)
    temp.grant_schema('public')
    with psycopg.connect(temp.admin_dsn) as admin:
        admin.execute('REVOKE USAGE ON SCHEMA public FROM PUBLIC')
        admin.execute(sql.SQL('REVOKE UPDATE,DELETE,TRUNCATE ON security_audit FROM {}').format(sql.Identifier(temp.runtime_role)))
    with TestClient(create_app(db,verifier)) as c:
        assert c.get('/readyz').status_code==200
        with psycopg.connect(temp.admin_dsn) as admin:
            admin.execute(sql.SQL('REVOKE {} ON {} {} FROM {}').format(sql.SQL(privilege),sql.SQL(kind),sql.Identifier(target),sql.Identifier(temp.runtime_role)))
        assert c.get('/readyz').status_code==503
        with psycopg.connect(temp.admin_dsn) as admin:
            admin.execute(sql.SQL('GRANT {} ON {} {} TO {}').format(sql.SQL(privilege),sql.SQL(kind),sql.Identifier(target),sql.Identifier(temp.runtime_role)))
        assert c.get('/readyz').status_code==200

@pytest.mark.parametrize('privilege',['UPDATE','DELETE','TRUNCATE'])
def test_readiness_rejects_each_forbidden_audit_privilege(setup,privilege):
    import psycopg
    from psycopg import sql
    temp,db,verifier,_headers=setup
    MigrationRunner(temp.admin_dsn,namespace='security').apply(MIGRATIONS)
    temp.grant_schema('public')
    with psycopg.connect(temp.admin_dsn) as admin:
        admin.execute(sql.SQL('REVOKE UPDATE,DELETE,TRUNCATE ON security_audit FROM {}').format(sql.Identifier(temp.runtime_role)))
    with TestClient(create_app(db,verifier)) as c:
        assert c.get('/readyz').status_code==200
        with psycopg.connect(temp.admin_dsn) as admin:
            admin.execute(sql.SQL('GRANT {} ON security_audit TO {}').format(sql.SQL(privilege),sql.Identifier(temp.runtime_role)))
        assert c.get('/readyz').status_code==503
        with psycopg.connect(temp.admin_dsn) as admin:
            admin.execute(sql.SQL('REVOKE {} ON security_audit FROM {}').format(sql.SQL(privilege),sql.Identifier(temp.runtime_role)))
        assert c.get('/readyz').status_code==200
