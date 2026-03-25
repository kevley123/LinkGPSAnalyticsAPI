"""
Analytics ML scaffold — anomaly detection training pipeline.
Reads from tracking.gps_positions (TimescaleDB), writes results to _ml tables.

Usage:
    python manage.py shell < analytics/anomaly_detector.py
    # Or call train() from a custom management command
"""
import os
import django

# ── Inputs: tracking.gps_positions + daily_routes_ml
# ── Outputs: route_anomalies_ml, route_clusters_ml, anomaly_models_ml

# Feature columns used for ML training
FEATURE_COLUMNS = ['speed', 'heading', 'altitude', 'accuracy', 'satellites']


def get_training_data(device_id: int, days: int = 30):
    """
    Fetch GPS positions for a device over the last N days.
    Returns a pandas DataFrame — requires: pandas, psycopg2
    """
    try:
        import pandas as pd
        from django.db import connection
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)

        sql = """
            SELECT
                id, device_id, recorded_at,
                ST_X(geom::geometry) AS longitude,
                ST_Y(geom::geometry) AS latitude,
                speed, heading, altitude, accuracy, satellites
            FROM tracking.gps_positions
            WHERE device_id = %s
              AND recorded_at >= %s
            ORDER BY recorded_at ASC
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [device_id, cutoff])
            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]

        df = pd.DataFrame(rows, columns=cols)
        return df
    except ImportError:
        raise ImportError("pandas is required for ML training: pip install pandas")


def train_isolation_forest(device_id: int, days: int = 30):
    """
    Train an Isolation Forest model for anomaly detection on a device's tracks.
    Saves the model and registers it in anomaly_models_ml.
    """
    try:
        import pandas as pd
        import joblib
        from datetime import date
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
        from django.utils import timezone

        df = get_training_data(device_id, days)
        if df.empty or len(df) < 50:
            print(f"[WARN] Not enough data for device {device_id} ({len(df)} rows)")
            return None

        features = df[FEATURE_COLUMNS].fillna(0)
        scaler = StandardScaler()
        X = scaler.fit_transform(features)

        model = IsolationForest(contamination=0.05, random_state=42, n_estimators=100)
        model.fit(X)

        # Save model to disk
        model_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, f'isolation_forest_device_{device_id}.joblib')
        joblib.dump({'model': model, 'scaler': scaler}, model_path)

        # Register in DB
        from core.application.use_cases.ml_use_cases import GetLatestAnomalyModel
        from core.infrastructure.repositories.ml_repository_impl import MLRepositoryImpl
        from core.domain.entities.ml_entities import AnomalyModelMl

        repo = MLRepositoryImpl()
        saved = repo.save_anomaly_model(AnomalyModelMl(
            id=0,
            device_id=device_id,
            model_path=model_path,
            model_type='IsolationForest',
            trained_from=date.today().replace(day=1),  # start of month
            trained_to=date.today(),
        ))

        print(f"[OK] Model trained for device {device_id} → {model_path}")
        return model_path

    except ImportError as e:
        raise ImportError(f"Missing ML dependency: {e}. Run: pip install scikit-learn joblib pandas")


def run_inference(device_id: int):
    """
    Run anomaly detection on recent positions and save results to route_anomalies_ml.
    """
    try:
        import joblib
        import numpy as np
        from datetime import datetime, timezone as tz
        from core.infrastructure.repositories.ml_repository_impl import MLRepositoryImpl
        from core.domain.entities.ml_entities import RouteAnomalyMl

        repo = MLRepositoryImpl()
        model_meta = repo.get_latest_model(device_id)
        if not model_meta or not model_meta.model_path:
            print(f"[WARN] No trained model for device {device_id}")
            return

        bundle = joblib.load(model_meta.model_path)
        model = bundle['model']
        scaler = bundle['scaler']

        df = get_training_data(device_id, days=1)  # last 24h
        if df.empty:
            print(f"[INFO] No recent data for device {device_id}")
            return

        features = df[FEATURE_COLUMNS].fillna(0)
        X = scaler.transform(features)
        scores = model.decision_function(X)   # lower = more anomalous
        labels = model.predict(X)             # -1 = anomaly, 1 = normal

        for i, row in df.iterrows():
            anomaly = RouteAnomalyMl(
                id=0,
                device_id=device_id,
                latitude=float(row.get('latitude', 0)),
                longitude=float(row.get('longitude', 0)),
                anomaly_score=float(-scores[i]),  # negate so higher = more anomalous
                is_anomaly=(labels[i] == -1),
                detected_at=datetime.now(tz=tz.utc),
                metadata={'source': 'IsolationForest', 'model_id': model_meta.id},
            )
            repo.save_route_anomaly(anomaly)

        count_anomalies = sum(1 for l in labels if l == -1)
        print(f"[OK] Inference complete for device {device_id}: {count_anomalies}/{len(labels)} anomalies detected")

    except ImportError as e:
        raise ImportError(f"Missing ML dependency: {e}. Run: pip install scikit-learn joblib pandas")


if __name__ == '__main__':
    # Example: train and infer for device 1
    device_id = 1
    train_isolation_forest(device_id, days=30)
    run_inference(device_id)
