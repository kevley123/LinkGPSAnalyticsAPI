"""
ML domain entities — they represent data stored in the _ml tables.
These are produced by AI/ML training and inference pipelines.
"""
from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import date, datetime


@dataclass
class DailyRouteMl:
    """Processed daily route summary used as ML feature input."""
    id: int
    device_id: int
    date: Optional[date] = None
    route: Optional[Any] = None             # PostGIS geometry (LineString)
    route_json: Optional[dict] = None       # Serialized route for ML
    total_distance: Optional[float] = None  # meters
    avg_speed: Optional[float] = None       # km/h
    created_at: Optional[datetime] = None


@dataclass
class AnomalyModelMl:
    """Metadata record for a trained anomaly detection model."""
    id: int
    device_id: int
    model_path: Optional[str] = None        # Path to .pkl / .joblib / .h5 file
    model_type: Optional[str] = None        # 'IsolationForest', 'LSTM', 'DBSCAN'
    trained_from: Optional[date] = None
    trained_to: Optional[date] = None
    created_at: Optional[datetime] = None


@dataclass
class RouteAnomalyMl:
    """Individual anomaly detection result for a GPS point."""
    id: int
    device_id: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geom: Optional[Any] = None              # PostGIS Point
    anomaly_score: Optional[float] = None   # Higher = more anomalous
    is_anomaly: bool = False
    detected_at: Optional[datetime] = None
    metadata: Optional[dict] = field(default_factory=dict)


@dataclass
class RouteClusterMl:
    """Cluster of habitual routes for a device (normal behavior baseline)."""
    id: int
    device_id: int
    cluster_id: Optional[int] = None        # DBSCAN label (-1 = noise)
    centroid_lat: Optional[float] = None
    centroid_lng: Optional[float] = None
    centroid_geom: Optional[Any] = None     # PostGIS Point
    density: Optional[float] = None
    created_at: Optional[datetime] = None
