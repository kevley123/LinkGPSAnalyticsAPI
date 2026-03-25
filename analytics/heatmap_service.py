import os
import json
import logging
from datetime import timedelta
import pandas as pd
import numpy as np
import h3
from django.conf import settings
from django.utils import timezone
from django.db import connection
from core.models import TrackedDevice, DeviceEvent, GeofenceEvent, Alert, RiskZone
from analytics.ml_pipeline import RouteAnomalyMl

logger = logging.getLogger(__name__)

class GlobalHeatmapService:
    """
    Model 3: Risk Zones Heatmap
    Aggregates Telemetry, Events, Alerts, and predefined Risk Zones into a 
    global spatial grid using H3 (resolution 8).
    """
    
    # H3 resolution 8 = ~0.7 km^2 per hexagon
    H3_RESOLUTION = 8
    
    # Weights for different data sources
    WEIGHT_TELEMETRY = 0.1
    WEIGHT_EVENT_CRITICAL = 0.8
    WEIGHT_EVENT_WARNING = 0.4
    WEIGHT_RISK_ZONE_MULTIPLIER = 1.5

    def __init__(self, days_lookback=30):
        self.days_lookback = days_lookback
        self.cutoff_date = timezone.now() - timedelta(days=self.days_lookback)
        
        # Ensure output directory exists
        self.output_dir = getattr(settings, 'HEATMAP_DATA_PATH', os.path.join(settings.BASE_DIR, 'heatmaps', 'global'))
        os.makedirs(self.output_dir, exist_ok=True)
        self.output_file = os.path.join(self.output_dir, 'heatmap_latest.json')

    def generate(self) -> dict:
        """
        Main pipeline: Extract, Enrich, Cluster, Normalize, and Save.
        """
        logger.info(f"[heatmap] Starting Model 3 generation (Lookback: {self.days_lookback} days)")
        
        # 1. Load Data
        df_base = self._load_telemetry()
        df_events = self._load_events()
        df_alerts = self._load_alerts()
        
        # Combine all points
        dfs = []
        if not df_base.empty: dfs.append(df_base)
        if not df_events.empty: dfs.append(df_events)
        if not df_alerts.empty: dfs.append(df_alerts)
        
        if not dfs:
            logger.warning("[heatmap] No data found to generate heatmap.")
            return {"status": "error", "message": "No data available"}
            
        df_all = pd.concat(dfs, ignore_index=True)
        
        # 2. Add H3 Spatial Index
        logger.info("[heatmap] Converting coordinates to H3 cells...")
        df_all['h3_cell'] = df_all.apply(
            lambda row: h3.geo_to_h3(row['lat'], row['lon'], self.H3_RESOLUTION), axis=1
        )
        
        # 3. Enrich with Risk Zones
        logger.info("[heatmap] Enriching with PostGIS Risk Zones...")
        risk_zones_cells = self._get_risk_zone_h3_cells()
        
        # Apply multiplier to existing telemetry/events that fall in a risk zone
        df_all['weight'] = df_all.apply(
            lambda row: row['weight'] * self.WEIGHT_RISK_ZONE_MULTIPLIER 
                        if row['h3_cell'] in risk_zones_cells 
                        else row['weight'],
            axis=1
        )
        
        # INJECT Risk Zones that have no telemetry, so they still render on the heatmap
        if risk_zones_cells:
            existing_cells = set(df_all['h3_cell'].unique())
            missing_risk_cells = risk_zones_cells - existing_cells
            
            if missing_risk_cells:
                risk_rows = []
                for cell in missing_risk_cells:
                    # Risk zones get a substantial baseline weight even without traffic
                    lat, lon = h3.h3_to_geo(cell)
                    risk_rows.append({
                        'lat': lat, 'lon': lon, 'type': 'static_risk_zone', 
                        'weight': 0.5, 'h3_cell': cell
                    })
                df_all = pd.concat([df_all, pd.DataFrame(risk_rows)], ignore_index=True)
        
        # 4. Aggregate by cell
        logger.info("[heatmap] Aggregating data by H3 cell...")
        agg_df = df_all.groupby('h3_cell').agg(
            total_weight=('weight', 'sum'),
            event_count=('type', 'count') # Count items
        ).reset_index()
        
        # 5. Normalize Intensity (0 to 1)
        if agg_df['total_weight'].max() > 0:
            # We use a logarithmic scale to prevent extreme outliers from crushing the scale
            agg_df['log_weight'] = np.log1p(agg_df['total_weight'])
            max_log = agg_df['log_weight'].max()
            agg_df['intensity'] = (agg_df['log_weight'] / max_log).round(4)
        else:
            agg_df['intensity'] = 0.0
            
        # Optional: Drop cells with very low intensity to keep JSON small
        agg_df = agg_df[agg_df['intensity'] > 0.05]
        
        # Add center coordinates for frontend rendering
        agg_df[['lat', 'lon']] = agg_df['h3_cell'].apply(
            lambda cell: pd.Series(h3.h3_to_geo(cell))
        )
        
        # 6. Format and Save
        result = agg_df[['h3_cell', 'lat', 'lon', 'intensity', 'event_count']].to_dict(orient='records')
        
        with open(self.output_file, 'w') as f:
            json.dump(result, f)
            
        logger.info(f"[heatmap] Generated {len(result)} H3 cells. Saved to {self.output_file}")
        
        return {
            "status": "success",
            "cells_generated": len(result),
            "file_path": self.output_file,
            "generated_at": timezone.now().isoformat()
        }

    def _load_telemetry(self) -> pd.DataFrame:
        """
        Extract sampled telemetry to form the baseline heatmap.
        Uses raw SQL to parse PostGIS geometry efficiently.
        """
        query = f"""
            SELECT 
                ST_Y(geom) as lat, 
                ST_X(geom) as lon
            FROM tracking.gps_positions
            WHERE recorded_at >= %s
              AND abs(speed) < 200
            -- Sample 1 every 20 points to keep baseline light
            AND id %% 20 = 0 
        """
        
        with connection.cursor() as cursor:
            cursor.execute(query, [self.cutoff_date])
            rows = cursor.fetchall()
            
        if not rows:
            return pd.DataFrame()
            
        df = pd.DataFrame(rows, columns=['lat', 'lon'])
        df['type'] = 'telemetry'
        df['weight'] = self.WEIGHT_TELEMETRY
        return df

    def _load_events(self) -> pd.DataFrame:
        """
        Extract logical events and assign weights based on type.
        """
        rows = []
        
        # 1. Device Events (e.g., Bloqueo de motor)
        dev_events = DeviceEvent.objects.filter(created_at__gte=self.cutoff_date)
        for ev in dev_events:
            meta = ev.metadata or {}
            # Check if metadata has location, else we'd need a join with gps_positions
            lat = meta.get('latitude') or meta.get('lat')
            lon = meta.get('longitude') or meta.get('lon')
            # Fallback to defaults or skip if no location
            if not lat or not lon:
                continue
                
            weight = self.WEIGHT_EVENT_CRITICAL if ev.event_type == 'bloqueo' else self.WEIGHT_EVENT_WARNING
            rows.append({
                'lat': float(lat), 'lon': float(lon), 
                'type': f'event_{ev.event_type}', 'weight': weight
            })
            
        return pd.DataFrame(rows)

    def _load_alerts(self) -> pd.DataFrame:
        """
        Extract IA Anomalies and standard Alerts.
        """
        rows = []
        
        # 1. ML Anomalies (Model 1 output)
        anomalies = RouteAnomalyMl.objects.filter(
            detected_at__gte=self.cutoff_date, 
            is_anomaly=True
        )
        for anom in anomalies:
            if anom.latitude and anom.longitude:
                # Use the AI score directly as weight
                rows.append({
                    'lat': anom.latitude, 'lon': anom.longitude, 
                    'type': 'ml_anomaly', 'weight': anom.anomaly_score
                })
                
        # 2. Standard Alerts
        alerts = Alert.objects.filter(created_at__gte=self.cutoff_date)
        for alert in alerts:
            meta = alert.metadata or {}
            lat = meta.get('latitude') or meta.get('lat')
            lon = meta.get('longitude') or meta.get('lon')
            if lat and lon:
                weight = self.WEIGHT_EVENT_CRITICAL if alert.severity == 'high' else self.WEIGHT_EVENT_WARNING
                rows.append({
                    'lat': float(lat), 'lon': float(lon), 
                    'type': f'alert_{alert.alert_type}', 'weight': weight
                })
        
        return pd.DataFrame(rows)

    def _get_risk_zone_h3_cells(self) -> set:
        """
        Fetches defined Risk Zones from PostGIS and converts their area to H3 cells.
        This allows O(1) intersection checks later.
        """
        # We extract both the GeoJSON for polyfill (large zones) and the Centroid (small zones)
        # to guarantee at least one H3 cell per risk zone even if it's smaller than the H3 resolution tick.
        query = """
            SELECT 
                ST_AsGeoJSON(geom), 
                ST_X(ST_Centroid(geom)) as lon, 
                ST_Y(ST_Centroid(geom)) as lat
            FROM public.risk_zones
            WHERE geom IS NOT NULL
        """
        
        risk_cells = set()
        with connection.cursor() as cursor:
            try:
                cursor.execute(query)
                rows = cursor.fetchall()
                
                for geojson_str, lon, lat in rows:
                    if not geojson_str or lon is None or lat is None:
                        continue
                        
                    # 1. Always add the centroid shell to guarantee small zones appear
                    center_cell = h3.geo_to_h3(lat, lon, self.H3_RESOLUTION)
                    risk_cells.add(center_cell)
                    
                    # 2. Add all internal cells for large zones
                    try:
                        geom = json.loads(geojson_str)
                        cells = h3.polyfill(geom, self.H3_RESOLUTION, geo_json_conformant=True)
                        risk_cells.update(cells)
                    except Exception as e:
                        logger.warning(f"[heatmap] Failed to polyfill geometry: {e}")
                        
            except Exception as e:
                logger.error(f"[heatmap] Could not extract risk zones: {e}")
                
        return risk_cells
