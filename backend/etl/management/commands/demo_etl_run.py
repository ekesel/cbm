from django.core.management.base import BaseCommand
from etl.utils import etl_run, increment

class Command(BaseCommand):
    help = "Demonstrate creating an ETLJobRun"

    def handle(self, *args, **options):
        with etl_run("demo_job", mapping_version="v1", meta={"note":"demo"}) as run:
            increment(run, records_pulled=5)
            increment(run, records_normalized=4)
            # raise Exception("simulate failure")  # uncomment to see FAILED runs
        self.stdout.write(self.style.SUCCESS(f"Created ETL run {run.run_id} with status {run.status}"))
