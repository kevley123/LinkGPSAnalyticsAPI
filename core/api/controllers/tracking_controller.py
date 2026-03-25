"""
Tracking API controllers — exposes device, position, alert, and geofence endpoints.
"""
import json
from datetime import datetime
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from core.application.use_cases.tracking_use_cases import (
    GetDeviceById,
    ListAllDevices,
    UpdateDeviceModo,
    GetDeviceLastPosition,
    GetDeviceHistory,
    GetLatestAllPositions,
    GetDeviceAlerts,
    GetUnresolvedAlerts,
    GetVehicleGeofences,
)


# ── Devices ────────────────────────────────────────────────────────

@api_view(['GET'])
def list_devices(request):
    """GET /api/devices/ — List all tracked devices."""
    devices = ListAllDevices().execute()
    data = [
        {
            'id': d.id,
            'device_imei': d.device_imei,
            'vehicle_id': d.vehicle_id,
            'status': d.status,
            'modo': d.modo,
            'last_seen': d.last_seen.isoformat() if d.last_seen else None,
        }
        for d in devices
    ]
    return Response({'count': len(data), 'results': data})


@api_view(['GET'])
def get_device(request, device_id: int):
    """GET /api/devices/{id}/ — Get a single device."""
    device = GetDeviceById().execute(device_id)
    if not device:
        return Response({'error': 'Device not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({
        'id': device.id,
        'device_imei': device.device_imei,
        'vehicle_id': device.vehicle_id,
        'status': device.status,
        'modo': device.modo,
        'activated_at': device.activated_at.isoformat() if device.activated_at else None,
        'last_seen': device.last_seen.isoformat() if device.last_seen else None,
        'metadata': device.metadata,
    })


@api_view(['PATCH'])
def update_device_modo(request, device_id: int):
    """PATCH /api/devices/{id}/modo/ — Update device operation mode (0-3)."""
    modo = request.data.get('modo')
    if modo is None or not isinstance(modo, int) or modo not in [0, 1, 2, 3]:
        return Response(
            {'error': 'modo must be an integer 0-3'},
            status=status.HTTP_400_BAD_REQUEST
        )
    ok = UpdateDeviceModo().execute(device_id, modo)
    if not ok:
        return Response({'error': 'Device not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'device_id': device_id, 'modo': modo, 'updated': True})


# ── GPS Positions ──────────────────────────────────────────────────

@api_view(['GET'])
def get_device_last_position(request, device_id: int):
    """GET /api/devices/{id}/position/ — Last known GPS position."""
    pos = GetDeviceLastPosition().execute(device_id)
    if not pos:
        return Response({'error': 'No position found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({
        'id': pos.id,
        'device_id': pos.device_id,
        'speed': pos.speed,
        'heading': pos.heading,
        'altitude': pos.altitude,
        'satellites': pos.satellites,
        'accuracy': pos.accuracy,
        'recorded_at': pos.recorded_at.isoformat() if pos.recorded_at else None,
    })


@api_view(['GET'])
def get_device_history(request, device_id: int):
    """
    GET /api/devices/{id}/history/
    Query params: from_dt, to_dt (ISO 8601)
    """
    from_dt_str = request.query_params.get('from_dt')
    to_dt_str = request.query_params.get('to_dt')
    if not from_dt_str or not to_dt_str:
        return Response(
            {'error': 'from_dt and to_dt query params required (ISO 8601)'},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        from_dt = parse_datetime(from_dt_str)
        to_dt = parse_datetime(to_dt_str)
    except Exception:
        return Response({'error': 'Invalid datetime format'}, status=status.HTTP_400_BAD_REQUEST)

    positions = GetDeviceHistory().execute(device_id, from_dt, to_dt)
    data = [
        {
            'id': p.id,
            'speed': p.speed,
            'heading': p.heading,
            'altitude': p.altitude,
            'satellites': p.satellites,
            'accuracy': p.accuracy,
            'recorded_at': p.recorded_at.isoformat(),
        }
        for p in positions
    ]
    return Response({'device_id': device_id, 'count': len(data), 'history': data})


@api_view(['GET'])
def get_all_latest_positions(request):
    """GET /api/positions/latest/ — Latest position for each device."""
    limit = int(request.query_params.get('limit', 100))
    positions = GetLatestAllPositions().execute(limit)
    data = [
        {
            'id': p.id,
            'device_id': p.device_id,
            'speed': p.speed,
            'heading': p.heading,
            'recorded_at': p.recorded_at.isoformat() if p.recorded_at else None,
        }
        for p in positions
    ]
    return Response({'count': len(data), 'positions': data})


# ── Alerts ─────────────────────────────────────────────────────────

@api_view(['GET'])
def get_device_alerts(request, device_id: int):
    """GET /api/devices/{id}/alerts/ — Alerts for a device."""
    limit = int(request.query_params.get('limit', 50))
    only_unresolved = request.query_params.get('unresolved', 'false').lower() == 'true'

    if only_unresolved:
        alerts = GetUnresolvedAlerts().execute(device_id)
    else:
        alerts = GetDeviceAlerts().execute(device_id, limit)

    data = [
        {
            'id': a.id,
            'alert_type': a.alert_type,
            'severity': a.severity,
            'resolved': a.resolved,
            'created_at': a.created_at.isoformat() if a.created_at else None,
            'metadata': a.metadata,
        }
        for a in alerts
    ]
    return Response({'device_id': device_id, 'count': len(data), 'alerts': data})


# ── Geofences ──────────────────────────────────────────────────────

@api_view(['GET'])
def get_vehicle_geofences(request, vehicle_id: int):
    """GET /api/geofences/vehicle/{id}/ — Geofences for a vehicle."""
    geofences = GetVehicleGeofences().execute(vehicle_id)
    data = [
        {
            'id': g.id,
            'name': g.name,
            'type': g.type,
            'active': g.active,
            'created_at': g.created_at.isoformat() if g.created_at else None,
        }
        for g in geofences
    ]
    return Response({'vehicle_id': vehicle_id, 'count': len(data), 'geofences': data})
