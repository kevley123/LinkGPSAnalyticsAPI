from typing import List, Optional
from core.domain.entities.alert import Alert as AlertEntity
from core.domain.ports.alert_repository import IAlertRepository
from core.models import Alert as AlertModel


def _to_entity(m: AlertModel) -> AlertEntity:
    return AlertEntity(
        id=m.pk,
        device_id=m.device_id,
        alert_type=m.alert_type,
        severity=m.severity,
        metadata=m.metadata or {},
        created_at=m.created_at,
        resolved=m.resolved,
    )


class AlertRepositoryImpl(IAlertRepository):

    def get_by_device(self, device_id: int, limit: int = 50) -> List[AlertEntity]:
        qs = AlertModel.objects.filter(device_id=device_id).order_by('-created_at')[:limit]
        return [_to_entity(m) for m in qs]

    def get_unresolved(self, device_id: int) -> List[AlertEntity]:
        qs = AlertModel.objects.filter(device_id=device_id, resolved=False).order_by('-created_at')
        return [_to_entity(m) for m in qs]

    def resolve(self, alert_id: int) -> bool:
        updated = AlertModel.objects.filter(pk=alert_id).update(resolved=True)
        return updated > 0
