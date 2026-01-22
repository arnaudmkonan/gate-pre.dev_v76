"""
Template CLI.

Command-line interface for managing document extraction templates.
"""

import asyncio
import json
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


@click.group()
def template_cli():
    """Template management commands for DocuMind AI."""
    pass


@template_cli.command("list")
@click.option("--on-disk", is_flag=True, help="List templates available on disk")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def list_templates(on_disk: bool, json_output: bool):
    """List available document type templates."""
    from app.services.template_loader_service import TemplateLoaderService
    
    if on_disk:
        templates = TemplateLoaderService.list_available_templates()
        
        if json_output:
            click.echo(json.dumps(templates, indent=2))
            return
        
        table = Table(title="📄 Available Templates (On Disk)")
        table.add_column("Document Type", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Fields", justify="right")
        table.add_column("Version")
        table.add_column("Prompt", justify="center")
        
        for t in templates:
            table.add_row(
                t["document_type"],
                t["name"],
                str(t["field_count"]),
                t["version"],
                "✅" if t["has_prompt"] else "❌"
            )
        
        console.print(table)
    else:
        # List from database
        asyncio.run(_list_db_templates(json_output))


async def _list_db_templates(json_output: bool):
    """List templates from database."""
    from app.core.database import AsyncSessionLocal
    from app.services.template_service import TemplateService
    
    async with AsyncSessionLocal() as session:
        templates = await TemplateService.list_templates(session, is_active=None)
        
        if json_output:
            data = [t.to_dict() for t in templates]
            click.echo(json.dumps(data, indent=2, default=str))
            return
        
        table = Table(title="📄 Templates in Database")
        table.add_column("ID", style="dim")
        table.add_column("Name", style="green")
        table.add_column("Document Type", style="cyan")
        table.add_column("Fields", justify="right")
        table.add_column("Usage", justify="right")
        table.add_column("Version", justify="right")
        table.add_column("Active", justify="center")
        
        for t in templates:
            field_count = len(t.field_definitions) if t.field_definitions else 0
            table.add_row(
                str(t.id)[:8],
                t.name,
                t.document_type,
                str(field_count),
                str(t.usage_count),
                f"v{t.version}",
                "✅" if t.is_active else "❌"
            )
        
        console.print(table)


@template_cli.command("seed")
@click.option("--force", is_flag=True, help="Force update existing templates")
@click.option("--type", "doc_type", help="Seed only a specific document type")
def seed_templates(force: bool, doc_type: str):
    """Seed predefined templates into the database."""
    asyncio.run(_seed_templates(force, doc_type))


async def _seed_templates(force: bool, doc_type: str):
    """Seed templates into database."""
    from app.core.database import AsyncSessionLocal
    from app.services.template_loader_service import TemplateLoaderService, DOCUMENT_TYPES
    
    if doc_type and doc_type not in DOCUMENT_TYPES:
        console.print(f"[red]Unknown document type: {doc_type}[/red]")
        console.print(f"Available types: {', '.join(DOCUMENT_TYPES)}")
        return
    
    console.print("[bold]🌱 Seeding document templates...[/bold]")
    
    async with AsyncSessionLocal() as session:
        if doc_type:
            template = await TemplateLoaderService.seed_template(session, doc_type, force)
            if template:
                console.print(f"[green]✅ Seeded: {template.name}[/green]")
            else:
                console.print(f"[red]❌ Failed to seed: {doc_type}[/red]")
        else:
            results = await TemplateLoaderService.seed_all_templates(session, force)
            
            console.print(f"\n[bold]Results:[/bold]")
            for dtype, template in results.items():
                field_count = len(template.field_definitions) if template.field_definitions else 0
                console.print(f"  [green]✅[/green] {template.name} ({field_count} fields)")
            
            console.print(f"\n[bold green]Successfully seeded {len(results)} templates[/bold green]")


@template_cli.command("validate")
@click.argument("doc_type")
def validate_template(doc_type: str):
    """Validate a template schema definition."""
    from app.services.template_loader_service import TemplateLoaderService
    
    schema = TemplateLoaderService.load_template_schema(doc_type)
    if not schema:
        console.print(f"[red]Template not found: {doc_type}[/red]")
        return
    
    errors = TemplateLoaderService.validate_template_schema(schema)
    
    if errors:
        console.print(f"[red]❌ Validation failed for {doc_type}:[/red]")
        for error in errors:
            console.print(f"  • {error}")
    else:
        console.print(f"[green]✅ Template {doc_type} is valid[/green]")
        
        # Show summary
        field_count = len(schema.get("field_definitions", []))
        required_count = len([f for f in schema.get("field_definitions", []) if f.get("required")])
        
        console.print(Panel(
            f"""[bold]{schema.get('template_name')}[/bold]

{schema.get('description', 'No description')}

[cyan]Fields:[/cyan] {field_count} ({required_count} required)
[cyan]Confidence Threshold:[/cyan] {schema.get('confidence_threshold', 0.75)}
[cyan]Keywords:[/cyan] {len(schema.get('matching_keywords', []))} defined
[cyan]Categories:[/cyan] {', '.join(schema.get('classification_categories', []))}
""",
            title=f"Template: {doc_type}"
        ))


@template_cli.command("show")
@click.argument("doc_type")
@click.option("--fields", is_flag=True, help="Show field definitions")
def show_template(doc_type: str, fields: bool):
    """Show details of a template schema."""
    from app.services.template_loader_service import TemplateLoaderService
    
    schema = TemplateLoaderService.load_template_schema(doc_type)
    if not schema:
        console.print(f"[red]Template not found: {doc_type}[/red]")
        return
    
    console.print(f"\n[bold cyan]{schema.get('template_name')}[/bold cyan]")
    console.print(f"Document Type: {schema.get('document_type')}")
    console.print(f"Version: {schema.get('version', '1.0.0')}")
    console.print(f"\n{schema.get('description', '')}\n")
    
    if fields:
        table = Table(title="Field Definitions")
        table.add_column("Field Name", style="cyan")
        table.add_column("Display Name")
        table.add_column("Type")
        table.add_column("Required", justify="center")
        table.add_column("Entity Type")
        
        for field in schema.get("field_definitions", []):
            table.add_row(
                field.get("field_name"),
                field.get("display_name", ""),
                field.get("field_type", "string"),
                "✓" if field.get("required") else "",
                field.get("entity_type", "")
            )
        
        console.print(table)
    else:
        console.print(f"[dim]Use --fields to see field definitions[/dim]")


@template_cli.command("stats")
def template_stats():
    """Show template usage statistics."""
    asyncio.run(_show_stats())


async def _show_stats():
    """Show template statistics."""
    from app.core.database import AsyncSessionLocal
    from app.services.template_loader_service import TemplateLoaderService
    
    async with AsyncSessionLocal() as session:
        stats = await TemplateLoaderService.get_template_stats(session)
        
        console.print(Panel(
            f"""[bold]Template Statistics[/bold]

[cyan]Total Templates:[/cyan] {stats['total_templates']}
[cyan]Active Templates:[/cyan] {stats['active_templates']}
[cyan]Available on Disk:[/cyan] {stats['available_on_disk']}
""",
            title="📊 Overview"
        ))
        
        if stats["usage_by_template"]:
            table = Table(title="Usage by Template")
            table.add_column("Template", style="green")
            table.add_column("Document Type", style="cyan")
            table.add_column("Usage Count", justify="right")
            table.add_column("Avg Confidence", justify="right")
            
            for row in stats["usage_by_template"]:
                conf = f"{row['avg_confidence']:.1%}" if row["avg_confidence"] else "N/A"
                table.add_row(
                    row["name"],
                    row["document_type"],
                    str(row["usage_count"]),
                    conf
                )
            
            console.print(table)


@template_cli.command("export")
@click.argument("doc_type")
@click.option("--output", "-o", help="Output file path")
def export_template(doc_type: str, output: str):
    """Export a template schema to JSON file."""
    from app.services.template_loader_service import TemplateLoaderService
    
    schema = TemplateLoaderService.load_template_schema(doc_type)
    if not schema:
        console.print(f"[red]Template not found: {doc_type}[/red]")
        return
    
    # Add prompt if available
    prompt = TemplateLoaderService.load_template_prompt(doc_type)
    if prompt:
        schema["extraction_prompt"] = prompt
    
    output_path = output or f"{doc_type}-template.json"
    
    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2)
    
    console.print(f"[green]✅ Exported to: {output_path}[/green]")


if __name__ == "__main__":
    template_cli()
