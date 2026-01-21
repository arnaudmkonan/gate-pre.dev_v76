import click
import httpx

API_URL = "http://localhost:8000"


@click.group()
def queue():
    """Queue management commands."""
    pass


@queue.command()
@click.option("--redis-host", prompt="Redis host", default="localhost", help="Redis host")
@click.option("--redis-port", prompt="Redis port", default=6379, type=int, help="Redis port")
@click.option("--redis-password", default=None, help="Redis password")
@click.option("--concurrency", default=4, type=int, help="Worker concurrency")
@click.option("--timeout", default=3600, type=int, help="Task timeout (seconds)")
@click.option("--max-retries", default=3, type=int, help="Max retries")
def configure(redis_host, redis_port, redis_password, concurrency, timeout, max_retries):
    """Configure queue (Redis/Celery)."""
    try:
        with httpx.Client() as client:
            response = client.post(
                f"{API_URL}/api/queue/config",
                json={
                    "redis_host": redis_host,
                    "redis_port": redis_port,
                    "redis_password": redis_password,
                    "worker_concurrency": concurrency,
                    "task_timeout": timeout,
                    "max_retries": max_retries,
                    "retry_backoff": True,
                },
            )

            if response.status_code == 201:
                data = response.json()
                click.secho("✓ Queue configured successfully", fg="green")
                click.echo(f"  ID: {data['id']}")
                click.echo(f"  Redis: {data['redis_host']}:{data['redis_port']}")
                click.echo(f"  Concurrency: {data['worker_concurrency']}")
            else:
                click.secho(f"✗ Failed: {response.text}", fg="red")

    except Exception as e:
        click.secho(f"✗ Error: {str(e)}", fg="red")


@queue.command()
def status():
    """Show queue status."""
    try:
        with httpx.Client() as client:
            response = client.get(f"{API_URL}/api/queue/status")

            if response.status_code == 200:
                data = response.json()
                click.echo("\n📊 Queue Status:")
                click.echo(f"  Pending:  {data['pending']} jobs")
                click.echo(f"  Running:  {data['running']} jobs")
                click.echo(f"  Failed:   {data['failed']} jobs")
                click.echo()
            else:
                click.secho(f"✗ Error: {response.text}", fg="red")

    except Exception as e:
        click.secho(f"✗ Error: {str(e)}", fg="red")


@queue.command()
@click.option("--page", default=1, type=int, help="Page number")
@click.option("--limit", default=20, type=int, help="Results per page")
@click.option("--status", default=None, help="Filter by status")
def list_jobs(page, limit, status):
    """List jobs."""
    try:
        with httpx.Client() as client:
            params = {"page": page, "page_size": limit}
            if status:
                params["status"] = status

            response = client.get(f"{API_URL}/api/queue/jobs", params=params)

            if response.status_code == 200:
                data = response.json()
                click.echo(f"\n📋 Jobs (Page {data['page']}/{(data['total'] + limit - 1) // limit}):")

                for job in data["items"]:
                    status_icon = {
                        "pending": "⏳",
                        "running": "▶️",
                        "completed": "✅",
                        "failed": "❌",
                    }.get(job["status"], "❓")

                    click.echo(f"\n{status_icon} {job['job_id']}")
                    click.echo(f"   Status: {job['status']}")
                    click.echo(f"   Retries: {job['retry_count']}")
                    click.echo(f"   Created: {job['created_at']}")
            else:
                click.secho(f"✗ Error: {response.text}", fg="red")

    except Exception as e:
        click.secho(f"✗ Error: {str(e)}", fg="red")


@queue.command()
@click.option("--limit", default=20, type=int, help="Limit results")
def show_dlq(limit):
    """Show dead letter queue."""
    try:
        with httpx.Client() as client:
            response = client.get(f"{API_URL}/api/queue/dlq", params={"limit": limit})

            if response.status_code == 200:
                data = response.json()
                click.echo(f"\n💀 Dead Letter Queue ({len(data)} items):")

                for dlq in data:
                    click.echo(f"\n❌ {dlq['job_id']}")
                    click.echo(f"   Error: {dlq['error_message'][:100]}...")
                    click.echo(f"   Created: {dlq['created_at']}")
            else:
                click.secho(f"✗ Error: {response.text}", fg="red")

    except Exception as e:
        click.secho(f"✗ Error: {str(e)}", fg="red")


@queue.command()
@click.option("--job-id", prompt="Job ID to retry", help="Job ID")
def retry(job_id):
    """Retry failed job."""
    try:
        with httpx.Client() as client:
            response = client.post(f"{API_URL}/api/queue/jobs/{job_id}/retry")

            if response.status_code == 200:
                click.secho(f"✓ Job {job_id} queued for retry", fg="green")
            else:
                click.secho(f"✗ Error: {response.text}", fg="red")

    except Exception as e:
        click.secho(f"✗ Error: {str(e)}", fg="red")


if __name__ == "__main__":
    queue()
