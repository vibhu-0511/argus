"""The one typed error of the workbench: {"error": {"code": "<snake_case>", "field": "<name or null>", "message": "..."}}.

The store raises it, routes raise it, `install_handlers` turns it (and the framework's own 404, 405 and
validation errors) into that JSON body. Messages are fixed text or contain only values the caller already
sent; they never hold a token, a path outside the store, or a stack trace.
"""

from __future__ import annotations

import re

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

_CODE = re.compile(r"[a-z][a-z0-9_]*")


class WorkbenchError(Exception):
    """A refusal with a stable code. `field` names the form field or file the person should fix, or None."""

    def __init__(self, code: str, message: str, field: str | None = None, status: int = 400):
        assert _CODE.fullmatch(code), f"error code must be snake_case: {code!r}"
        super().__init__(message)
        self.code, self.message, self.field, self.status = code, message, field, status

    def body(self) -> dict:
        return {"error": {"code": self.code, "field": self.field, "message": self.message}}


def error_response(err: WorkbenchError) -> JSONResponse:
    return JSONResponse(err.body(), status_code=err.status)


def from_validation(exc: ValidationError, code: str, what: str) -> WorkbenchError:
    """A pydantic failure as a typed error naming the first bad field. Input values are not echoed."""
    first = exc.errors(include_input=False, include_url=False, include_context=False)[0]
    field = ".".join(str(p) for p in first["loc"]) or None
    return WorkbenchError(code, f"{what}: {first['msg']}", field=field)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(WorkbenchError)
    async def _workbench(_: Request, exc: WorkbenchError):
        return error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        first = exc.errors()[0]
        loc = [str(p) for p in first["loc"] if p not in ("body", "query", "path", "header")]
        return error_response(WorkbenchError("invalid_request", str(first["msg"]), field=".".join(loc) or None, status=422))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return error_response(WorkbenchError(code, str(exc.detail), status=exc.status_code))
