"""Grant or revoke admin access for an existing user, by email.

Deliberately promotes/demotes an already-registered account rather than taking a password itself:
the account still goes through the normal register + argon2-hash + email-verification flow, so
this command never handles a plaintext credential and there is no standing admin password in an
env var. See docs/adr/20_ROLES_AND_ADMIN.md. Run on a host with DB access (docker exec / railway run):

    python -m app.auth.cli promote --email admin@example.com
    python -m app.auth.cli demote --email admin@example.com
"""

import argparse
import asyncio

from app.auth.repository import UserRepository
from app.db.session import get_session
from app.models.user import UserRole


async def _set_role(email: str, role: UserRole) -> None:
    async for session in get_session():
        repo = UserRepository(session)
        user = await repo.get_by_email(email)
        if user is None:
            raise SystemExit(f"No user with email {email!r}")
        await repo.set_role(user, role)
        await session.commit()
        print(f"{user.email} is now {role.value}")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    promote = subparsers.add_parser("promote", help="Grant admin access to an existing user")
    promote.add_argument("--email", required=True)

    demote = subparsers.add_parser("demote", help="Revoke admin access from an existing user")
    demote.add_argument("--email", required=True)

    args = parser.parse_args()
    role = UserRole.ADMIN if args.command == "promote" else UserRole.USER
    asyncio.run(_set_role(args.email, role))


if __name__ == "__main__":
    main()
