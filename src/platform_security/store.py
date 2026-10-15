import hashlib
import json
import re
from datetime import datetime
from uuid import UUID,uuid4
from psycopg.rows import dict_row
from .migrations import MIGRATIONS
class Conflict(Exception):pass

def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z][a-z0-9_.-]{0,63}',value):raise ValueError('Invalid identifier')
    return value

def reference(provider,value):
    patterns={'env':r'[A-Z][A-Z0-9_]{0,127}','vault':r'[a-z][a-z0-9_/-]{0,199}','aws':r'[a-z][a-z0-9_/-]{0,199}'}
    if provider not in patterns or not isinstance(value,str) or not re.fullmatch(patterns[provider],value) or '..' in value:raise ValueError('Invalid reference')
    return value

class EnvironmentResolver:
    """Explicit application-only mapping. Never exposed by an HTTP route."""
    def __init__(self,allowed):self._allowed=dict(allowed)
    def resolve(self,name):
        reference('env',name)
        return self._allowed[name]

class SecurityStore:
    def __init__(self,database):self.db=database
    def put_reference(self,workspace,name,provider,ref,purpose,rotated_at):
        identifier(name);reference(provider,ref)
        if not isinstance(purpose,str) or not re.fullmatch(r'[A-Za-z0-9 .,()_-]{1,160}',purpose):raise ValueError('Invalid purpose')
        if rotated_at is not None and (not isinstance(rotated_at,datetime) or rotated_at.tzinfo is None):raise ValueError('Invalid rotation')
        with self.db.transaction(workspace) as c:
            c.row_factory=dict_row
            return c.execute('INSERT INTO secret_references VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(workspace_id,name) DO UPDATE SET provider=EXCLUDED.provider,reference=EXCLUDED.reference,purpose=EXCLUDED.purpose,rotated_at=EXCLUDED.rotated_at RETURNING name,provider,reference,purpose,rotated_at',(workspace,name,provider,ref,purpose,rotated_at)).fetchone()
    def list_references(self,workspace,limit=100,after=''):
        if not 1<=limit<=100:raise ValueError('Invalid limit')
        with self.db.transaction(workspace) as c:
            c.row_factory=dict_row
            return c.execute('SELECT name,provider,reference,purpose,rotated_at FROM secret_references WHERE name>%s ORDER BY name LIMIT %s',(after,limit)).fetchall()
    def append(self,workspace,actor,key,action,target):
        identifier(action);identifier(target)
        if not isinstance(actor,UUID) or not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',key):raise ValueError('Invalid event')
        fingerprint=hashlib.sha256(json.dumps([str(actor),action,target],separators=(',',':')).encode()).hexdigest()
        with self.db.transaction(workspace) as c:
            c.row_factory=dict_row
            c.execute('INSERT INTO security_audit(workspace_id,id,actor,event_key,fingerprint,action,target) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(workspace_id,event_key) DO NOTHING',(workspace,uuid4(),actor,key,fingerprint,action,target))
            row=c.execute('SELECT id,actor,action,target,created_at,fingerprint FROM security_audit WHERE event_key=%s',(key,)).fetchone()
            if row.pop('fingerprint')!=fingerprint:raise Conflict()
            return row
    def list_audit(self,workspace,limit=100,after=None):
        if not 1<=limit<=100:raise ValueError('Invalid limit')
        with self.db.transaction(workspace) as c:
            c.row_factory=dict_row
            return c.execute('SELECT id,actor,action,target,created_at FROM security_audit WHERE (%s::uuid IS NULL OR id>%s::uuid) ORDER BY id LIMIT %s',(after,after,limit)).fetchall()
    def ready(self):
        with self.db.transaction(UUID(int=0)) as c:
            # Check every operation individually: a comma privilege list means ANY.
            required_permissions=c.execute("""SELECT has_schema_privilege(current_user,'public','USAGE')
                AND has_table_privilege(current_user,'public.platform_schema_migrations','SELECT')
                AND has_table_privilege(current_user,'public.secret_references','SELECT')
                AND has_table_privilege(current_user,'public.secret_references','INSERT')
                AND has_table_privilege(current_user,'public.secret_references','UPDATE')
                AND has_table_privilege(current_user,'public.security_audit','SELECT')
                AND has_table_privilege(current_user,'public.security_audit','INSERT')""").fetchone()[0]
            if not required_permissions:return False
            history=c.execute('SELECT version,checksum FROM platform_schema_migrations WHERE namespace=%s ORDER BY version',('security',)).fetchall()
            if history!=[(m.version,m.checksum) for m in MIGRATIONS]:return False
            c.execute('SELECT name,provider,reference,purpose,rotated_at FROM secret_references LIMIT 0')
            c.execute('SELECT id,actor,event_key,action,target FROM security_audit LIMIT 0')
            rows=c.execute("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid IN(to_regclass('secret_references'),to_regclass('security_audit'))").fetchall()
            immutable=c.execute("SELECT 1 FROM pg_trigger WHERE tgrelid=to_regclass('security_audit') AND tgname='immutable_audit' AND tgenabled='O'").fetchone()
            permissions=c.execute("SELECT has_table_privilege(current_user,'security_audit','UPDATE') OR has_table_privilege(current_user,'security_audit','DELETE') OR has_table_privilege(current_user,'security_audit','TRUNCATE')").fetchone()
            return len(rows)==2 and all(x[0] for x in rows) and bool(immutable) and not permissions[0]
