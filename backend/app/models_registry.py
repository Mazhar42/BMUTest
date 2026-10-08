"""Import every ORM model so SQLAlchemy mappers and Alembic autogenerate see the full schema."""

from app.core import models as core_models  # noqa: F401
from app.modules.catalog import models as catalog_models  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.notifications import models as notification_models  # noqa: F401
from app.modules.orders import models as order_models  # noqa: F401
from app.modules.patients import models as patient_models  # noqa: F401
from app.modules.payments import models as payment_models  # noqa: F401
from app.modules.prescriptions import models as prescription_models  # noqa: F401
