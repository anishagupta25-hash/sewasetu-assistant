import os
from mcp.server.fastmcp import FastMCP, Context

from mcp.server.fastmcp import FastMCP, Context

from sewa_mcp.auth import require_officer, officer_username
from sewa_mcp.common import get_db, write_audit

MCP_AUDIENCE = os.environ.get(
    "OFFICER_MCP_URL",
    "http://localhost:8200"
).rstrip("/")

mcp = FastMCP(
    "Sewa Setu Officer Assistant",
    stateless_http=True,
    json_response=True,
    host="0.0.0.0",
    port=8200,
)
@mcp.tool()
def list_applications(
    ctx: Context,
    status: str = "PENDING",
    block: str = "",
) -> dict:
    """
    List pension applications for the authenticated block officer.
    """

    claims = require_officer(ctx, MCP_AUDIENCE)
    officer = officer_username(claims)

    allowed_statuses = {
        "PENDING",
        "APPROVED",
        "REJECTED",
        "WITHDRAWN",
        "DEEMED_APPROVED",
    }

    if status not in allowed_statuses:
        return {
            "error": "Invalid status",
            "allowed_statuses": sorted(allowed_statuses),
        }

    conn = get_db()
    cur = conn.cursor()

    try:
        if block:
            cur.execute(
                """
                SELECT
                    id,
                    application_no,
                    applicant_name,
                    mobile,
                    block,
                    status,
                    submitted_at
                FROM applications
                WHERE status = %s
                  AND block = %s
                ORDER BY submitted_at ASC
                LIMIT 100
                """,
                (status, block),
            )
        else:
            cur.execute(
                """
                SELECT
                    id,
                    application_no,
                    applicant_name,
                    mobile,
                    block,
                    status,
                    submitted_at
                FROM applications
                WHERE status = %s
                ORDER BY submitted_at ASC
                LIMIT 100
                """,
                (status,),
            )

        rows = cur.fetchall()

        return {
            "officer": officer,
            "count": len(rows),
            "applications": [
                {
                    "id": row[0],
                    "application_no": row[1],
                    "applicant_name": row[2],
                    "mobile": row[3],
                    "block": row[4],
                    "status": row[5],
                    "submitted_at": (
                        row[6].isoformat()
                        if row[6]
                        else None
                    ),
                }
                for row in rows
            ],
        }

    finally:
        cur.close()
        conn.close()


@mcp.tool()
def get_application(
    ctx: Context,
    application_id: int,
) -> dict:
    """
    Get the full application record for officer review.
    """

    require_officer(ctx, MCP_AUDIENCE)

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
                gender,
                marital_status,
                village,
                block,
                bank_account,
                ifsc,
                doc_path,
                status,
                submitted_at,
                decided_at,
                decided_by
            FROM applications
            WHERE id = %s
            """,
            (application_id,),
        )

        row = cur.fetchone()

        if not row:
            return {
                "found": False,
                "error": "Application not found.",
            }

        return {
            "found": True,
            "application": {
                "id": row[0],
                "application_no": row[1],
                "applicant_name": row[2],
                "mobile": row[3],
                "dob": row[4].isoformat() if row[4] else None,
                "gender": row[5],
                "marital_status": row[6],
                "village": row[7],
                "block": row[8],
                "bank_account": row[9],
                "ifsc": row[10],
                "doc_path": row[11],
                "status": row[12],
                "submitted_at": (
                    row[13].isoformat()
                    if row[13]
                    else None
                ),
                "decided_at": (
                    row[14].isoformat()
                    if row[14]
                    else None
                ),
                "decided_by": row[15],
            },
        }

    finally:
        cur.close()
        conn.close()


@mcp.tool()
def get_application_audit(
    ctx: Context,
    application_id: int,
) -> dict:
    """
    Get the audit history of a pension application.
    """

    require_officer(ctx, MCP_AUDIENCE)

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT application_no
            FROM applications
            WHERE id = %s
            """,
            (application_id,),
        )

        application = cur.fetchone()

        if not application:
            return {
                "found": False,
                "error": "Application not found.",
            }

        cur.execute(
            """
            SELECT
                at,
                action,
                actor,
                note
            FROM audit_log
            WHERE application_id = %s
            ORDER BY at ASC
            """,
            (application_id,),
        )

        rows = cur.fetchall()

        return {
            "found": True,
            "application_id": application_id,
            "application_no": application[0],
            "audit": [
                {
                    "at": (
                        row[0].isoformat()
                        if row[0]
                        else None
                    ),
                    "action": row[1],
                    "actor": row[2],
                    "note": row[3],
                }
                for row in rows
            ],
        }

    finally:
        cur.close()
        conn.close()


@mcp.tool()
def approve_application(
    ctx: Context,
    application_id: int,
    note: str = "",
) -> dict:
    """
    Approve a pending pension application.
    """

    claims = require_officer(ctx, MCP_AUDIENCE)
    officer = officer_username(claims)

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE applications
            SET
                status = 'APPROVED',
                decided_at = NOW(),
                decided_by = %s
            WHERE id = %s
              AND status = 'PENDING'
            RETURNING application_no
            """,
            (officer, application_id),
        )

        row = cur.fetchone()

        if not row:
            conn.rollback()

            return {
                "success": False,
                "error": (
                    "Application does not exist "
                    "or is not pending."
                ),
            }

        write_audit(
            cur,
            application_id,
            "APPROVED",
            "officer:%s" % officer,
            note,
        )

        conn.commit()

        return {
            "success": True,
            "application_id": application_id,
            "application_no": row[0],
            "status": "APPROVED",
            "decided_by": officer,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


@mcp.tool()
def reject_application(
    ctx: Context,
    application_id: int,
    note: str = "",
) -> dict:
    """
    Reject a pending pension application.
    """

    claims = require_officer(ctx, MCP_AUDIENCE)
    officer = officer_username(claims)

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE applications
            SET
                status = 'REJECTED',
                decided_at = NOW(),
                decided_by = %s
            WHERE id = %s
              AND status = 'PENDING'
            RETURNING application_no
            """,
            (officer, application_id),
        )

        row = cur.fetchone()

        if not row:
            conn.rollback()

            return {
                "success": False,
                "error": (
                    "Application does not exist "
                    "or is not pending."
                ),
            }

        write_audit(
            cur,
            application_id,
            "REJECTED",
            "officer:%s" % officer,
            note,
        )

        conn.commit()

        return {
            "success": True,
            "application_id": application_id,
            "application_no": row[0],
            "status": "REJECTED",
            "decided_by": officer,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
