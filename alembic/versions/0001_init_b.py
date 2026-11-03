"""0001 awal B: ticket, case_tbl, sla_record, sla_event, crm_outbox, escalation. TRD §14.2 satu head, hanya maju."""
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    import sqlalchemy as sa
    from app.core.db import engine
    from app.modules import models  # noqa
    models.Base.metadata.create_all(bind=engine)

def downgrade():
    pass  # TRD §14.2: destruktif dilarang sebelum Minggu 15
