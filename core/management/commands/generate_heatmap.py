from django.core.management.base import BaseCommand
from analytics.heatmap_service import GlobalHeatmapService

class Command(BaseCommand):
    help = 'Generates the Global Risk Heatmap JSON file (Model 3)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', 
            type=int, 
            default=30, 
            help='Lookback period in days (default: 30)'
        )

    def handle(self, *args, **options):
        days = options['days']
        
        self.stdout.write(f"Starting Global Risk Heatmap generation (Last {days} days)...")
        
        service = GlobalHeatmapService(days_lookback=days)
        result = service.generate()
        
        if result.get("status") == "success":
            self.stdout.write(self.style.SUCCESS(
                f"Successfully generated heatmap with {result['cells_generated']} H3 cells."
            ))
            self.stdout.write(f"Saved to: {result['file_path']}")
        else:
            self.stdout.write(self.style.ERROR(
                f"Failed to generate heatmap: {result.get('message')}"
            ))
