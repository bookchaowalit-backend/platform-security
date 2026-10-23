"""Explicit service lifecycle; migrations never run at API startup."""
import argparse
import os

from platform_backend_core import Database, MigrationRunner, TokenVerifier

from .app import create_app
from .migrations import MIGRATIONS


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['serve','migrate']);args=p.parse_args()
    try:
        if args.command=='migrate':
            MigrationRunner(os.environ['DATABASE_URL'],namespace='security').apply(MIGRATIONS)
            return
        verifier=TokenVerifier(issuer=os.environ['JWT_ISSUER'],audience=os.environ['JWT_AUDIENCE'],public_key=os.environ.get('JWT_PUBLIC_KEY'),jwks_url=os.environ.get('JWT_JWKS_URL'))
        app=create_app(Database(os.environ['DATABASE_URL']),verifier)
        import uvicorn
        uvicorn.run(app,host='0.0.0.0',port=int(os.environ.get('PORT','8080')),access_log=False,limit_concurrency=100)
    except Exception:
        raise SystemExit('Service configuration or dependency unavailable') from None
if __name__=='__main__':main()
