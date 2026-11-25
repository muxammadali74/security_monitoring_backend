"""Add persistent security zones, detection events, and Telegram links.

Revision ID: e81f6308a419
Revises: df3bcd78e531
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e81f6308a419"
down_revision: Union[str, Sequence[str], None] = "df3bcd78e531"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _add_zone_column_if_missing(name: str, column: sa.Column) -> None:
    columns = {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_columns("cameras_zones")
    }
    if name not in columns:
        op.add_column("cameras_zones", column)


def upgrade() -> None:
    tables = _existing_tables()
    if "cameras_zones" in tables:
        _add_zone_column_if_missing(
            "zone_type",
            sa.Column(
                "zone_type",
                sa.String(length=32),
                nullable=False,
                server_default="intrusion",
            ),
        )
        _add_zone_column_if_missing(
            "color",
            sa.Column(
                "color",
                sa.String(length=16),
                nullable=False,
                server_default="indigo",
            ),
        )
        _add_zone_column_if_missing(
            "object_class_ids",
            sa.Column(
                "object_class_ids",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[0,2,7]'"),
            ),
        )
        _add_zone_column_if_missing(
            "is_active",
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )
        _add_zone_column_if_missing(
            "created_at",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        _add_zone_column_if_missing(
            "updated_at",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    if "detection_events" not in tables:
        op.create_table(
            "detection_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("camera_id", sa.Integer(), nullable=False),
            sa.Column("zone_id", sa.Integer(), nullable=True),
            sa.Column("object_class_id", sa.Integer(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("bounding_box", sa.JSON(), nullable=False),
            sa.Column(
                "occurred_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("snapshot", sa.LargeBinary(), nullable=False),
            sa.Column(
                "notification_status",
                sa.String(length=16),
                server_default="pending",
                nullable=False,
            ),
            sa.Column("notification_error", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["camera_id"], ["cameras.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["zone_id"], ["cameras_zones.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_detection_events_user_id", "detection_events", ["user_id"])
        op.create_index(
            "ix_detection_events_camera_id", "detection_events", ["camera_id"]
        )
        op.create_index("ix_detection_events_zone_id", "detection_events", ["zone_id"])
        op.create_index(
            "ix_detection_events_occurred_at", "detection_events", ["occurred_at"]
        )

    if "telegram_integrations" not in tables:
        op.create_table(
            "telegram_integrations",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("chat_id", sa.String(length=64), nullable=True),
            sa.Column(
                "notifications_enabled",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
            sa.Column("link_code_hash", sa.String(length=64), nullable=True),
            sa.Column(
                "link_code_expires_at", sa.DateTime(timezone=True), nullable=True
            ),
            sa.Column("linked_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id", name="uq_telegram_integrations_user_id"
            ),
            sa.UniqueConstraint(
                "chat_id", name="uq_telegram_integrations_chat_id"
            ),
            sa.UniqueConstraint(
                "link_code_hash", name="uq_telegram_integrations_link_hash"
            ),
        )
        op.create_index(
            "ix_telegram_integrations_user_id",
            "telegram_integrations",
            ["user_id"],
        )


def downgrade() -> None:
    op.drop_index(
        "ix_telegram_integrations_user_id", table_name="telegram_integrations"
    )
    op.drop_table("telegram_integrations")
    op.drop_index("ix_detection_events_occurred_at", table_name="detection_events")
    op.drop_index("ix_detection_events_zone_id", table_name="detection_events")
    op.drop_index("ix_detection_events_camera_id", table_name="detection_events")
    op.drop_index("ix_detection_events_user_id", table_name="detection_events")
    op.drop_table("detection_events")
    op.drop_column("cameras_zones", "updated_at")
    op.drop_column("cameras_zones", "created_at")
    op.drop_column("cameras_zones", "is_active")
    op.drop_column("cameras_zones", "object_class_ids")
    op.drop_column("cameras_zones", "zone_type")
    op.drop_column("cameras_zones", "color")
