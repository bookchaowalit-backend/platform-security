from datetime import datetime
from uuid import UUID
from fastapi import Depends,Header,Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field
from platform_backend_core import create_app as base_app,require_scope
from .store import SecurityStore,Conflict
class Reference(BaseModel):
    model_config=ConfigDict(extra='forbid')
    provider:str=Field(max_length=8)
    reference:str=Field(max_length=200)
    purpose:str=Field(max_length=160)
    rotated_at:datetime|None=None
class Audit(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:str=Field(max_length=64)
    target:str=Field(max_length=64)
def create_app(database,verifier):
    app=base_app('security',database,verifier,max_body_bytes=8192);store=SecurityStore(database)
    app.state.readiness_checks['security_schema_permissions']=store.ready
    @app.exception_handler(ValueError)
    async def invalid(request,exc):return JSONResponse({'detail':'Invalid metadata'},422)
    @app.exception_handler(Conflict)
    async def conflict(request,exc):return JSONResponse({'detail':'Idempotency conflict'},409)
    @app.put('/v1/secret-references/{name}')
    def put(name:str,body:Reference,p=Depends(require_scope('references:write'))):return store.put_reference(p.workspace,name,body.provider,body.reference,body.purpose,body.rotated_at)
    @app.get('/v1/secret-references')
    def refs(limit:int=Query(100,ge=1,le=100),after:str=Query('',max_length=64),p=Depends(require_scope('references:read'))):return store.list_references(p.workspace,limit,after)
    @app.post('/v1/audit')
    def append(body:Audit,key:str=Header(alias='Idempotency-Key',max_length=128),p=Depends(require_scope('audit:write'))):return store.append(p.workspace,p.actor,key,body.action,body.target)
    @app.get('/v1/audit')
    def audit(limit:int=Query(100,ge=1,le=100),after:UUID|None=None,p=Depends(require_scope('audit:read'))):return store.list_audit(p.workspace,limit,after)
    return app
