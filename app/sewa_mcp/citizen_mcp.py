from mcp.server.fastmcp import FastMCP, Context

import os
from datetime import datetime
from sewa_mcp.auth import require_citizen, citizen_mobile
from sewa_mcp.common import (
    get_db,
    validate_application,
    active_application,
    create_application,
    write_audit,
    BLOCKS,
    MIN_AGE,
    SCHEME_DEADLINE,
)


MCP_AUDIENCE = os.environ.get(
    "CITIZEN_MCP_URL",
    "http://localhost:8100"
).rstrip("/")


mcp = FastMCP(
    "Sewa Setu Citizen Assistant",
    stateless_http=True,
    json_response=True,
    host="0.0.0.0",
    port=8100,
)


@mcp.tool()
def check_eligibility(
    ctx: Context,
    applicant_name: str,
    village: str,
    block: str,
    dob: str,
    bank_account: str,
    ifsc: str = "",
    doc_path: str = "",
) -> dict:
    """
    Check whether a citizen's pension application satisfies
    the existing Sewa Setu application rules.
    """

    require_citizen(ctx, MCP_AUDIENCE)

    data = {
        "applicant_name": applicant_name,
        "village": village,
        "block": block,
        "dob": dob,
        "bank_account": bank_account,
        "ifsc": ifsc,
    }

    errors, cleaned = validate_application(
        data,
        doc_path,
    )

    return {
        "eligible": len(errors) == 0,
        "errors": errors,
        "requirements": {
            "minimum_age": MIN_AGE,
            "valid_blocks": BLOCKS,
            "scheme_deadline": SCHEME_DEADLINE.isoformat(),
            "age_proof_required": True,
        },
    }


@mcp.tool()
def apply_for_pension(
    ctx: Context,
    applicant_name: str,
    village: str,
    block: str,
    dob: str,
    bank_account: str,
    ifsc: str,
    doc_path: str,
    gender: str = "",
    marital_status: str = "",
    husband_name: str = "",
) -> dict:
    """
    Submit an Old Age Pension application using the existing
    Sewa Setu application business rules.
    """

    claims = require_citizen(ctx, MCP_AUDIENCE)
    mobile = citizen_mobile(claims)

    data = {
        "applicant_name": applicant_name,
        "village": village,
        "block": block,
        "dob": dob,
        "bank_account": bank_account,
        "ifsc": ifsc,
        "gender": gender,
        "marital_status": marital_status,
        "husband_name": husband_name,
    }

    errors, cleaned = validate_application(
        data,
        doc_path,
    )

    if errors:
        return {
            "success": False,
            "errors": errors,
        }

    conn = get_db()
    cur = conn.cursor()

    try:
        existing = active_application(cur, mobile)

        if existing:
            return {
                "success": False,
                "error": "You already have an active application.",
                "application": {
                    "id": existing[0],
                    "application_no": existing[1],
                    "status": existing[2],
                },
            }

        app_id, application_no = create_application(
            cur,
            mobile,
            cleaned,
        )

        conn.commit()

        return {
            "success": True,
            "application": {
                "id": app_id,
                "application_no": application_no,
                "status": "PENDING",
            },
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


@mcp.tool()
def get_my_application(ctx: Context) -> dict:
    """
    Get the authenticated citizen's most recent pension application.
    """

    claims = require_citizen(ctx, MCP_AUDIENCE)
    mobile = citizen_mobile(claims)

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                id,
                application_no,
                applicant_name,
                mobile,
                dob,
                village,
                block,
                bank_account,
                ifsc,
                status,
                submitted_at,
                decided_at
            FROM applications
            WHERE mobile = %s
            ORDER BY submitted_at DESC
            LIMIT 1
            """,
            (mobile,),
        )

        row = cur.fetchone()

        if not row:
            return {
                "found": False,
                "message": "No pension application found.",
            }

        return {
            "found": True,
            "application": {
                "id": row[0],
                "application_no": row[1],
                "applicant_name": row[2],
                "mobile": row[3],
                "dob": row[4].isoformat() if row[4] else None,
                "village": row[5],
                "block": row[6],
                "bank_account": row[7],
                "ifsc": row[8],
                "status": row[9],
                "submitted_at": row[10].isoformat()
                if row[10]
                else None,
                "decided_at": row[11].isoformat()
                if row[11]
                else None,
            },
        }

    finally:
        cur.close()
        conn.close()


@mcp.tool()
def withdraw_application(
    ctx: Context,
    application_id: int,
) -> dict:
    """
    Withdraw the authenticated citizen's pending application.
    """

    claims = require_citizen(ctx, MCP_AUDIENCE)
    mobile = citizen_mobile(claims)

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE applications
            SET
                status = 'WITHDRAWN',
                decided_at = %s,
                decided_by = 'APPLICANT'
            WHERE id = %s
              AND mobile = %s
              AND status = 'PENDING'
            RETURNING application_no
            """,
            (
                datetime.now(),
                application_id,
                mobile,
            ),
        )

        row = cur.fetchone()

        if not row:
            conn.rollback()

            return {
                "success": False,
                "error": (
                    "Only your own pending application "
                    "can be withdrawn."
                ),
            }

        write_audit(
            cur,
            application_id,
            "WITHDRAW",
            "applicant:%s" % mobile,
        )

        conn.commit()

        return {
            "success": True,
            "application_no": row[0],
            "status": "WITHDRAWN",
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


@mcp.tool()
def get_scheme_info(ctx: Context) -> dict:
    """
    Get Old Age Pension scheme requirements from the existing portal.
    """

    require_citizen(ctx, MCP_AUDIENCE)

    return {
        "scheme": "Old Age Pension",
        "minimum_age": MIN_AGE,
        "valid_blocks": BLOCKS,
        "application_deadline": SCHEME_DEADLINE.isoformat(),
        "age_proof_required": True,
        "bank_account_required": True,
        "ifsc_required": True,
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
