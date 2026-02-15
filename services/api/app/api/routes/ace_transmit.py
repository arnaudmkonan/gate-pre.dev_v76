"""
ACE Transmission API Routes.

Endpoints for transmitting entries to CBP ACE system.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.database import get_db
from app.services.ace_transmitter import ACETransmitter, TransmissionMode

router = APIRouter(prefix="/api/ace/transmit", tags=["ACE Transmission"])


class TransmitRequest(BaseModel):
    """Request to transmit entry to ACE."""
    entry_id: UUID


class BatchTransmitRequest(BaseModel):
    """Request to transmit multiple entries."""
    entry_ids: List[UUID]


class TransmissionStatusResponse(BaseModel):
    """Response with transmission connection status."""
    mode: str
    sftp_enabled: bool
    sftp_host: str
    sftp_port: int
    sftp_user: str
    key_configured: bool
    upload_path: str
    response_path: str
    ready_for_live: bool


@router.post("/entry/{entry_id}")
async def transmit_entry(
    entry_id: UUID,
    db=Depends(get_db),
):
    """
    Transmit a single entry to ACE.
    
    This will:
    1. Generate the ABI file for the entry
    2. Upload to ACE SFTP (or simulate if not configured)
    3. Update entry status to 'filing'
    
    Returns transmission result with confirmation ID.
    """
    transmitter = ACETransmitter(db)
    result = await transmitter.transmit_entry(entry_id)
    
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "transmission_failed",
                "message": result.error,
                "entry_id": str(entry_id),
            }
        )
    
    return result.to_dict()


@router.post("/batch")
async def transmit_batch(
    request: BatchTransmitRequest,
    db=Depends(get_db),
):
    """
    Transmit multiple entries to ACE.
    
    Processes entries sequentially and returns summary.
    """
    if len(request.entry_ids) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 entries per batch",
        )
    
    transmitter = ACETransmitter(db)
    return await transmitter.transmit_batch(request.entry_ids)


@router.get("/status/{entry_id}")
async def check_transmission_status(
    entry_id: UUID,
    db=Depends(get_db),
):
    """
    Check ACE response status for a transmitted entry.
    
    Polls for CBP response and returns current status.
    """
    transmitter = ACETransmitter(db)
    result = await transmitter.check_response(entry_id)
    return result.to_dict()


@router.get("/connection")
async def get_connection_status(
    db=Depends(get_db),
):
    """
    Get ACE SFTP connection status.
    
    Returns configuration status and whether system is ready
    for live transmission.
    """
    transmitter = ACETransmitter(db)
    return transmitter.get_connection_status()


@router.post("/test-connection")
async def test_connection(
    db=Depends(get_db),
):
    """
    Test ACE SFTP connection without transmitting.
    
    Attempts to connect to configured SFTP server and
    list contents of upload directory.
    """
    transmitter = ACETransmitter(db)
    
    if transmitter.mode != TransmissionMode.LIVE:
        return {
            "success": False,
            "mode": transmitter.mode.value,
            "message": "ACE SFTP not configured. Set ACE_SFTP_ENABLED=true and configure credentials.",
            "configuration": transmitter.get_connection_status(),
        }
    
    # Test connection
    try:
        import paramiko
        import os
        
        if not os.path.exists(transmitter.sftp_key_path):
            return {
                "success": False,
                "message": f"SFTP key file not found: {transmitter.sftp_key_path}",
            }
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        private_key = paramiko.RSAKey.from_private_key_file(transmitter.sftp_key_path)
        
        ssh.connect(
            hostname=transmitter.sftp_host,
            port=transmitter.sftp_port,
            username=transmitter.sftp_user,
            pkey=private_key,
            timeout=10,
        )
        
        sftp = ssh.open_sftp()
        
        # Try to list upload directory
        try:
            files = sftp.listdir(transmitter.upload_path)
            upload_accessible = True
        except Exception:
            files = []
            upload_accessible = False
        
        sftp.close()
        ssh.close()
        
        return {
            "success": True,
            "mode": "live",
            "message": "Successfully connected to ACE SFTP",
            "upload_path_accessible": upload_accessible,
            "files_in_upload": len(files),
        }
        
    except paramiko.AuthenticationException as e:
        return {
            "success": False,
            "message": f"Authentication failed: {e}",
        }
    except paramiko.SSHException as e:
        return {
            "success": False,
            "message": f"SSH connection error: {e}",
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection error: {e}",
        }


@router.get("/mode")
async def get_transmission_mode(
    db=Depends(get_db),
):
    """
    Get current transmission mode.
    
    Returns 'live' if ACE SFTP is configured, 'simulation' otherwise.
    """
    transmitter = ACETransmitter(db)
    return {
        "mode": transmitter.mode.value,
        "description": (
            "Live transmission to CBP ACE"
            if transmitter.mode == TransmissionMode.LIVE
            else "Simulation mode - files not actually transmitted"
        ),
    }


@router.post("/simulate/{entry_id}")
async def simulate_transmission(
    entry_id: UUID,
    db=Depends(get_db),
):
    """
    Force simulation mode transmission for testing.
    
    Useful for testing the transmission flow without
    actual SFTP connection.
    """
    transmitter = ACETransmitter(db, mode=TransmissionMode.SIMULATION)
    result = await transmitter.transmit_entry(entry_id)
    return result.to_dict()
