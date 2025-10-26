"""init

Revision ID: 1543f40cf6e0
Revises:
Create Date: 2025-10-26 09:26:58.675361
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "1543f40cf6e0"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# constants to avoid string duplication
CHILD_ID_FK = "child.id"


def upgrade() -> None:
    op.create_table(
        "domainthreshold",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("age_years", sa.Integer(), nullable=False),
        sa.Column("age_months", sa.Integer(), nullable=False),
        sa.Column("yellow_min", sa.Integer(), nullable=False),
        sa.Column("green_min", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "exercise",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("payload_json", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "exerciseanswer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("ts_utc", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "institution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "parent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "child",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("age_years", sa.Integer(), nullable=False),
        sa.Column("age_months", sa.Integer(), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("ppr_consent", sa.Boolean(), nullable=False),
        sa.Column("report_path", sa.String(), nullable=True),
        sa.Column("report_filename", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["institution_id"], ["institution.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "staff",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institution.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "childparentlink",
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], [CHILD_ID_FK]),
        sa.ForeignKeyConstraint(["parent_id"], ["parent.id"]),
        sa.PrimaryKeyConstraint("child_id", "parent_id"),
    )

    op.create_table(
        "childstafflink",
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], [CHILD_ID_FK]),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("child_id", "staff_id"),
    )

    op.create_table(
        "domainprogress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("color", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], [CHILD_ID_FK]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("domainprogress")
    op.drop_table("childstafflink")
    op.drop_table("childparentlink")
    op.drop_table("staff")
    op.drop_table("child")
    op.drop_table("parent")
    op.drop_table("institution")
    op.drop_table("exerciseanswer")
    op.drop_table("exercise")
    op.drop_table("domainthreshold")
