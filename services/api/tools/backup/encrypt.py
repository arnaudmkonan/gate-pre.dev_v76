"""Backup encryption utility using GPG."""
import os
import logging
import subprocess
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class BackupEncryption:
    """Handles backup encryption/decryption."""

    def __init__(self, gpg_home: str = "~/.gnupg", passphrase: str = None):
        """Initialize encryption handler."""
        self.gpg_home = Path(gpg_home).expanduser()
        self.passphrase = passphrase

    def encrypt_file(self, input_file: str, output_file: str = None) -> str:
        """Encrypt a file using GPG."""
        input_path = Path(input_file)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        if output_file is None:
            output_file = f"{input_file}.gpg"

        logger.info(f"Encrypting file: {input_file}")

        try:
            cmd = [
                "gpg",
                f"--homedir={self.gpg_home}",
                "--symmetric",
                "--cipher-algo=AES256",
                f"--output={output_file}",
                "--batch",
                "--quiet"
            ]

            if self.passphrase:
                cmd.extend(["--passphrase", self.passphrase])

            cmd.append(input_file)

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"Encryption failed: {result.stderr}")

            output_size = Path(output_file).stat().st_size
            logger.info(f"File encrypted successfully: {output_file} ({output_size} bytes)")

            return output_file

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt_file(self, input_file: str, output_file: str = None) -> str:
        """Decrypt a GPG encrypted file."""
        input_path = Path(input_file)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        if output_file is None:
            # Remove .gpg extension if present
            output_file = str(input_path).replace(".gpg", "")

        logger.info(f"Decrypting file: {input_file}")

        try:
            cmd = [
                "gpg",
                f"--homedir={self.gpg_home}",
                f"--output={output_file}",
                "--batch",
                "--quiet"
            ]

            if self.passphrase:
                cmd.extend(["--passphrase", self.passphrase])

            cmd.append(input_file)

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"Decryption failed: {result.stderr}")

            output_size = Path(output_file).stat().st_size
            logger.info(f"File decrypted successfully: {output_file} ({output_size} bytes)")

            return output_file

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise

    def batch_encrypt(self, directory: str, pattern: str = "*.sql.gz") -> dict:
        """Encrypt all matching files in a directory."""
        dir_path = Path(directory)

        if not dir_path.exists():
            raise ValueError(f"Directory not found: {directory}")

        logger.info(f"Encrypting files matching {pattern} in {directory}")

        results = {"encrypted": [], "failed": []}

        for file_path in dir_path.glob(pattern):
            try:
                output_file = f"{file_path}.gpg"
                self.encrypt_file(str(file_path), output_file)
                results["encrypted"].append(str(file_path))
            except Exception as e:
                logger.error(f"Failed to encrypt {file_path}: {e}")
                results["failed"].append({"file": str(file_path), "error": str(e)})

        logger.info(
            f"Batch encryption completed: {len(results['encrypted'])} "
            f"encrypted, {len(results['failed'])} failed"
        )

        return results

    def batch_decrypt(self, directory: str, pattern: str = "*.gpg") -> dict:
        """Decrypt all matching files in a directory."""
        dir_path = Path(directory)

        if not dir_path.exists():
            raise ValueError(f"Directory not found: {directory}")

        logger.info(f"Decrypting files matching {pattern} in {directory}")

        results = {"decrypted": [], "failed": []}

        for file_path in dir_path.glob(pattern):
            try:
                output_file = str(file_path).replace(".gpg", "")
                self.decrypt_file(str(file_path), output_file)
                results["decrypted"].append(str(file_path))
            except Exception as e:
                logger.error(f"Failed to decrypt {file_path}: {e}")
                results["failed"].append({"file": str(file_path), "error": str(e)})

        logger.info(
            f"Batch decryption completed: {len(results['decrypted'])} "
            f"decrypted, {len(results['failed'])} failed"
        )

        return results

    def verify_encryption(self, encrypted_file: str) -> bool:
        """Verify that a file is properly encrypted."""
        file_path = Path(encrypted_file)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {encrypted_file}")

        try:
            # Check file signature
            cmd = [
                "gpg",
                f"--homedir={self.gpg_home}",
                "--list-only",
                "--quiet",
                encrypted_file
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False

    def shred_file(self, file_path: str, passes: int = 3) -> None:
        """Securely delete a file."""
        file_obj = Path(file_path)

        if not file_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Securely deleting file: {file_path} ({passes} passes)")

        try:
            # Use shred on Unix-like systems
            cmd = ["shred", f"--force", f"--verbose", f"--iterations={passes}", file_path]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.warning(f"shred command failed, falling back to unlink")
                file_obj.unlink()
            else:
                logger.info(f"File securely deleted")

        except FileNotFoundError:
            # Fallback to standard file deletion
            logger.warning("shred not available, using standard deletion")
            file_obj.unlink()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    passphrase = os.getenv("ENCRYPTION_PASSPHRASE")

    if not passphrase:
        logger.error("ENCRYPTION_PASSPHRASE environment variable required")
        exit(1)

    encryption = BackupEncryption(passphrase=passphrase)

    # Example usage
    import sys

    if len(sys.argv) < 2:
        print("Usage: encrypt.py <encrypt|decrypt|batch-encrypt|batch-decrypt> <file-or-dir>")
        exit(1)

    command = sys.argv[1]
    target = sys.argv[2] if len(sys.argv) > 2 else None

    if command == "encrypt" and target:
        try:
            output = encryption.encrypt_file(target)
            print(f"Encrypted: {output}")
        except Exception as e:
            print(f"Error: {e}")
            exit(1)
    elif command == "decrypt" and target:
        try:
            output = encryption.decrypt_file(target)
            print(f"Decrypted: {output}")
        except Exception as e:
            print(f"Error: {e}")
            exit(1)
    elif command == "batch-encrypt" and target:
        results = encryption.batch_encrypt(target)
        print(f"Results: {results}")
    elif command == "batch-decrypt" and target:
        results = encryption.batch_decrypt(target)
        print(f"Results: {results}")
    else:
        print("Invalid command or missing target")
        exit(1)
