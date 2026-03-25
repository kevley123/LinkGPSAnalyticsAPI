"""
ML REST API — Full anomaly detection endpoints.

POST /api/ml/devices/{id}/score/        — Real-time point scoring
GET  /api/ml/devices/{id}/anomalies/    — Fetch anomaly results
GET  /api/ml/devices/{id}/heatmap/      — Heatmap data (all points with score)
GET  /api/ml/devices/{id}/summary/      — Stats summary per device
GET  /api/ml/devices/{id}/model/        — Latest model metadata
POST /api/ml/devices/{id}/train/        — Trigger async training
POST /api/ml/devices/{id}/infer/        — Trigger async batch inference
GET  /api/ml/heatmap/all/               — Global heatmap across all devices
"""
import logging
from datetime import datetime, timezone as tz, timedelta
from django.db import models
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from core.models import TrackedDevice, AnomalyModelMl, RouteAnomalyMl, DailyRouteMl, RouteClusterMl
from analytics.ml_pipeline import InferenceService, ClusteringService

logger = logging.getLogger(__name__)


def get_device_id_by_vehicle(vehicle_id: int) -> int:
    """Helper to resolve vehicle_id to the primary device_id for ML processing."""
    try:
        device = TrackedDevice.objects.filter(vehicle_id=vehicle_id).first()
        if not device:
            raise ValueError(f"No tracked device found for vehicle_id {vehicle_id}")
        return device.pk
    except Exception as e:
        raise ValueError(str(e))


# ── Real-time Scoring ─────────────────────────────────────────────────────

@api_view(['POST'])
def score_gps_point(request, vehicle_id: int):
    """
    Score a single incoming GPS point against the vehicle's trained model.
    """
    try:
        device_id = get_device_id_by_vehicle(vehicle_id)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    data = request.data
    lat = data.get('latitude')
    lon = data.get('longitude')
    if lat is None or lon is None:
        return Response(
            {'error': 'latitude and longitude are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    recorded_at = None
    if data.get('recorded_at'):
        try:
            recorded_at = datetime.fromisoformat(str(data['recorded_at']))
        except ValueError:
            pass

    result = InferenceService().score_point(
        device_id=device_id,
        latitude=float(lat),
        longitude=float(lon),
        speed=float(data.get('speed', 0) or 0),
        heading=float(data.get('heading', 0) or 0),
        altitude=float(data.get('altitude', 0) or 0),
        accuracy=float(data.get('accuracy', 0) or 0),
        recorded_at=recorded_at,
        save=True,
    )

    if 'error' in result:
        return Response({'device_id': device_id, **result}, status=status.HTTP_404_NOT_FOUND)

    return Response({'device_id': device_id, **result})
@api_view(['POST'])
def confirm_gps_alert(request, vehicle_id: int):
    """
    POST /api/ml/vehicles/{id}/confirm/
    A simplified 'twin' of the score endpoint. 
    Returns a simple boolean to confirm if an alert should be triggered.
    """
    try:
        device_id = get_device_id_by_vehicle(vehicle_id)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    data = request.data
    lat = data.get('latitude')
    lon = data.get('longitude')
    if lat is None or lon is None:
        return Response({'error': 'latitude and longitude are required'}, status=400)

    # Use the same logic as score_point but with save=False (or True if preferred for history)
    result = InferenceService().score_point(
        device_id=device_id,
        latitude=float(lat),
        longitude=float(lon),
        speed=float(data.get('speed', 0) or 0),
        heading=float(data.get('heading', 0) or 0),
        altitude=float(data.get('altitude', 0) or 0),
        accuracy=float(data.get('accuracy', 0) or 0),
        save=False, # Just a confirmation check
    )

    if 'error' in result:
        return Response({'should_alert': False, 'reason': result['error']}, status=200)

    return Response({
        'device_id': device_id,
        'should_alert': result.get('is_anomaly', False),
        'risk_level': result.get('risk_level', 'low'),
        'anomaly_score': result.get('anomaly_score', 0.0)
    })


# ── Anomaly Results ───────────────────────────────────────────────────────

@api_view(['GET'])
def get_anomalies(request, vehicle_id: int):
    """
    GET /api/ml/vehicles/{id}/anomalies/

    Query params:
        - hours: int (default 168 = 7 days)
        - only_anomalies: bool (default false)
        - risk: 'low' | 'medium' | 'high'
        - limit: int (default 500)
    """
    try:
        device_id = get_device_id_by_vehicle(vehicle_id)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    hours = int(request.query_params.get('hours', 168))
    only_anomalies = request.query_params.get('only_anomalies', 'false').lower() == 'true'
    risk_filter = request.query_params.get('risk')
    limit = min(int(request.query_params.get('limit', 500)), 2000)

    since = datetime.now(tz=tz.utc) - timedelta(hours=hours)
    qs = RouteAnomalyMl.objects.filter(
        device_id=device_id,
        detected_at__gte=since,
    ).order_by('-detected_at')

    if only_anomalies:
        qs = qs.filter(is_anomaly=True)
    if risk_filter:
        qs = [r for r in qs if r.metadata.get('risk_level') == risk_filter]
    else:
        qs = qs[:limit]

    data = [
        {
            'id': r.id,
            'latitude': r.latitude,
            'longitude': r.longitude,
            'anomaly_score': r.anomaly_score,
            'is_anomaly': r.is_anomaly,
            'risk_level': r.metadata.get('risk_level') if r.metadata else None,
            'detected_at': r.detected_at.isoformat() if r.detected_at else None,
        }
        for r in qs
    ]
    return Response({
        'device_id': device_id,
        'hours': hours,
        'count': len(data),
        'anomaly_count': sum(1 for d in data if d['is_anomaly']),
        'results': data,
    })


# ── Heatmap Data ──────────────────────────────────────────────────────────

@api_view(['GET'])
def get_heatmap_device(request, vehicle_id: int):
    """
    GET /api/ml/vehicles/{id}/heatmap/
    """
    try:
        device_id = get_device_id_by_vehicle(vehicle_id)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    hours = int(request.query_params.get('hours', 24))
    min_score = float(request.query_params.get('min_score', 0.0))
    sampling = max(1, int(request.query_params.get('sampling', 1)))

    since = datetime.now(tz=tz.utc) - timedelta(hours=hours)
    
    # Base query
    qs = RouteAnomalyMl.objects.filter(
        device_id=device_id,
        detected_at__gte=since,
        latitude__isnull=False,
        longitude__isnull=False,
        anomaly_score__gte=min_score,
    ).order_by('detected_at')

    # Apply manual sampling in Python (more efficient than complex SQL for small offsets)
    # or simple limit
    all_points = list(qs.values('latitude', 'longitude', 'anomaly_score', 'is_anomaly')[:5000])
    
    if sampling > 1:
        # Keep ALL anomalies, but sample normal points
        sampled_points = []
        for i, p in enumerate(all_points):
            if p['is_anomaly'] or (i % sampling == 0):
                sampled_points.append(p)
        points_to_send = sampled_points
    else:
        points_to_send = all_points

    # Format for Leaflet.heat / mapbox heatmap
    normal = []
    anomalous = []
    
    for r in points_to_send:
        item = {
            'lat': r['latitude'],
            'lng': r['longitude'],
            'weight': float(r['anomaly_score'] or 0),
        }
        if r['is_anomaly']:
            anomalous.append(item)
        else:
            normal.append(item)

    return Response({
        'device_id': device_id,
        'hours': hours,
        'sampling': sampling,
        'total_returned': len(normal) + len(anomalous),
        'normal_points': normal,       # Suggest painting as a green path or sparse dots
        'anomaly_points': anomalous,   # Suggest painting as a red heatmap layer
    })


@api_view(['GET'])
def get_global_heatmap(request):
    """
    GET /api/ml/heatmap/all/
    Global Risk Heatmap (Model 3) - Serves the precomputed H3 grid JSON.
    """
    import os
    import json
    from django.conf import settings
    
    output_dir = getattr(settings, 'HEATMAP_DATA_PATH', os.path.join(settings.BASE_DIR, 'heatmaps', 'global'))
    filepath = os.path.join(output_dir, 'heatmap_latest.json')
    
    if not os.path.exists(filepath):
        return Response(
            {"error": "Heatmap not generated yet. Trigger generation first."}, 
            status=status.HTTP_404_NOT_FOUND
        )
        
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return Response(data)
    except Exception as e:
        return Response({"error": f"Failed to read heatmap data: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def generate_global_heatmap(request):
    """
    POST /api/ml/heatmap/generate/
    Manually triggers the creation of the Global Risk Heatmap (Model 3).
    """
    from analytics.heatmap_service import GlobalHeatmapService
    
    days = int(request.data.get('days', 30))
    
    try:
        service = GlobalHeatmapService(days_lookback=days)
        result = service.generate()
        
        if result.get("status") == "success":
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Device Summary ────────────────────────────────────────────────────────

@api_view(['GET'])
def get_device_anomaly_summary(request, vehicle_id: int):
    """
    GET /api/ml/vehicles/{id}/summary/
    """
    try:
        device_id = get_device_id_by_vehicle(vehicle_id)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    hours = int(request.query_params.get('hours', 168))
    since = datetime.now(tz=tz.utc) - timedelta(hours=hours)

    qs = RouteAnomalyMl.objects.filter(device_id=device_id, detected_at__gte=since)
    total = qs.count()
    anomaly_count = qs.filter(is_anomaly=True).count()

    model = AnomalyModelMl.objects.filter(device_id=device_id).order_by('-created_at').first()

    # Risk distribution from metadata
    risk_dist = {'low': 0, 'medium': 0, 'high': 0}
    for r in qs.values('metadata', 'is_anomaly'):
        level = (r.get('metadata') or {}).get('risk_level', 'low')
        if level in risk_dist:
            risk_dist[level] += 1

    return Response({
        'device_id': device_id,
        'period_hours': hours,
        'total_points': total,
        'anomaly_count': anomaly_count,
        'anomaly_rate': round(anomaly_count / total, 4) if total else 0,
        'risk_distribution': risk_dist,
        'model': {
            'id': model.pk if model else None,
            'type': model.model_type if model else None,
            'trained_from': model.trained_from.isoformat() if model and model.trained_from else None,
            'trained_to': model.trained_to.isoformat() if model and model.trained_to else None,
            'created_at': model.created_at.isoformat() if model and model.created_at else None,
        } if model else None,
    })


# ── Async Task Triggers ───────────────────────────────────────────────────

@api_view(['POST'])
def trigger_training(request, vehicle_id: int):
    """
    POST /api/ml/vehicles/{id}/train/
    """
    try:
        device_id = get_device_id_by_vehicle(vehicle_id)
        from analytics.tasks import train_device_model_task
        days = int(request.data.get('days', 20))
        task = train_device_model_task.delay(device_id, days)
        return Response({
            'status': 'queued',
            'vehicle_id': vehicle_id,
            'device_id': device_id,
            'task_id': task.id,
            'message': f'Training job queued for vehicle {vehicle_id}',
        }, status=status.HTTP_202_ACCEPTED)
    except Exception as e:
        logger.error(f"[trigger_training] {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def trigger_inference(request, vehicle_id: int):
    """
    POST /api/ml/vehicles/{id}/infer/
    """
    try:
        device_id = get_device_id_by_vehicle(vehicle_id)
        from analytics.tasks import run_inference_task
        hours = int(request.data.get('hours', 24))
        task = run_inference_task.delay(device_id, hours)
        return Response({
            'status': 'queued',
            'vehicle_id': vehicle_id,
            'device_id': device_id,
            'task_id': task.id,
            'message': f'Inference job queued for vehicle {vehicle_id}',
        }, status=status.HTTP_202_ACCEPTED)
    except Exception as e:
        logger.error(f"[trigger_inference] {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Supplementary / Legacy Endpoints ─────────────────────────────────────

@api_view(['GET'])
def get_daily_routes_ml(request, vehicle_id: int):
    """
    List aggregated daily routes for a vehicle.
    """
    try:
        device_id = get_device_id_by_vehicle(vehicle_id)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    date_param = request.query_params.get('date')
    if date_param:
        from datetime import date
        try:
            target_date = date.fromisoformat(date_param)
            route = DailyRouteMl.objects.filter(device_id=device_id, date=target_date).first()
            
            # If not found and it's today, try to aggregate on the fly
            if not route and target_date >= date.today():
                from analytics.ml_pipeline import AggregationService
                AggregationService().aggregate_device_day(device_id, target_date)
                route = DailyRouteMl.objects.filter(device_id=device_id, date=target_date).first()

            if not route:
                return Response({'error': f'No route found for date {date_param}'}, status=status.HTTP_404_NOT_FOUND)

            return Response({
                'vehicle_id': vehicle_id,
                'device_id': device_id,
                'date': route.date.isoformat(),
                'distance': route.total_distance,
                'avg_speed': route.avg_speed,
                'points': route.route_json
            })
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # Otherwise return summary list of last 30 days
    qs = DailyRouteMl.objects.filter(device_id=device_id).order_by('-date')[:30]
    data = [
        {
            'date': r.date.isoformat(),
            'distance': r.total_distance,
            'avg_speed': r.avg_speed,
            'point_count': len(r.route_json) if r.route_json else 0
        } for r in qs
    ]
    return Response(data)


@api_view(['GET'])
def get_route_anomalies(request, vehicle_id: int):
    """Legacy alias for get_anomalies."""
    return get_anomalies(request._request, vehicle_id)


@api_view(['GET'])
def get_route_clusters(request, vehicle_id: int):
    """Get location clusters for a vehicle."""
    try:
        device_id = get_device_id_by_vehicle(vehicle_id)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    from core.models import RouteClusterMl
    qs = RouteClusterMl.objects.filter(device_id=device_id).order_by('-density')
    data = [
        {
            'cluster_id': r.cluster_id,
            'lat': r.centroid_lat,
            'lng': r.centroid_lng,
            'density': r.density
        } for r in qs
    ]
    return Response(data)


@api_view(['GET'])
def get_anomaly_model_meta(request, vehicle_id: int):
    """Get metadata about the current trained model for a vehicle."""
    try:
        device_id = get_device_id_by_vehicle(vehicle_id)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    model = AnomalyModelMl.objects.filter(device_id=device_id).order_by('-created_at').first()
    if not model:
        return Response({'error': 'No model found'}, status=404)
    return Response({
        'vehicle_id': vehicle_id,
        'device_id': device_id,
        'id': model.id,
        'type': model.model_type,
        'path': model.model_path,
        'trained_at': model.created_at
    })


@api_view(['GET'])
def get_weekly_report(request, vehicle_id: int):
    """
    GET /api/ml/vehicles/{id}/weekly-report/
    Analyzes the last 7 days of anomalies to find trends.
    """
    try:
        device_id = get_device_id_by_vehicle(vehicle_id)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    since = datetime.now(tz=tz.utc) - timedelta(days=7)
    qs = RouteAnomalyMl.objects.filter(device_id=device_id, detected_at__gte=since)
    
    total = qs.count()
    if total == 0:
        return Response({'message': 'No data for the last 7 days'}, status=200)

    anomalies = qs.filter(is_anomaly=True)
    anomaly_count = anomalies.count()

    # Peak hours of anomalies
    from django.db.models.functions import ExtractHour
    from django.db.models import Count
    
    hour_stats = (
        anomalies
        .annotate(hour=ExtractHour('detected_at'))
        .values('hour')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # Weekly percentage trend (by day)
    from django.db.models.functions import TruncDay
    day_stats = (
        qs.annotate(day=TruncDay('detected_at'))
        .values('day')
        .annotate(
            total_points=Count('id'),
            anom_points=Count('id', filter=models.Q(is_anomaly=True))
        )
        .order_by('day')
    )

    days_detail = []
    for d in day_stats:
        total_p = d['total_points']
        anom_p = d['anom_points']
        days_detail.append({
            'date': d['day'].date().isoformat(),
            'total_points': total_p,
            'anomaly_points': anom_p,
            'percentage': round((anom_p / total_p * 100), 2) if total_p > 0 else 0
        })

    return Response({
        'vehicle_id': vehicle_id,
        'period': 'last_7_days',
        'summary': {
            'total_points_analyzed': total,
            'total_anomalies_found': anomaly_count,
            'global_anomaly_rate': f"{round((anomaly_count / total * 100), 2)}%",
        },
        'peak_anomaly_hours': [
            {'hour': h['hour'], 'count': h['count']} for h in hour_stats[:5]
        ],
        'daily_trends': days_detail
    })


# ════════════════════════════════════════════════════════════════════════════
# Model 2 — DBSCAN Cluster Endpoints
# ════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
def get_vehicle_clusters(request, vehicle_id: int):
    """
    GET /api/ml/vehicles/{id}/clusters/
    Returns all known behavior clusters for the vehicle.
    Each cluster represents a frequent zone: home, work, regular stop, etc.

    Response:
        cluster_id, centroid (lat/lng), radius, density, point_count, label (main/secondary)
    """
    try:
        device_id = get_device_id_by_vehicle(vehicle_id)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    clusters = RouteClusterMl.objects.filter(device_id=device_id).order_by('-density')
    if not clusters.exists():
        return Response({
            'vehicle_id': vehicle_id,
            'message': 'No clusters found. Run clustering first.',
            'clusters': []
        })

    data = [
        {
            'cluster_id': c.cluster_id,
            'label': c.label or 'secondary',
            'centroid': {'lat': c.centroid_lat, 'lng': c.centroid_lng},
            'radius': c.radius,
            'density': c.density,
            'point_count': c.point_count,
            'updated_at': c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in clusters
    ]

    return Response({
        'vehicle_id': vehicle_id,
        'total_clusters': len(data),
        'main_clusters': sum(1 for c in data if c['label'] == 'main'),
        'clusters': data,
    })


@api_view(['POST'])
def trigger_clustering(request, vehicle_id: int):
    """
    POST /api/ml/vehicles/{id}/cluster/run/
    Triggers DBSCAN clustering synchronously.
    Body (optional): { "days": 20 }
    """
    try:
        device_id = get_device_id_by_vehicle(vehicle_id)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    days = int(request.data.get('days', 20))

    try:
        result = ClusteringService().run_clustering(device_id, days=days)
        return Response({
            'vehicle_id': vehicle_id,
            'device_id': device_id,
            **result,
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f'[trigger_clustering] {e}')
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_cluster_heatmap(request, vehicle_id: int):
    """
    GET /api/ml/vehicles/{id}/cluster-heatmap/
    Returns cluster centroids as weighted heatmap points for Leaflet.

    Response:
        List of { lat, lng, weight, cluster_id, label }
        weight = normalized density (0.0 - 1.0)
    """
    try:
        device_id = get_device_id_by_vehicle(vehicle_id)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    clusters = RouteClusterMl.objects.filter(
        device_id=device_id,
        centroid_lat__isnull=False,
        centroid_lng__isnull=False,
    ).order_by('-density')

    if not clusters.exists():
        return Response({'vehicle_id': vehicle_id, 'points': [], 'message': 'No clusters yet'})

    # Normalize density to 0.0 - 1.0 for heatmap weight
    densities = [c.density or 0 for c in clusters]
    max_density = max(densities) if densities else 1

    points = [
        {
            'lat': c.centroid_lat,
            'lng': c.centroid_lng,
            'weight': round((c.density or 0) / max_density, 4),
            'cluster_id': c.cluster_id,
            'label': c.label or 'secondary',
            'radius': c.radius,
        }
        for c in clusters
    ]

    return Response({
        'vehicle_id': vehicle_id,
        'total_clusters': len(points),
        'points': points,
    })
