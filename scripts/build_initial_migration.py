"""Development utility: freeze ORM DDL once into an explicit, reviewable Alembic revision.

Run from backend with ../scripts/build_initial_migration.py. Do not regenerate an applied revision.
"""

from pathlib import Path
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable
from app.models import Base

target = Path("alembic/versions/0001_initial.py")
if target.exists():
    raise SystemExit("Revision already exists; create a new Alembic revision for schema changes")
dialect = postgresql.dialect()
tables = Base.metadata.sorted_tables
header = '''"""Initial application schema with mixed-dimension pgvector storage."""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
'''
lines = [header]
for table in tables:
    ddl = str(CreateTable(table).compile(dialect=dialect)).strip()
    lines.append('    op.execute("""\n' + ddl + '\n""")\n')
    for index in sorted(table.indexes, key=lambda i: i.name):
        lines.append(f"    op.execute({str(CreateIndex(index).compile(dialect=dialect))!r})\n")
lines.append("\n\ndef downgrade():\n")
for table in reversed(tables):
    lines.append(f'    op.execute("DROP TABLE {table.name}")\n')
target.write_text("".join(lines), encoding="utf-8")
print(f"Wrote {target}: {len(tables)} tables")
