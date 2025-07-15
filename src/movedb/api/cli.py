"""CLI for managing the MoveDB database and API."""

import os
import sys
from pathlib import Path
from typing import List, Optional
import click
from uuid import UUID

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from movedb.api.database import create_db_and_tables, engine
from movedb.api.services import TrialService, BulkOperationService, AnalysisService
from movedb.api.enhanced_models import create_enhanced_trial_from_c3d
from movedb.core.trial import Trial as CoreTrial
from sqlmodel import Session


@click.group()
def cli():
    """MoveDB Core CLI for database and API management."""
    pass


@cli.command()
def init_db():
    """Initialize the database tables."""
    try:
        create_db_and_tables()
        click.echo("✅ Database tables created successfully!")
    except Exception as e:
        click.echo(f"❌ Error creating database tables: {e}")
        sys.exit(1)


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind the server to")
@click.option("--port", default=8000, help="Port to bind the server to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host: str, port: int, reload: bool):
    """Start the FastAPI server."""
    try:
        import uvicorn
        from movedb.api.app import app
        
        click.echo(f"🚀 Starting MoveDB API server on {host}:{port}")
        if reload:
            click.echo("🔄 Auto-reload enabled for development")
        
        uvicorn.run(
            "movedb.api.app:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
    except ImportError:
        click.echo("❌ uvicorn not installed. Please install with: pip install uvicorn[standard]")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error starting server: {e}")
        sys.exit(1)


@cli.command()
@click.argument("c3d_file", type=click.Path(exists=True, path_type=Path))
def import_c3d(c3d_file: Path):
    """Import a single C3D file as a trial."""
    try:
        with Session(engine) as session:
            # Load C3D file as core trial
            core_trial = CoreTrial.from_c3d_file(str(c3d_file))
            
            # Save to database
            service = TrialService(session)
            trial_id = service.core_to_db(core_trial)
            
            click.echo(f"✅ Imported {c3d_file.name} as trial {trial_id}")
    except Exception as e:
        click.echo(f"❌ Error importing {c3d_file}: {e}")
        sys.exit(1)


@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
def import_directory(directory: Path):
    """Import all C3D files from a directory."""
    try:
        with Session(engine) as session:
            service = BulkOperationService(session)
            trial_ids = service.import_trials_from_c3d_directory(str(directory))
            
            click.echo(f"✅ Imported {len(trial_ids)} trials from {directory}")
            for trial_id in trial_ids:
                click.echo(f"  - {trial_id}")
    except Exception as e:
        click.echo(f"❌ Error importing directory {directory}: {e}")
        sys.exit(1)


@cli.command()
@click.argument("trial_id", type=str)
@click.argument("output_dir", type=click.Path(path_type=Path))
@click.option("--formats", multiple=True, default=["trc", "mat", "pkl"], 
              help="Export formats (can be used multiple times)")
def export_trial(trial_id: str, output_dir: Path, formats: List[str]):
    """Export a trial to various formats."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with Session(engine) as session:
            service = BulkOperationService(session)
            exported_files = service.export_trial_to_formats(
                UUID(trial_id), 
                str(output_dir), 
                list(formats)
            )
            
            click.echo(f"✅ Exported trial {trial_id}:")
            for format_name, file_path in exported_files.items():
                click.echo(f"  - {format_name}: {file_path}")
    except ValueError:
        click.echo(f"❌ Invalid trial ID: {trial_id}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error exporting trial: {e}")
        sys.exit(1)


@cli.command()
def list_trials():
    """List all trials in the database."""
    try:
        from sqlmodel import select
        from movedb.api.models import Trial
        
        with Session(engine) as session:
            statement = select(Trial)
            trials = session.exec(statement).all()
            
            if not trials:
                click.echo("No trials found in database.")
                return
            
            click.echo(f"Found {len(trials)} trials:")
            click.echo("-" * 80)
            for trial in trials:
                click.echo(f"ID: {trial.id}")
                click.echo(f"Name: {trial.name}")
                click.echo(f"Session: {trial.session_name or 'N/A'}")
                click.echo(f"Classification: {trial.classification or 'N/A'}")
                click.echo(f"Created: {trial.created_at}")
                click.echo("-" * 80)
    except Exception as e:
        click.echo(f"❌ Error listing trials: {e}")
        sys.exit(1)


@cli.command()
@click.argument("trial_id", type=str)
def trial_stats(trial_id: str):
    """Show statistics for a specific trial."""
    try:
        with Session(engine) as session:
            service = AnalysisService(session)
            stats = service.get_trial_statistics(UUID(trial_id))
            
            click.echo(f"Statistics for trial: {stats['name']}")
            click.echo("-" * 50)
            click.echo(f"Duration (frames): {stats['duration_frames']}")
            click.echo(f"Duration (seconds): {stats['duration_seconds']:.2f}")
            click.echo(f"Number of events: {stats['num_events']}")
            click.echo(f"Number of force platforms: {stats['num_force_platforms']}")
            click.echo(f"Number of markers: {stats['num_markers']}")
            click.echo(f"Number of analog channels: {stats['num_analog_channels']}")
            
            if stats['point_gaps']:
                click.echo("Point gaps found:")
                for marker, gaps in stats['point_gaps'].items():
                    if gaps:
                        click.echo(f"  {marker}: {gaps}")
    except ValueError:
        click.echo(f"❌ Invalid trial ID: {trial_id}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error getting trial statistics: {e}")
        sys.exit(1)


@cli.command()
@click.option("--marker", help="Check gaps for specific marker only")
def find_gaps(marker: Optional[str]):
    """Find all trials with marker gaps."""
    try:
        with Session(engine) as session:
            service = AnalysisService(session)
            trials_with_gaps = service.find_trials_with_gaps(marker)
            
            if not trials_with_gaps:
                if marker:
                    click.echo(f"No trials found with gaps in marker: {marker}")
                else:
                    click.echo("No trials found with marker gaps.")
                return
            
            click.echo(f"Found {len(trials_with_gaps)} trials with gaps:")
            click.echo("-" * 80)
            
            for trial_info in trials_with_gaps:
                click.echo(f"Trial: {trial_info['trial_name']} (ID: {trial_info['trial_id']})")
                click.echo("Gaps:")
                for marker_name, gaps in trial_info['gaps'].items():
                    click.echo(f"  {marker_name}: {gaps}")
                click.echo("-" * 80)
    except Exception as e:
        click.echo(f"❌ Error finding gaps: {e}")
        sys.exit(1)


@cli.command()
def check_db():
    """Check database connection and show configuration."""
    try:
        from movedb.api.database import get_database_url
        
        # Test connection
        with Session(engine) as session:
            session.exec("SELECT 1").first()
        
        click.echo("✅ Database connection successful!")
        click.echo(f"Database URL: {get_database_url()}")
        
        # Count tables
        from sqlmodel import text
        with Session(engine) as session:
            result = session.exec(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)).all()
            
            click.echo(f"Found {len(result)} tables:")
            for table in result:
                click.echo(f"  - {table}")
                
    except Exception as e:
        click.echo(f"❌ Database connection failed: {e}")
        click.echo("Make sure PostgreSQL is running and DATABASE_URL is correct.")
        sys.exit(1)


if __name__ == "__main__":
    cli()
