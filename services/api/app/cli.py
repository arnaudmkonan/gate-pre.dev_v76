import click

from app.tools.storage_cli import storage
from app.tools.queue_cli import queue
from app.tools.vector_store_cli import vector_store
from app.tools.click_cli import cli as click_commands
from app.tools.template_cli import template_cli


@click.group()
def cli():
    """DocuMind AI - Documentation Ingestion Platform CLI."""
    pass


# Add sub-commands
cli.add_command(storage)
cli.add_command(queue)
cli.add_command(vector_store)
cli.add_command(template_cli, name="templates")

# Add Click CLI commands (upload, monitor, storage configure)
# Note: The click_cli module has its own CLI group with upload, monitor, and storage commands
# We'll integrate them here by adding the main click_cli commands to this group
from app.tools.click_cli import upload, monitor, storage as click_storage
cli.add_command(upload)
cli.add_command(monitor)
cli.add_command(click_storage)


@cli.command()
def health():
    """Check API health."""
    try:
        import httpx

        response = httpx.get("http://localhost:8000/health")
        if response.status_code == 200:
            click.secho("✓ API is healthy", fg="green")
            click.echo(f"  Status: {response.json()}")
        else:
            click.secho("✗ API returned error", fg="red")
    except Exception as e:
        click.secho(f"✗ Could not reach API: {str(e)}", fg="red")


if __name__ == "__main__":
    cli()
