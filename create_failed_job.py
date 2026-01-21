#!/usr/bin/env python3
"""Create a test failed job in the database."""
import asyncio
import os
from datetime import datetime
import uuid

# Add the API service to path
import sys
sys.path.insert(0, '/workspace/services/api')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.ingest_job import IngestJob
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/workspace/services/api/.env')

DATABASE_URL = os.getenv('DATABASE_URL')

async def create_failed_job():
    """Create a test failed job."""
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Create a failed job
        job_id = str(uuid.uuid4())
        failed_job = IngestJob(
            id=job_id,
            status='failed',
            error_message='Test failure',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        session.add(failed_job)
        await session.commit()

        print(f"✅ Created failed job: {job_id}")
        return job_id

if __name__ == '__main__':
    job_id = asyncio.run(create_failed_job())
    print(f"Job ID: {job_id}")
