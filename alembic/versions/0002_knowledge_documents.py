"""0002 tabel knowledge_document + knowledge_chunk untuk ingest dokumen unggahan. TRD §14.2, hanya maju."""
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    import sqlalchemy as sa
    from app.core.db import engine
    from app.modules import models_a  # noqa: registrasi tabel baru pada Base
    models_a.Base.metadata.create_all(bind=engine)

def downgrade():
    pass  # TRD §14.2: destruktif dilarang sebelum Minggu 15
