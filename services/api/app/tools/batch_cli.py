"""CLI tools for batch processing operations."""
import json
import logging
from datetime import datetime
from typing import Optional

import click
import httpx
from croniter import croniter

logger = logging.getLogger(__name__)


class BatchClient:
    """Client for interacting with batch processing API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=30.0)

    def create_schedule(
        self,
        schedule_name: str,
        cron_expression: str,
        batch_size: int = 10,
        max_concurrency: int = 5,
        description: Optional[str] = None,
    ) -> dict:
        """Create a new batch schedule."""
        payload = {
            "schedule_name": schedule_name,
            "cron_expression": cron_expression,
            "batch_size": batch_size,
            "max_concurrency": max_concurrency,
            "description": description,
        }
        response = self.client.post("/api/batch/schedules", json=payload)
        response.raise_for_status()
        return response.json()

    def list_schedules(self, is_active: Optional[bool] = None) -> list:
        """List batch schedules."""
        params = {}
        if is_active is not None:
            params["is_active"] = is_active

        response = self.client.get("/api/batch/schedules", params=params)
        response.raise_for_status()
        return response.json()

    def get_schedule(self, schedule_id: str) -> dict:
        """Get a batch schedule by ID."""
        response = self.client.get(f"/api/batch/schedules/{schedule_id}")
        response.raise_for_status()
        return response.json()

    def update_schedule(
        self,
        schedule_id: str,
        schedule_name: Optional[str] = None,
        cron_expression: Optional[str] = None,
        batch_size: Optional[int] = None,
        max_concurrency: Optional[int] = None,
        is_active: Optional[bool] = None,
        description: Optional[str] = None,
    ) -> dict:
        """Update a batch schedule."""
        payload = {}
        if schedule_name is not None:
            payload["schedule_name"] = schedule_name
        if cron_expression is not None:
            payload["cron_expression"] = cron_expression
        if batch_size is not None:
            payload["batch_size"] = batch_size
        if max_concurrency is not None:
            payload["max_concurrency"] = max_concurrency
        if is_active is not None:
            payload["is_active"] = is_active
        if description is not None:
            payload["description"] = description

        response = self.client.put(f"/api/batch/schedules/{schedule_id}", json=payload)
        response.raise_for_status()
        return response.json()

    def delete_schedule(self, schedule_id: str) -> None:
        """Delete a batch schedule."""
        response = self.client.delete(f"/api/batch/schedules/{schedule_id}")
        response.raise_for_status()

    def close(self):
        """Close the HTTP client."""
        self.client.close()


@click.group()
def batch_cli():
    """Batch processing CLI for managing ingestion schedules."""
    pass


@batch_cli.command()
@click.option(
    "--schedule-name", required=True, help="Unique name for the schedule"
)
@click.option(
    "--cron",
    "cron_expression",
    required=True,
    help='Cron expression (e.g., "0 * * * *" for hourly)',
)
@click.option(
    "--batch-size", default=10, type=int, help="Jobs per batch (default: 10)"
)
@click.option(
    "--max-concurrency",
    default=5,
    type=int,
    help="Max concurrent jobs (default: 5)",
)
@click.option("--description", default=None, help="Schedule description")
@click.option("--api-url", default="http://localhost:8000", help="API base URL")
def create(
    schedule_name: str,
    cron_expression: str,
    batch_size: int,
    max_concurrency: int,
    description: Optional[str],
    api_url: str,
):
    """Create a new batch schedule."""
    try:
        # Validate cron expression
        try:
            croniter(cron_expression)
        except Exception:
            click.echo(f"✗ Invalid cron expression: {cron_expression}", err=True)
            raise click.ClickException("Cron expression is invalid")

        client = BatchClient(api_url)
        schedule = client.create_schedule(
            schedule_name=schedule_name,
            cron_expression=cron_expression,
            batch_size=batch_size,
            max_concurrency=max_concurrency,
            description=description,
        )

        click.echo(f"✓ Schedule created: {schedule['id']}")
        click.echo(f"  Name: {schedule['schedule_name']}")
        click.echo(f"  Cron: {schedule['cron_expression']}")
        click.echo(f"  Batch Size: {schedule['batch_size']}")
        click.echo(f"  Max Concurrency: {schedule['max_concurrency']}")
        click.echo(f"  Next Run: {schedule.get('next_run_at', 'N/A')}")
        client.close()

    except Exception as e:
        click.echo(f"✗ Error creating schedule: {e}", err=True)
        raise click.ClickException(str(e))


@batch_cli.command()
@click.option(
    "--is-active",
    type=bool,
    default=None,
    help="Filter by active status (true/false)",
)
@click.option("--api-url", default="http://localhost:8000", help="API base URL")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def list(is_active: Optional[bool], api_url: str, output_json: bool):
    """List batch schedules."""
    try:
        client = BatchClient(api_url)
        schedules = client.list_schedules(is_active=is_active)

        if output_json:
            click.echo(json.dumps(schedules, indent=2, default=str))
        else:
            if not schedules:
                click.echo("No schedules found")
                return

            click.echo(f"Found {len(schedules)} schedule(s):\n")
            for schedule in schedules:
                status = "ACTIVE" if schedule.get("is_active") else "INACTIVE"
                click.echo(f"  ID: {schedule['id']}")
                click.echo(f"  Name: {schedule['schedule_name']}")
                click.echo(f"  Status: {status}")
                click.echo(f"  Cron: {schedule['cron_expression']}")
                click.echo(f"  Batch Size: {schedule['batch_size']}")
                click.echo(f"  Max Concurrency: {schedule['max_concurrency']}")
                click.echo(f"  Next Run: {schedule.get('next_run_at', 'N/A')}")
                click.echo()

        client.close()

    except Exception as e:
        click.echo(f"✗ Error listing schedules: {e}", err=True)
        raise click.ClickException(str(e))


@batch_cli.command()
@click.argument("schedule_id")
@click.option("--api-url", default="http://localhost:8000", help="API base URL")
def show(schedule_id: str, api_url: str):
    """Show details of a specific schedule."""
    try:
        client = BatchClient(api_url)
        schedule = client.get_schedule(schedule_id)

        click.echo(f"\nSchedule: {schedule['schedule_name']}")
        click.echo(f"  ID: {schedule['id']}")
        click.echo(f"  Status: {'ACTIVE' if schedule.get('is_active') else 'INACTIVE'}")
        click.echo(f"  Cron: {schedule['cron_expression']}")
        click.echo(f"  Batch Size: {schedule['batch_size']}")
        click.echo(f"  Max Concurrency: {schedule['max_concurrency']}")
        click.echo(f"  Last Run: {schedule.get('last_run_at', 'Never')}")
        click.echo(f"  Next Run: {schedule.get('next_run_at', 'TBD')}")
        if schedule.get("description"):
            click.echo(f"  Description: {schedule['description']}")
        click.echo()

        client.close()

    except Exception as e:
        click.echo(f"✗ Error retrieving schedule: {e}", err=True)
        raise click.ClickException(str(e))


@batch_cli.command()
@click.argument("schedule_id")
@click.option(
    "--schedule-name", default=None, help="New schedule name"
)
@click.option(
    "--cron", "cron_expression", default=None, help="New cron expression"
)
@click.option("--batch-size", type=int, default=None, help="New batch size")
@click.option(
    "--max-concurrency", type=int, default=None, help="New max concurrency"
)
@click.option("--is-active", type=bool, default=None, help="Set active status")
@click.option("--description", default=None, help="New description")
@click.option("--api-url", default="http://localhost:8000", help="API base URL")
def update(
    schedule_id: str,
    schedule_name: Optional[str],
    cron_expression: Optional[str],
    batch_size: Optional[int],
    max_concurrency: Optional[int],
    is_active: Optional[bool],
    description: Optional[str],
    api_url: str,
):
    """Update a batch schedule."""
    try:
        client = BatchClient(api_url)
        updated = client.update_schedule(
            schedule_id,
            schedule_name=schedule_name,
            cron_expression=cron_expression,
            batch_size=batch_size,
            max_concurrency=max_concurrency,
            is_active=is_active,
            description=description,
        )

        click.echo(f"✓ Schedule updated: {updated['schedule_name']}")
        click.echo(f"  Status: {'ACTIVE' if updated.get('is_active') else 'INACTIVE'}")
        click.echo(f"  Cron: {updated['cron_expression']}")
        click.echo(f"  Batch Size: {updated['batch_size']}")
        click.echo(f"  Max Concurrency: {updated['max_concurrency']}")
        client.close()

    except Exception as e:
        click.echo(f"✗ Error updating schedule: {e}", err=True)
        raise click.ClickException(str(e))


@batch_cli.command()
@click.argument("schedule_id")
@click.option("--api-url", default="http://localhost:8000", help="API base URL")
@click.confirmation_option(prompt="Are you sure you want to delete this schedule?")
def delete(schedule_id: str, api_url: str):
    """Delete a batch schedule."""
    try:
        client = BatchClient(api_url)
        client.delete_schedule(schedule_id)

        click.echo(f"✓ Schedule deleted: {schedule_id}")
        client.close()

    except Exception as e:
        click.echo(f"✗ Error deleting schedule: {e}", err=True)
        raise click.ClickException(str(e))


if __name__ == "__main__":
    batch_cli()
