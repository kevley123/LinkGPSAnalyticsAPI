from typing import List, Optional
from core.domain.entities.tracked_device import TrackedDevice as TrackedDeviceEntity
from core.domain.ports.tracked_device_repository import ITrackedDeviceRepository
from core.models import TrackedDevice as TrackedDeviceModel


def _to_entity(m: TrackedDeviceModel) -> TrackedDeviceEntity:
    return TrackedDeviceEntity(
        id=m.pk,
        device_imei=m.device_imei,
        vehicle_id=m.vehicle_id,
        status=m.status,
        activated_at=m.activated_at,
        last_seen=m.last_seen,
        metadata=m.metadata or {},
        modo=m.modo,
    )


class TrackedDeviceRepositoryImpl(ITrackedDeviceRepository):

    def get_by_id(self, device_id: int) -> Optional[TrackedDeviceEntity]:
        try:
            return _to_entity(TrackedDeviceModel.objects.get(pk=device_id))
        except TrackedDeviceModel.DoesNotExist:
            return None

    def get_by_imei(self, imei: str) -> Optional[TrackedDeviceEntity]:
        try:
            return _to_entity(TrackedDeviceModel.objects.get(device_imei=imei))
        except TrackedDeviceModel.DoesNotExist:
            return None

    def list_all(self) -> List[TrackedDeviceEntity]:
        return [_to_entity(m) for m in TrackedDeviceModel.objects.all()]

    def update_modo(self, device_id: int, modo: int) -> bool:
        updated = TrackedDeviceModel.objects.filter(pk=device_id).update(modo=modo)
        return updated > 0
