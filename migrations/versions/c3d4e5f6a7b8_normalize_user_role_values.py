"""normalize user role values

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-10 00:00:00.000000

The previous migration's server_default wrote the lowercase enum *value* ('user') rather than
the enum *name* ('USER') that Enum(..., native_enum=False) expects on read (matching every other
enum column in this schema — see listingstatus/notificationtype/scrapejobtype/scrapejobstatus in
6893edef29c3_initial_schema.py). Any row written before that fix has an unreadable role. This
normalizes existing data; a no-op on a DB that never saw the buggy default.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    users = sa.table('users', sa.column('role', sa.String))
    op.execute(users.update().where(users.c.role == 'user').values(role='USER'))
    op.execute(users.update().where(users.c.role == 'admin').values(role='ADMIN'))


def downgrade() -> None:
    users = sa.table('users', sa.column('role', sa.String))
    op.execute(users.update().where(users.c.role == 'USER').values(role='user'))
    op.execute(users.update().where(users.c.role == 'ADMIN').values(role='admin'))
