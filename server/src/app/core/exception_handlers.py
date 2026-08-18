from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException


async def handle_app_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppException)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, handle_app_exception)
