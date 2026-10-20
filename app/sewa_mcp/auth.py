# mcp/auth.py

import os
import jwt

from mcp.server.fastmcp import Context


ISSUER = os.environ.get(
    "PUBLIC_BASE_URL",
    "http://localhost:8000"
).rstrip("/")


def verify_token(
    ctx: Context,
    required_scope: str,
    required_role: str,
    expected_audience: str,
):
    headers = ctx.headers or {}

    authorization = headers.get("authorization", "")

    if not authorization.startswith("Bearer "):
        raise PermissionError("Missing Bearer token")

    token = authorization[7:].strip()

    if not token:
        raise PermissionError("Empty Bearer token")

    try:
        jwks_client = jwt.PyJWKClient(
            f"{ISSUER}/.well-known/jwks.json"
        )

        signing_key = jwks_client.get_signing_key_from_jwt(token)

        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=expected_audience,
            issuer=ISSUER,
        )

    except jwt.PyJWTError as exc:
        raise PermissionError(
            "Invalid or expired access token"
        ) from exc

    scope = claims.get("scope", "")
    role = claims.get("role")

    if required_scope not in scope.split():
        raise PermissionError(
            f"Missing required scope: {required_scope}"
        )

    if role != required_role:
        raise PermissionError(
            f"Invalid role: expected {required_role}"
        )

    return claims


def require_citizen(ctx: Context, expected_audience: str):
    return verify_token(
        ctx,
        "citizen",
        "citizen",
        expected_audience,
    )


def require_officer(ctx: Context, expected_audience: str):
    return verify_token(
        ctx,
        "officer",
        "officer",
        expected_audience,
    )


def citizen_mobile(claims):
    subject = claims.get("sub", "")

    if not subject.startswith("citizen:"):
        raise PermissionError("Invalid citizen subject")

    return subject[len("citizen:"):]


def officer_username(claims):
    subject = claims.get("sub", "")

    if not subject.startswith("officer:"):
        raise PermissionError("Invalid officer subject")

    return subject[len("officer:"):]