"""API routes. Every module here that has a module-level `router` (APIRouter) is included by `server.create_app`.

Add a file, do not edit server.py. A POST, PUT, PATCH or DELETE route needs no token code of its own: the
middleware in security.py refuses it before the route runs unless the per-start token was sent.
"""
