"""Standard API errors (rules/03): 400 rule broken, 401 not signed in, 403 role or membership,
404 not found or not visible, 422 invalid input, 423 date locked."""
from fastapi import HTTPException


def bad_request(msg: str) -> HTTPException:
    return HTTPException(400, msg)


def unauthorized(msg: str = "Please sign in") -> HTTPException:
    return HTTPException(401, msg)


def forbidden(msg: str = "Not allowed for your role") -> HTTPException:
    return HTTPException(403, msg)


def not_found(msg: str = "Not found") -> HTTPException:
    return HTTPException(404, msg)


def unprocessable(msg: str) -> HTTPException:
    return HTTPException(422, msg)


def locked(msg: str = "This day is locked. Request an unlock first.") -> HTTPException:
    return HTTPException(423, msg)
