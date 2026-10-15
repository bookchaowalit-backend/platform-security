from platform_backend_core import Migration
MIGRATIONS=[Migration('0001',"""
CREATE TABLE secret_references(workspace_id uuid NOT NULL,name text NOT NULL,provider text NOT NULL CHECK(provider IN ('env','vault','aws')),reference text NOT NULL,purpose text NOT NULL,rotated_at timestamptz,PRIMARY KEY(workspace_id,name));
CREATE TABLE security_audit(workspace_id uuid NOT NULL,id uuid NOT NULL,actor uuid NOT NULL,event_key text NOT NULL,fingerprint text NOT NULL,action text NOT NULL,target text NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),PRIMARY KEY(workspace_id,id),UNIQUE(workspace_id,event_key));
CREATE INDEX ON security_audit(workspace_id,created_at,id);
ALTER TABLE secret_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE secret_references FORCE ROW LEVEL SECURITY;
CREATE POLICY workspace ON secret_references USING(workspace_id=nullif(current_setting('app.workspace_id',true),'')::uuid) WITH CHECK(workspace_id=nullif(current_setting('app.workspace_id',true),'')::uuid);
ALTER TABLE security_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE security_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY workspace ON security_audit USING(workspace_id=nullif(current_setting('app.workspace_id',true),'')::uuid) WITH CHECK(workspace_id=nullif(current_setting('app.workspace_id',true),'')::uuid);
CREATE FUNCTION reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Audit is append only'; END; $$;
CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE OR TRUNCATE ON security_audit FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_mutation();
REVOKE ALL ON security_audit FROM PUBLIC;
""")]
