"""
ACE Transmission Service.

Handles secure file transfer to CBP ACE system via SFTP.
Supports both real SFTP transmission and simulation mode for testing.

Requirements for Production:
- ACE account with CBP
- Digital certificate from CBP
- SFTP credentials (host, user, key)
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID
from enum import Enum
from dataclasses import dataclass, field
import tempfile
from io import StringIO

# Paramiko is optional - only needed for live SFTP transmission
try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    paramiko = None
    PARAMIKO_AVAILABLE = False

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


from app.core.config import settings
from app.models.entry import Entry, EntryStatus, EntryStatusHistory
from app.services.abi_file_exporter import ABIFileExporter

logger = logging.getLogger(__name__)


class TransmissionStatus(str, Enum):
    """Status of ACE transmission."""
    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class TransmissionMode(str, Enum):
    """Transmission mode."""
    LIVE = "live"  # Actual SFTP to CBP
    SIMULATION = "simulation"  # Simulated for testing


@dataclass
class TransmissionResult:
    """Result of ACE file transmission."""
    success: bool
    entry_id: UUID
    entry_number: str
    status: TransmissionStatus
    ace_confirmation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message: str = ""
    error: Optional[str] = None
    mode: TransmissionMode = TransmissionMode.SIMULATION
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "entry_id": str(self.entry_id),
            "entry_number": self.entry_number,
            "status": self.status.value,
            "ace_confirmation_id": self.ace_confirmation_id,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "error": self.error,
            "mode": self.mode.value,
        }


class ACETransmitter:
    """
    Service for transmitting ABI files to CBP ACE system.
    
    Supports two modes:
    1. LIVE: Actual SFTP connection to CBP servers
    2. SIMULATION: Simulated transmission for testing
    """
    
    def __init__(self, db: AsyncSession, mode: TransmissionMode = None):
        self.db = db
        self.abi_exporter = ABIFileExporter(db)
        
        # Determine mode from settings or parameter
        if mode:
            self.mode = mode
        elif settings.ace_sftp_enabled and settings.ace_sftp_host:
            self.mode = TransmissionMode.LIVE
        else:
            self.mode = TransmissionMode.SIMULATION
        
        # SFTP configuration
        self.sftp_host = settings.ace_sftp_host
        self.sftp_port = settings.ace_sftp_port
        self.sftp_user = settings.ace_sftp_user
        self.sftp_key_path = settings.ace_sftp_key_path
        self.upload_path = settings.ace_upload_path
        self.response_path = settings.ace_response_path
    
    async def transmit_entry(self, entry_id: UUID) -> TransmissionResult:
        """
        Transmit a single entry to ACE.
        
        Steps:
        1. Generate ABI file for entry
        2. Upload to ACE SFTP (or simulate)
        3. Wait for/poll for response
        4. Update entry status
        """
        # Get entry
        query = select(Entry).where(Entry.id == entry_id)
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            return TransmissionResult(
                success=False,
                entry_id=entry_id,
                entry_number="",
                status=TransmissionStatus.FAILED,
                error="Entry not found",
                mode=self.mode,
            )
        
        if entry.status not in [EntryStatus.READY_TO_FILE.value, EntryStatus.DRAFT.value]:
            return TransmissionResult(
                success=False,
                entry_id=entry_id,
                entry_number=entry.entry_number or "",
                status=TransmissionStatus.FAILED,
                error=f"Entry status '{entry.status}' is not ready for filing",
                mode=self.mode,
            )
        
        try:
            # Generate ABI content
            abi_result = await self.abi_exporter.export_entry(entry_id)
            if not abi_result.get("success"):
                return TransmissionResult(
                    success=False,
                    entry_id=entry_id,
                    entry_number=entry.entry_number or "",
                    status=TransmissionStatus.FAILED,
                    error=abi_result.get("error", "Failed to generate ABI file"),
                    mode=self.mode,
                )
            
            abi_content = abi_result.get("abi_content", "")
            filename = abi_result.get("filename", f"{entry.entry_number}.abi")
            
            # Transmit based on mode
            if self.mode == TransmissionMode.LIVE:
                transmission_result = await self._transmit_sftp(entry, abi_content, filename)
            else:
                transmission_result = await self._transmit_simulation(entry, abi_content, filename)
            
            # Update entry status
            await self._update_entry_status(entry, transmission_result)
            
            return transmission_result
            
        except Exception as e:
            logger.exception(f"Error transmitting entry {entry_id}: {e}")
            return TransmissionResult(
                success=False,
                entry_id=entry_id,
                entry_number=entry.entry_number or "",
                status=TransmissionStatus.FAILED,
                error=str(e),
                mode=self.mode,
            )
    
    async def _transmit_sftp(
        self, entry: Entry, abi_content: str, filename: str
    ) -> TransmissionResult:
        """Transmit ABI file via SFTP to ACE."""
        logger.info(f"Transmitting entry {entry.entry_number} to ACE via SFTP")
        
        # Check if paramiko is available
        if not PARAMIKO_AVAILABLE:
            return TransmissionResult(
                success=False,
                entry_id=entry.id,
                entry_number=entry.entry_number or "",
                status=TransmissionStatus.FAILED,
                error="SFTP library (paramiko) not installed. Install with: pip install paramiko",
                mode=TransmissionMode.LIVE,
            )
        
        try:
            # Load private key
            if not os.path.exists(self.sftp_key_path):
                return TransmissionResult(
                    success=False,
                    entry_id=entry.id,
                    entry_number=entry.entry_number or "",
                    status=TransmissionStatus.FAILED,
                    error=f"SFTP key not found: {self.sftp_key_path}",
                    mode=TransmissionMode.LIVE,
                )
            
            # Run SFTP in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._sftp_upload_sync,
                abi_content,
                filename,
            )
            
            if result["success"]:
                confirmation_id = f"ACE-{entry.entry_number}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                return TransmissionResult(
                    success=True,
                    entry_id=entry.id,
                    entry_number=entry.entry_number or "",
                    status=TransmissionStatus.UPLOADED,
                    ace_confirmation_id=confirmation_id,
                    message=f"Successfully uploaded to {self.sftp_host}:{self.upload_path}/{filename}",
                    mode=TransmissionMode.LIVE,
                )
            else:
                return TransmissionResult(
                    success=False,
                    entry_id=entry.id,
                    entry_number=entry.entry_number or "",
                    status=TransmissionStatus.FAILED,
                    error=result.get("error", "SFTP upload failed"),
                    mode=TransmissionMode.LIVE,
                )
                
        except Exception as e:
            logger.exception(f"SFTP transmission error: {e}")
            return TransmissionResult(
                success=False,
                entry_id=entry.id,
                entry_number=entry.entry_number or "",
                status=TransmissionStatus.FAILED,
                error=str(e),
                mode=TransmissionMode.LIVE,
            )
    
    def _sftp_upload_sync(self, content: str, filename: str) -> Dict[str, Any]:
        """Synchronous SFTP upload (runs in thread pool)."""
        try:
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Load private key
            private_key = paramiko.RSAKey.from_private_key_file(self.sftp_key_path)
            
            # Connect
            ssh.connect(
                hostname=self.sftp_host,
                port=self.sftp_port,
                username=self.sftp_user,
                pkey=private_key,
                timeout=30,
            )
            
            # Open SFTP session
            sftp = ssh.open_sftp()
            
            # Write file to remote
            remote_path = f"{self.upload_path}/{filename}"
            with sftp.file(remote_path, 'w') as remote_file:
                remote_file.write(content)
            
            # Close connections
            sftp.close()
            ssh.close()
            
            logger.info(f"Successfully uploaded {filename} to {self.sftp_host}")
            return {"success": True}
            
        except paramiko.AuthenticationException as e:
            return {"success": False, "error": f"Authentication failed: {e}"}
        except paramiko.SSHException as e:
            return {"success": False, "error": f"SSH error: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _transmit_simulation(
        self, entry: Entry, abi_content: str, filename: str
    ) -> TransmissionResult:
        """Simulate transmission for testing."""
        logger.info(f"SIMULATION: Transmitting entry {entry.entry_number}")
        
        # Simulate processing delay
        await asyncio.sleep(0.5)
        
        # Generate simulated confirmation
        confirmation_id = f"SIM-{entry.entry_number}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Save simulated file locally for verification
        if settings.debug:
            temp_dir = tempfile.gettempdir()
            sim_path = os.path.join(temp_dir, "ace_simulated", filename)
            os.makedirs(os.path.dirname(sim_path), exist_ok=True)
            with open(sim_path, 'w') as f:
                f.write(abi_content)
            logger.info(f"SIMULATION: Saved ABI to {sim_path}")
        
        return TransmissionResult(
            success=True,
            entry_id=entry.id,
            entry_number=entry.entry_number or "",
            status=TransmissionStatus.UPLOADED,
            ace_confirmation_id=confirmation_id,
            message="SIMULATION: Entry transmitted successfully",
            mode=TransmissionMode.SIMULATION,
        )
    
    async def _update_entry_status(
        self, entry: Entry, result: TransmissionResult
    ) -> None:
        """Update entry status after transmission."""
        previous_status = entry.status
        
        if result.success:
            entry.status = EntryStatus.FILING.value
            entry.ace_status = "submitted"
            entry.filed_at = result.timestamp
            entry.ace_entry_id = result.ace_confirmation_id
        else:
            # Keep current status but record the failure
            entry.ace_response = {
                "transmission_error": result.error,
                "attempted_at": result.timestamp.isoformat(),
            }
        
        # Create history record
        history = EntryStatusHistory(
            entry_id=entry.id,
            from_status=previous_status,
            to_status=entry.status,
            changed_by="ACE Transmitter",
            reason=result.message if result.success else result.error,
            ace_message={
                "transmission_result": result.to_dict(),
            },
        )
        self.db.add(history)
        
        await self.db.commit()
    
    async def transmit_batch(
        self, entry_ids: List[UUID]
    ) -> Dict[str, Any]:
        """
        Transmit multiple entries to ACE.
        
        Returns summary of successes and failures.
        """
        results = []
        successful = 0
        failed = 0
        
        for entry_id in entry_ids:
            result = await self.transmit_entry(entry_id)
            results.append(result.to_dict())
            if result.success:
                successful += 1
            else:
                failed += 1
        
        return {
            "total": len(entry_ids),
            "successful": successful,
            "failed": failed,
            "mode": self.mode.value,
            "results": results,
        }
    
    async def check_response(
        self, entry_id: UUID, timeout_seconds: int = 300
    ) -> TransmissionResult:
        """
        Check for ACE response for a transmitted entry.
        
        In LIVE mode, polls SFTP response directory.
        In SIMULATION mode, automatically returns success after delay.
        """
        query = select(Entry).where(Entry.id == entry_id)
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            return TransmissionResult(
                success=False,
                entry_id=entry_id,
                entry_number="",
                status=TransmissionStatus.FAILED,
                error="Entry not found",
                mode=self.mode,
            )
        
        if self.mode == TransmissionMode.SIMULATION:
            # Simulate immediate acceptance
            await asyncio.sleep(1)
            return TransmissionResult(
                success=True,
                entry_id=entry_id,
                entry_number=entry.entry_number or "",
                status=TransmissionStatus.CONFIRMED,
                ace_confirmation_id=entry.ace_entry_id,
                message="SIMULATION: Entry accepted by CBP",
                mode=TransmissionMode.SIMULATION,
            )
        
        # LIVE mode: Poll for response file
        # This would look for response files in the SFTP response directory
        # matching the entry number
        
        # For now, return pending status
        return TransmissionResult(
            success=True,
            entry_id=entry_id,
            entry_number=entry.entry_number or "",
            status=TransmissionStatus.PENDING,
            ace_confirmation_id=entry.ace_entry_id,
            message="Awaiting CBP response",
            mode=TransmissionMode.LIVE,
        )
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get ACE connection status and configuration."""
        return {
            "mode": self.mode.value,
            "sftp_enabled": settings.ace_sftp_enabled,
            "sftp_host": self.sftp_host or "Not configured",
            "sftp_port": self.sftp_port,
            "sftp_user": self.sftp_user or "Not configured",
            "key_configured": bool(self.sftp_key_path and os.path.exists(self.sftp_key_path)),
            "upload_path": self.upload_path,
            "response_path": self.response_path,
            "ready_for_live": (
                settings.ace_sftp_enabled and
                bool(self.sftp_host) and
                bool(self.sftp_user) and
                bool(self.sftp_key_path) and
                os.path.exists(self.sftp_key_path) if self.sftp_key_path else False
            ),
        }
