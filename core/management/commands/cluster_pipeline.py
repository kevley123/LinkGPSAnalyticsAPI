"""
Management command for Model 2 — DBSCAN Route Clustering.

Usage:
    python manage.py cluster_pipeline --device 4
    python manage.py cluster_pipeline --all
"""
from django.core.management.base import BaseCommand
from analytics.ml_pipeline import ClusteringService


class Command(BaseCommand):
    help = 'Run DBSCAN clustering pipeline for one or all devices (Model 2)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--device', type=int, default=None,
            help='Internal device_id to cluster'
        )
        parser.add_argument(
            '--all', action='store_true',
            help='Run clustering for all active devices'
        )
        parser.add_argument(
            '--days', type=int, default=20,
            help='Number of days of historical data to use (default: 20)'
        )

    def handle(self, *args, **options):
        service = ClusteringService()

        if options['all']:
            self.stdout.write("Running clustering for ALL active devices...")
            results = service.run_all_vehicles(days=options['days'])
            for device_id, result in results.items():
                if 'error' in result:
                    self.stdout.write(self.style.ERROR(
                        f"  ✗ Device {device_id}: {result.get('error')}"
                    ))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✓ Device {device_id}: "
                        f"{result['n_clusters']} clusters, {result['n_noise']} noise points"
                    ))

        elif options['device']:
            device_id = options['device']
            self.stdout.write(f"Running clustering for device {device_id}...")
            result = service.run_clustering(device_id, days=options['days'])

            if 'error' in result:
                self.stdout.write(self.style.ERROR(
                    f"  ✗ {result.get('error')}"
                ))
                return

            self.stdout.write(self.style.SUCCESS(
                f"\n✓ Clustering complete for device {device_id}"
            ))
            self.stdout.write(f"  Clusters found : {result['n_clusters']}")
            self.stdout.write(f"  Noise points   : {result['n_noise']}")
            for c in result.get('clusters', []):
                label = '[MAIN]' if c['label'] == 'main' else '      '
                self.stdout.write(
                    f"  {label} Cluster {c['cluster_id']:2d}: "
                    f"({c['centroid_lat']:.5f}, {c['centroid_lng']:.5f}) "
                    f"| {c['point_count']} pts | r={c['radius']:.0f}m"
                )
        else:
            self.stderr.write("Please specify --device <id> or --all")
