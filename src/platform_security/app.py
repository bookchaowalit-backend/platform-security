from datetime import datetime
from uuid import UUID

from fastapi import Depends, Header, Query
from fastapi.responses import JSONResponse
from platform_backend_core import create_app as base_app
from platform_backend_core import require_scope
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware import Middleware

from ._edge import EdgeGuard
from ._sentry import CaptureErrors
from .store import Conflict, InvalidInput, SecurityStore

# Scope dependencies built once at import (Ruff B008: no calls in argument defaults).
REFERENCES_READ=Depends(require_scope('references:read'))
REFERENCES_WRITE=Depends(require_scope('references:write'))
AUDIT_READ=Depends(require_scope('audit:read'))
AUDIT_WRITE=Depends(require_scope('audit:write'))
_PRIVATE_PATHS={'/openapi.json','/docs','/docs/oauth2-redirect','/redoc','/metrics'}

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
    # Nothing on the public URL describes the API or its traffic: the schema lives in contracts/.
    app.router.routes[:]=[r for r in app.router.routes if getattr(r,'path',None) not in _PRIVATE_PATHS]
    app.openapi_url=app.docs_url=app.redoc_url=None
    # add_middleware = outermost, so throttled clients never reach token verification.
    app.add_middleware(EdgeGuard)
    # Last in the list = innermost: inside the core boundary that turns errors into a 500.
    app.user_middleware.append(Middleware(CaptureErrors))
    # Only the domain InvalidInput is a client error; any other exception (an unexpected
    # ValueError included) is a server bug and becomes the shared core's redacted 500.
    @app.exception_handler(InvalidInput)
    async def invalid(request,exc):return JSONResponse({'detail':'Invalid metadata'},422)
    @app.exception_handler(Conflict)
    async def conflict(request,exc):return JSONResponse({'detail':'Idempotency conflict'},409)
    @app.put('/v1/secret-references/{name}')
    def put(name:str,body:Reference,p=REFERENCES_WRITE):return store.put_reference(p.workspace,name,body.provider,body.reference,body.purpose,body.rotated_at)
    @app.get('/v1/secret-references')
    def refs(limit:int=Query(100,ge=1,le=100),after:str=Query('',max_length=64),p=REFERENCES_READ):return store.list_references(p.workspace,limit,after)
    @app.post('/v1/audit')
    def append(body:Audit,key:str=Header(alias='Idempotency-Key',max_length=128),p=AUDIT_WRITE):return store.append(p.workspace,p.actor,key,body.action,body.target)
    @app.get('/v1/audit')
    def audit(limit:int=Query(100,ge=1,le=100),after:UUID|None=None,p=AUDIT_READ):return store.list_audit(p.workspace,limit,after)
    return app
