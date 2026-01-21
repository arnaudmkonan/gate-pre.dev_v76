import click
import httpx

API_URL = "http://localhost:8000"


@click.group()
def vector_store():
    """Vector store configuration commands."""
    pass


@vector_store.command()
@click.option("--backend", prompt="Vector backend", default="supabase", help="Backend type")
@click.option("--url", prompt="Vector store URL", help="Vector store URL")
@click.option("--api-key", prompt="API key", hide_input=True, help="API key")
@click.option("--embedding-model", default="text-embedding-3-small", help="Embedding model")
@click.option("--namespace", default=None, help="Namespace/Collection name")
def configure(backend, url, api_key, embedding_model, namespace):
    """Configure vector store."""
    try:
        with httpx.Client() as client:
            response = client.post(
                f"{API_URL}/api/vector-store/config",
                json={
                    "backend": backend,
                    "url": url,
                    "api_key": api_key,
                    "embedding_model": embedding_model,
                    "embedding_dimension": 1536,
                    "namespace_collection_name": namespace,
                },
            )

            if response.status_code == 201:
                data = response.json()
                click.secho("✓ Vector store configured successfully", fg="green")
                click.echo(f"  ID: {data['id']}")
                click.echo(f"  Backend: {data['backend']}")
                click.echo(f"  Model: {data['embedding_model']}")
                click.echo(f"  Dimension: {data['embedding_dimension']}")
            else:
                click.secho(f"✗ Failed: {response.text}", fg="red")

    except Exception as e:
        click.secho(f"✗ Error: {str(e)}", fg="red")


@vector_store.command()
def test_connection():
    """Test vector store connection."""
    try:
        with httpx.Client() as client:
            response = client.get(f"{API_URL}/api/vector-store/config")

            if response.status_code == 200:
                data = response.json()
                click.secho("✓ Vector store connection successful", fg="green")
                click.echo(f"  Backend: {data['backend']}")
                click.echo(f"  URL: {data['url']}")
                click.echo(f"  Model: {data['embedding_model']}")
            elif response.status_code == 404:
                click.secho("✗ No vector store configured. Run: vector-store configure", fg="yellow")
            else:
                click.secho(f"✗ Error: {response.text}", fg="red")

    except Exception as e:
        click.secho(f"✗ Error: {str(e)}", fg="red")


@vector_store.command()
def show_config():
    """Show vector store configuration."""
    try:
        with httpx.Client() as client:
            response = client.get(f"{API_URL}/api/vector-store/config")

            if response.status_code == 200:
                data = response.json()
                click.echo("\n🔍 Vector Store Configuration:")
                click.echo(f"  ID: {data['id']}")
                click.echo(f"  Backend: {data['backend']}")
                click.echo(f"  URL: {data['url']}")
                click.echo(f"  Model: {data['embedding_model']}")
                click.echo(f"  Dimension: {data['embedding_dimension']}")
                if data.get("namespace_collection_name"):
                    click.echo(f"  Namespace: {data['namespace_collection_name']}")
                click.echo(f"  Active: {data['is_active']}")
                click.echo()
            elif response.status_code == 404:
                click.secho("✗ No vector store configured", fg="yellow")
            else:
                click.secho(f"✗ Error: {response.text}", fg="red")

    except Exception as e:
        click.secho(f"✗ Error: {str(e)}", fg="red")


if __name__ == "__main__":
    vector_store()
