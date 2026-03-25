"""
ML Services — Anomaly Detection Pipeline
=========================================
architecture:
  1. AggregationService   → reads gps_positions, writes daily_routes_ml
  2. TrainingService      → reads daily_routes_ml, trains IsolationForest per device
  3. InferenceService     → scores new GPS points against trained model

Each tracked_device has its own model stored as a .pkl file.
Model metadata is persisted in anomaly_models_ml.
Anomaly results are written to route_anomalies_ml.
"""
import os
import math
import joblib
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone as tz, date
from typing import Optional

from django.db import connection, transaction

from core.models import (
    TrackedDevice,
    DailyRouteMl,
    AnomalyModelMl,
    RouteAnomalyMl,
    RouteClusterMl,
)

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
# Path to store trained .pkl files inside the project
MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'ml_models'
)
os.makedirs(MODELS_DIR, exist_ok=True)

TRAINING_DAYS = 20
MIN_ROWS_TO_TRAIN = 50
CONTAMINATION = 0.05        # 5% expected anomalies
N_ESTIMATORS = 200

# Features extracted per GPS point
FEATURES = ['latitude', 'longitude', 'hour', 'speed', 'heading',
            'altitude', 'accuracy', 'dist_from_prev']


# ════════════════════════════════════════════════════════════════════════════
# 1. DATA AGGREGATION SERVICE
# ════════════════════════════════════════════════════════════════════════════

class AggregationService:
    """
    Reads raw gps_positions for a device + date range and produces
    cleaned, feature-rich rows saved to daily_routes_ml.
    """

    def aggregate_device_day(self, device_id: int, target_date: date) -> Optional[int]:
        """
        Aggregate GPS positions for one device on one day.
        Returns the DailyRouteMl.id created, or None if no data.
        """
        start = datetime(target_date.year, target_date.month, target_date.day,
                         0, 0, 0, tzinfo=tz.utc)
        end = start + timedelta(days=1)

        sql = """
            SELECT
                id,
                ST_Y(geom::geometry) AS latitude,
                ST_X(geom::geometry) AS longitude,
                speed, heading, altitude, accuracy, satellites,
                recorded_at
            FROM tracking.gps_positions
            WHERE device_id = %s
              AND recorded_at >= %s
              AND recorded_at < %s
              AND geom IS NOT NULL
            ORDER BY recorded_at ASC
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [device_id, start, end])
            rows = cursor.fetchall()
            cols = [d[0] for d in cursor.description]

        if not rows:
            logger.info(f"[aggregation] No data for device {device_id} on {target_date}")
            return None

        df = pd.DataFrame(rows, columns=cols)
        df = self._clean(df)

        if len(df) < 5:
            logger.info(f"[aggregation] Too few valid rows ({len(df)}) for device {device_id} on {target_date}")
            return None

        # Build route summary
        total_distance = df['dist_from_prev'].sum()
        avg_speed = df['speed'].mean() if df['speed'].notna().any() else 0.0
        route_json = df[['latitude', 'longitude', 'speed', 'recorded_at']].to_dict(orient='records')
        # Convert timestamps for JSON serialization
        for rec in route_json:
            if hasattr(rec.get('recorded_at'), 'isoformat'):
                rec['recorded_at'] = rec['recorded_at'].isoformat()

        # Delete old entry for this device+date if exists (idempotent)
        DailyRouteMl.objects.filter(device_id=device_id, date=target_date).delete()

        entry = DailyRouteMl(
            device_id=device_id,
            date=target_date,
            route_json=route_json,
            total_distance=round(float(total_distance), 3),
            avg_speed=round(float(avg_speed), 3),
        )
        entry.save(using='default')
        logger.info(
            f"[aggregation] device={device_id} date={target_date} "
            f"points={len(df)} dist={total_distance:.1f}m"
        )
        return entry.pk

    def aggregate_device_last_n_days(self, device_id: int, days: int = TRAINING_DAYS):
        """Aggregate all days in the last N days for a device."""
        today = date.today()
        created = []
        for i in range(days):
            d = today - timedelta(days=i + 1)
            pk = self.aggregate_device_day(device_id, d)
            if pk:
                created.append(pk)
        return created

    # ── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _clean(df: pd.DataFrame) -> pd.DataFrame:
        """Clean and enrich GPS dataframe."""
        # Drop duplicate timestamps
        df = df.drop_duplicates(subset='recorded_at')

        # Remove rows with no coordinates
        df = df.dropna(subset=['latitude', 'longitude'])

        # Clamp impossible speeds (GPS glitch)
        if 'speed' in df.columns:
            df['speed'] = df['speed'].clip(lower=0, upper=250)

        # Fill sensor gaps with median
        for col in ['speed', 'heading', 'altitude', 'accuracy']:
            if col in df.columns:
                df[col] = df[col].fillna(df[col].median())

        # Add hour-of-day feature
        df['hour'] = pd.to_datetime(df['recorded_at']).dt.hour

        # Compute distance_from_previous (meters, haversine)
        df = df.reset_index(drop=True)
        df['dist_from_prev'] = 0.0
        for i in range(1, len(df)):
            df.loc[i, 'dist_from_prev'] = _haversine(
                df.loc[i - 1, 'latitude'], df.loc[i - 1, 'longitude'],
                df.loc[i, 'latitude'], df.loc[i, 'longitude'],
            )

        # Remove GPS "teleports" (>5 km jump in one point)
        df = df[df['dist_from_prev'] < 5000]

        return df


# ════════════════════════════════════════════════════════════════════════════
# 2. TRAINING SERVICE
# ════════════════════════════════════════════════════════════════════════════

class TrainingService:
    """
    Trains one IsolationForest model per device using data from daily_routes_ml.
    Persists the model as a .pkl file and registers metadata in anomaly_models_ml.
    """

    def train_device(self, device_id: int, days: int = TRAINING_DAYS) -> Optional[str]:
        """
        Train (or retrain) an anomaly detection model for a device.

        Returns:
            str: path to saved .pkl file, or None on failure
        """
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline

        cutoff = date.today() - timedelta(days=days)
        routes = DailyRouteMl.objects.filter(
            device_id=device_id,
            date__gte=cutoff,
        ).order_by('date')

        if not routes.exists():
            logger.warning(f"[training] No daily_routes_ml for device {device_id}")
            return None

        # Build feature matrix from stored route_json
        rows = []
        for route in routes:
            if not route.route_json:
                continue
            for pt in route.route_json:
                rows.append({
                    'latitude': pt.get('latitude', 0),
                    'longitude': pt.get('longitude', 0),
                    'hour': _hour_from_iso(pt.get('recorded_at')),
                    'speed': pt.get('speed', 0) or 0,
                    'heading': 0,      # not stored in route_json, neutral
                    'altitude': 0,
                    'accuracy': 0,
                    'dist_from_prev': 0,
                })

        if len(rows) < MIN_ROWS_TO_TRAIN:
            logger.warning(
                f"[training] Only {len(rows)} rows for device {device_id}. "
                f"Need ≥ {MIN_ROWS_TO_TRAIN}. Skipping."
            )
            return None

        df = pd.DataFrame(rows)
        # Use only these features for training (must exist in df)
        used_features = [f for f in FEATURES if f in df.columns]
        X = df[used_features].fillna(0).values

        # Build sklearn pipeline: scaler + model
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('model', IsolationForest(
                n_estimators=N_ESTIMATORS,
                contamination=CONTAMINATION,
                random_state=42,
                n_jobs=-1,
            ))
        ])
        pipeline.fit(X)

        # Version: use today's date + device_id
        version_tag = f"{date.today().strftime('%Y%m%d')}_{device_id}"
        model_path = os.path.join(MODELS_DIR, f"iforest_device_{device_id}_v{version_tag}.pkl")

        joblib.dump({
            'pipeline': pipeline,
            'features': used_features,
            'trained_on': date.today().isoformat(),
            'device_id': device_id,
            'n_samples': len(rows),
        }, model_path)

        # Register in DB: insert new record (keep history for versioning)
        AnomalyModelMl.objects.create(
            device_id=device_id,
            model_path=model_path,
            model_type='IsolationForest',
            trained_from=cutoff,
            trained_to=date.today(),
        )

        logger.info(
            f"[training] ✓ Device {device_id}: model trained on "
            f"{len(rows)} points → {model_path}"
        )
        return model_path

    def train_all_devices(self, days: int = TRAINING_DAYS):
        """Train models for every active tracked device."""
        devices = TrackedDevice.objects.filter(status='active')
        results = {}
        for device in devices:
            try:
                path = self.train_device(device.pk, days)
                results[device.pk] = path or 'SKIPPED'
            except Exception as e:
                logger.error(f"[training] ERROR device {device.pk}: {e}")
                results[device.pk] = f'ERROR: {e}'
        return results


# ════════════════════════════════════════════════════════════════════════════
# 3. INFERENCE SERVICE
# ════════════════════════════════════════════════════════════════════════════

class InferenceService:
    """
    Scores GPS position points against a device's trained model.
    Saves classified results to route_anomalies_ml.
    """

    def _load_model(self, device_id: int) -> Optional[dict]:
        """Load the latest trained model bundle for a device."""
        latest = (
            AnomalyModelMl.objects
            .filter(device_id=device_id)
            .order_by('-created_at')
            .first()
        )
        if not latest or not latest.model_path:
            return None
        if not os.path.exists(latest.model_path):
            logger.warning(f"[inference] Model file missing: {latest.model_path}")
            return None
        return {'bundle': joblib.load(latest.model_path), 'meta': latest}

    def score_point(
        self,
        device_id: int,
        latitude: float,
        longitude: float,
        speed: float = 0,
        heading: float = 0,
        altitude: float = 0,
        accuracy: float = 0,
        recorded_at: Optional[datetime] = None,
        dist_from_prev: float = 0,
        save: bool = True,
    ) -> dict:
        """
        Score a single GPS point and optionally persist the result.

        Returns dict with:
          - anomaly_score: float (higher = more anomalous)
          - is_anomaly: bool
          - risk_level: 'low' | 'medium' | 'high'
        """
        loaded = self._load_model(device_id)
        if not loaded:
            return {'anomaly_score': None, 'is_anomaly': False, 'risk_level': 'unknown',
                    'error': 'No trained model for this device'}

        bundle = loaded['bundle']
        pipeline = bundle['pipeline']
        features = bundle['features']

        hour = recorded_at.hour if recorded_at else 0
        row = {
            'latitude': latitude,
            'longitude': longitude,
            'hour': hour,
            'speed': speed,
            'heading': heading,
            'altitude': altitude,
            'accuracy': accuracy,
            'dist_from_prev': dist_from_prev,
        }
        X = np.array([[row.get(f, 0) for f in features]])
        
        # Get Isolation Forest prediction (-1 = anomaly, 1 = normal)
        label = int(pipeline.predict(X)[0])

        # ── Refined Additive Scoring Logic ────────────────────────────────────
        # User formula:
        # 1. Base from Isolation Forest: +0.5 if -1
        # 2. Base from Cluster Distance: +0.4 if dist > 5km
        
        score_if = 0.5 if label == -1 else 0.0
        
        cluster_info = _get_cluster_context(device_id, latitude, longitude)
        score_dist = 0.0
        
        # ── Safe Zone Override (Base) ─────────────────────────────────────────
        if cluster_info['has_clusters'] and cluster_info['inside_cluster']:
            if cluster_info['nearest_cluster_label'] == 'main':
                score_if = 0.0  # Zero out IF anomaly if at base
            else:
                score_if = min(score_if, 0.2) # Reduce IF anomaly if at secondary zone

        if cluster_info['has_clusters']:
            dist = cluster_info['min_distance']
            if dist > 5000:
                score_dist = 0.4  # Major deviation (>5km)
            elif dist > 2000:
                score_dist = 0.2  # Moderate deviation (>2km)
            else:
                score_dist = 0.0  # Safe/Grace zone (<2km)
        else:
            # If no clusters exist yet, we don't penalize distance
            score_dist = 0.0

        anomaly_score = round(score_if + score_dist, 2)
        is_anomaly = anomaly_score >= 0.7  # Requires BOTH IF + Distance or extreme deviation (>5km)
        risk_level = _risk_from_score(anomaly_score)

        result = {
            'anomaly_score': anomaly_score,
            'is_anomaly': is_anomaly,
            'risk_level': risk_level,
            'model_id': loaded['meta'].pk,
            'components': {
                'if_score_contrib': score_if,
                'dist_score_contrib': score_dist,
            },
            'cluster_context': cluster_info
        }

        if save:
            self._save_result(
                device_id, latitude, longitude, anomaly_score,
                is_anomaly, recorded_at, result, loaded['meta']
            )

        return result

    def score_device_recent(self, device_id: int, hours: int = 24) -> list:
        """
        Score all GPS positions from the last N hours for a device.
        Batch scoring — efficient for nightly jobs.
        """
        loaded = self._load_model(device_id)
        if not loaded:
            logger.warning(f"[inference] No model for device {device_id}")
            return []

        since = datetime.now(tz=tz.utc) - timedelta(hours=hours)
        sql = """
            SELECT
                id,
                ST_Y(geom::geometry) AS latitude,
                ST_X(geom::geometry) AS longitude,
                speed, heading, altitude, accuracy, recorded_at
            FROM tracking.gps_positions
            WHERE device_id = %s
              AND recorded_at >= %s
              AND geom IS NOT NULL
            ORDER BY recorded_at ASC
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [device_id, since])
            rows = cursor.fetchall()
            cols = [d[0] for d in cursor.description]

        if not rows:
            return []

        df = pd.DataFrame(rows, columns=cols)
        df['hour'] = pd.to_datetime(df['recorded_at']).dt.hour
        df['dist_from_prev'] = 0.0
        for i in range(1, len(df)):
            df.loc[i, 'dist_from_prev'] = _haversine(
                df.loc[i - 1, 'latitude'], df.loc[i - 1, 'longitude'],
                df.loc[i, 'latitude'], df.loc[i, 'longitude'],
            )
        df = df.fillna(0)

        bundle = loaded['bundle']
        pipeline = bundle['pipeline']
        features = bundle['features']

        X = df[[f for f in features if f in df.columns]].values
        raw_scores = pipeline.decision_function(X)
        labels = pipeline.predict(X)

        # Bulk delete old results in this window to avoid duplicates
        RouteAnomalyMl.objects.filter(
            device_id=device_id,
            detected_at__gte=since,
        ).delete()

        results = []
        bulk_objs = []
        for i, row in df.iterrows():
            anomaly_score = round(max(0.0, min(1.0, (-float(raw_scores[i]) + 0.5))), 4)
            is_anomaly = int(labels[i]) == -1
            risk_level = _risk_from_score(anomaly_score)

            bulk_objs.append(RouteAnomalyMl(
                device_id=device_id,
                latitude=float(row['latitude']),
                longitude=float(row['longitude']),
                anomaly_score=anomaly_score,
                is_anomaly=is_anomaly,
                detected_at=row['recorded_at'],
                metadata={
                    'risk_level': risk_level,
                    'model_id': loaded['meta'].pk,
                    'raw_score': float(raw_scores[i]),
                },
            ))
            results.append({
                'latitude': float(row['latitude']),
                'longitude': float(row['longitude']),
                'anomaly_score': anomaly_score,
                'is_anomaly': is_anomaly,
                'risk_level': risk_level,
                'recorded_at': str(row['recorded_at']),
            })

        # Bulk insert
        RouteAnomalyMl.objects.bulk_create(bulk_objs, batch_size=500)
        logger.info(
            f"[inference] device={device_id}: scored {len(results)} points, "
            f"{sum(1 for r in results if r['is_anomaly'])} anomalies"
        )
        return results

    def _save_result(
        self, device_id, lat, lon, score, is_anomaly, recorded_at, result, model_meta
    ):
        RouteAnomalyMl.objects.create(
            device_id=device_id,
            latitude=lat,
            longitude=lon,
            anomaly_score=score,
            is_anomaly=is_anomaly,
            detected_at=recorded_at or datetime.now(tz=tz.utc),
            metadata={
                'risk_level': result.get('risk_level'),
                'model_id': model_meta.pk,
            },
        )


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

def _haversine(lat1, lon1, lat2, lon2) -> float:
    """Distance between two lat/lon points in meters."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _hour_from_iso(iso_str) -> int:
    if not iso_str:
        return 0
    try:
        return datetime.fromisoformat(str(iso_str)).hour
    except Exception:
        return 0


def _risk_from_score(score: float) -> str:
    """Map anomaly_score (0-1) to risk label."""
    if score < 0.4:
        return 'low'
    elif score < 0.65:
        return 'medium'
    else:
        return 'high'


def _get_cluster_context(device_id: int, lat: float, lng: float) -> dict:
    """
    Helper used by Model 1 to find the nearest know cluster for a point.
    Returns distance information to integrate with the anomaly score.
    """
    clusters = list(
        RouteClusterMl.objects.filter(
            device_id=device_id,
            centroid_lat__isnull=False,
            centroid_lng__isnull=False,
        ).values('pk', 'cluster_id', 'centroid_lat', 'centroid_lng', 'label', 'density')
    )
    if not clusters:
        return {'has_clusters': False}

    min_dist = float('inf')
    nearest = None
    for c in clusters:
        d = _haversine(lat, lng, c['centroid_lat'], c['centroid_lng'])
        if d < min_dist:
            min_dist = d
            nearest = c

    return {
        'has_clusters': True,
        'min_distance': round(min_dist, 1),
        'nearest_cluster_id': nearest['cluster_id'] if nearest else None,
        'nearest_cluster_label': nearest.get('label') if nearest else None,
        'inside_cluster': min_dist <= 200,
    }


# ════════════════════════════════════════════════════════════════════════════
# 4. CLUSTERING SERVICE (Model 2 — DBSCAN)
# ════════════════════════════════════════════════════════════════════════════

class ClusteringService:
    """
    Identifies frequent zones (home, work, regular routes) per device using DBSCAN.

    - Does not save a .pkl file. Clusters are recalculated periodically.
    - Excludes anomalous points from training to learn only from normal behavior.
    - Saves results to route_clusters_ml for frontend visualization and Model 1 enrichment.
    """

    # DBSCAN parameters
    #
    # eps: radius in RADIANS for Ball Tree with Haversine metric.
    # 200m / 6_371_000m (Earth radius) = ~0.0000314 rad
    # We use 200m to avoid too many small fragmented clusters.
    EPS_METERS = 200
    EPS_RAD = EPS_METERS / 6_371_000   # convert to radians for haversine
    MIN_SAMPLES = 8         # Min 8 stopped-points needed to form a cluster
    MAX_SPEED_KMH = 10      # Only use GPS points where the vehicle was nearly stopped
    TRAINING_DAYS = 20

    def run_clustering(self, device_id: int, days: int = None) -> dict:
        """
        Run DBSCAN for a single device and persist cluster results.

        Returns:
            dict with n_clusters, n_noise, and list of cluster summaries
        """
        from sklearn.cluster import DBSCAN

        days = days or self.TRAINING_DAYS
        df = self._load_clean_points(device_id, days)

        if df is None or len(df) < self.MIN_SAMPLES * 2:
            logger.warning(f"[clustering] Not enough clean data for device {device_id} "
                           f"(need {self.MIN_SAMPLES * 2} stopped-point records)")
            return {'device_id': device_id, 'n_clusters': 0, 'n_noise': 0, 'error': 'insufficient_data'}

        # BACK TO 2D HAVERSINE FOR SPATIAL PRECISION
        # 3D (with hour) caused chaining: points at the same place but different hours
        # were merging into large corridors. 
        # For "Zones", we need pure Geographic clustering.
        
        # eps in radians for 150m
        eps_rad = 150 / 6_371_000

        X_rad = np.radians(df[['latitude', 'longitude']].values)
        
        db = DBSCAN(
            eps=eps_rad,
            min_samples=self.MIN_SAMPLES,
            algorithm='ball_tree',
            metric='haversine',
        )
        labels = db.fit_predict(X_rad)

        df = df.copy()
        df['cluster'] = labels

        n_noise = int((labels == -1).sum())
        unique_clusters = [l for l in set(labels) if l != -1]
        n_clusters = len(unique_clusters)

        logger.info(
            f"[clustering] device={device_id}: {len(df)} clean points → "
            f"{n_clusters} clusters, {n_noise} noise points"
        )

        # Compute max density for label classification (top 20% → 'main')
        density_threshold = None
        cluster_summaries = []
        for cid in sorted(unique_clusters):
            members = df[df['cluster'] == cid]
            c_lat = float(members['latitude'].mean())
            c_lng = float(members['longitude'].mean())
            count = len(members)
            
            # Count unique days this cluster was visited
            frequent_days = int(members['date'].nunique()) if 'date' in members.columns else 1
            
            # User scoring: point_count * frequent_days
            ranking_score = count * frequent_days

            radius = float(max(
                _haversine(row['latitude'], row['longitude'], c_lat, c_lng)
                for _, row in members.iterrows()
            ))
            cluster_summaries.append({
                'cluster_id': int(cid),
                'centroid_lat': c_lat,
                'centroid_lng': c_lng,
                'point_count': count,
                'frequent_days': frequent_days,
                'ranking_score': ranking_score,
                'radius': round(radius, 1),
                'density': float(count),
            })

        # Label top 2 targets as 'main'
        if cluster_summaries:
            sorted_by_score = sorted(cluster_summaries, key=lambda x: x['ranking_score'], reverse=True)
            main_ids = {c['cluster_id'] for c in sorted_by_score[:2]}
        else:
            main_ids = set()

        # Persist to DB (delete old + bulk insert)
        self._save_clusters(device_id, cluster_summaries, main_ids)

        return {
            'device_id': device_id,
            'n_clusters': n_clusters,
            'n_noise': n_noise,
            'clusters': [
                {**c, 'label': 'main' if c['cluster_id'] in main_ids else 'secondary'}
                for c in cluster_summaries
            ],
        }

    def run_all_vehicles(self, days: int = None) -> dict:
        """Run clustering for all active tracked devices."""
        devices = TrackedDevice.objects.filter(status='active')
        results = {}
        for device in devices:
            try:
                result = self.run_clustering(device.pk, days)
                results[device.pk] = result
            except Exception as e:
                logger.error(f"[clustering] ERROR device {device.pk}: {e}")
                results[device.pk] = {'error': str(e)}
        return results

    # ── Private helpers ──────────────────────────────────────────────────────

    def _load_clean_points(self, device_id: int, days: int) -> Optional[pd.DataFrame]:
        """
        Load GPS points from daily_routes_ml, keeping ONLY:
          - Points where speed < MAX_SPEED_KMH (vehicle was stopped or nearly stopped)
          - Points not flagged as anomalies

        This ensures DBSCAN detects real PLACES (parking spots, clients, base)
        rather than route corridors.
        """
        cutoff = date.today() - timedelta(days=days)
        routes = DailyRouteMl.objects.filter(
            device_id=device_id,
            date__gte=cutoff,
        ).order_by('date')

        if not routes.exists():
            return None

        # Collect confirmed anomaly coordinates to exclude
        since = datetime.combine(cutoff, datetime.min.time()).replace(tzinfo=tz.utc)
        anomaly_coords = {
            (round(a[0], 5), round(a[1], 5))
            for a in RouteAnomalyMl.objects.filter(
                device_id=device_id,
                detected_at__gte=since,
                is_anomaly=True,
                latitude__isnull=False,
                longitude__isnull=False,
            ).values_list('latitude', 'longitude')
        }

        rows = []
        for route in routes:
            if not route.route_json:
                continue
            
            for pt in route.route_json:
                lat = pt.get('latitude')
                lng = pt.get('longitude')
                speed = pt.get('speed') or 0

                if lat is None or lng is None:
                    continue

                # Filter only stopped/slow points
                if speed > self.MAX_SPEED_KMH:
                    continue

                # Exclude anomalies
                if (round(lat, 5), round(lng, 5)) in anomaly_coords:
                    continue
                
                # Extract hour
                hour = pt.get('hour')
                if hour is None and pt.get('recorded_at'):
                    hour = _hour_from_iso(pt.get('recorded_at'))
                
                rows.append({
                    'latitude': lat, 
                    'longitude': lng, 
                    'date': route.date,
                    'hour': hour or 0
                })

        if not rows:
            return None

        # Round coords slightly to merge near-duplicates
        df = pd.DataFrame(rows)
        df['lat_round'] = df['latitude'].round(4)
        df['lng_round'] = df['longitude'].round(4)
        # Deduplicate per location/day/hour to keep the dataset manageable but represent frequency
        df = df.drop_duplicates(subset=['lat_round', 'lng_round', 'date', 'hour'])
        return df

    def _save_clusters(self, device_id: int, summaries: list, main_ids: set):
        """Delete existing clusters for device and bulk-insert new ones."""
        from django.utils import timezone

        RouteClusterMl.objects.filter(device_id=device_id).delete()

        now = timezone.now()
        objs = [
            RouteClusterMl(
                device_id=device_id,
                cluster_id=c['cluster_id'],
                centroid_lat=c['centroid_lat'],
                centroid_lng=c['centroid_lng'],
                density=c['density'],
                point_count=c['point_count'],
                radius=c['radius'],
                label='main' if c['cluster_id'] in main_ids else 'secondary',
                updated_at=now,
            )
            for c in summaries
        ]
        RouteClusterMl.objects.bulk_create(objs, batch_size=200)
        logger.info(f"[clustering] Saved {len(objs)} clusters for device {device_id}")
