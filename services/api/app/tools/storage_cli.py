import asyncio
import logging

import click
import httpx

logger = logging.getLogger(__name__)
API_URL = "http://localhost:8000"


@click.group()
def storage():
    """Storage configuration commands."""
    pass


@storage.command()
@click.option("--provider", default="supabase", help="Storage provider")
@click.option("--endpoint", prompt="Storage endpoint URL", help="Storage endpoint")
@click.option("--bucket", prompt="Bucket name", help="Bucket name")
@click.option("--region", default="us-east-1", help="Region")
@click.option("--access-key", prompt="Access key", hide_input=True, help="Access key")
@click.option("--secret-key", prompt="Secret key", hide_input=True, help="Secret key")
@click.option("--max-size", default=100, help="Max file size in MB")
def configure(provider, endpoint, bucket, region, access_key, secret_key, max_size):
    """Configure storage provider."""
    try:
        with httpx.Client() as client:
            response = client.post(
                f"{API_URL}/api/storage/config",
                json={
                    "provider": provider,
                    "endpoint": endpoint,
                    "bucket_name": bucket,
                    "region": region,
                    "access_key": access_key,
                    "secret_key": secret_key,
                    "max_file_size_mb": max_size,
                },
            )

            if response.status_code == 201:
                data = response.json()
                click.secho("✓ Storage configured successfully", fg="green")
                click.echo(f"  ID: {data['id']}")
                click.echo(f"  Provider: {data['provider']}")
                click.echo(f"  Bucket: {data['bucket_name']}")
            else:
                click.secho(f"✗ Failed: {response.text}", fg="red")

    except Exception as e:
        click.secho(f"✗ Error: {str(e)}", fg="red")


@storage.command()
def test_connection():
    """Test storage connection."""
    try:
        with httpx.Client() as client:
            response = client.get(f"{API_URL}/api/storage/config")

            if response.status_code == 200:
                data = response.json()
                click.secho("✓ Storage connection successful", fg="green")
                click.echo(f"  Provider: {data['provider']}")
                click.echo(f"  Endpoint: {data['endpoint']}")
                click.echo(f"  Bucket: {data['bucket_name']}")
            elif response.status_code == 404:
                click.secho("✗ No storage configured. Run: storage configure", fg="yellow")
            else:
                click.secho(f"✗ Error: {response.text}", fg="red")

    except Exception as e:
        click.secho(f"✗ Error: {str(e)}", fg="red")


@storage.command()
def show_config():
    """Show storage configuration."""
    try:
        with httpx.Client() as client:
            response = client.get(f"{API_URL}/api/storage/config")

            if response.status_code == 200:
                data = response.json()
                click.echo("\n📦 Storage Configuration:")
                click.echo(f"  ID: {data['id']}")
                click.echo(f"  Provider: {data['provider']}")
                click.echo(f"  Endpoint: {data['endpoint']}")
                click.echo(f"  Bucket: {data['bucket_name']}")
                click.echo(f"  Region: {data['region']}")
                click.echo(f"  Max Size: {data['max_file_size_mb']}MB")
                click.echo(f"  Active: {data['is_active']}")
                click.echo()
            elif response.status_code == 404:
                click.secho("✗ No storage configured", fg="yellow")
            else:
                click.secho(f"✗ Error: {response.text}", fg="red")

    except Exception as e:
        click.secho(f"✗ Error: {str(e)}", fg="red")


if __name__ == "__main__":
    storage()
