"""Extractor for HTML, MD, JSON, XML, and YAML files."""

import logging
import json
from typing import Dict, Any, List
from io import BytesIO

from app.services.extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class MarkupJsonExtractor(BaseExtractor):
    """Extractor for HTML, Markdown, JSON, XML, and YAML files."""

    SUPPORTED_EXTENSIONS = ["html", "md", "json", "xml", "yml", "yaml"]

    async def extract_text(self, file_bytes: bytes) -> str:
        """Extract text from markup/JSON file."""
        try:
            text = file_bytes.decode("utf-8", errors="replace")

            # Detect format and extract
            if text.strip().startswith("<"):
                # HTML or XML
                return await self._extract_html_text(text)
            elif text.strip().startswith("{") or text.strip().startswith("["):
                # JSON
                return await self._extract_json_text(text)
            elif text.strip().startswith("---") or ":" in text:
                # YAML or Markdown
                return text
            else:
                # Plain markdown or text
                return text
        except Exception as e:
            logger.error(f"Error extracting markup/JSON: {e}")
            return ""

    async def _extract_html_text(self, html_text: str) -> str:
        """Extract text from HTML."""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_text, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)

            return text
        except Exception as e:
            logger.error(f"Error extracting HTML text: {e}")
            return html_text

    async def _extract_json_text(self, json_text: str) -> str:
        """Extract text from JSON."""
        try:
            data = json.loads(json_text)
            return json.dumps(data, indent=2)
        except Exception as e:
            logger.error(f"Error parsing JSON: {e}")
            return json_text

    async def validate_format(self, file_bytes: bytes) -> bool:
        """Validate file format."""
        try:
            text = file_bytes.decode("utf-8", errors="replace")

            if text.strip().startswith("{") or text.strip().startswith("["):
                # JSON validation
                json.loads(text)
                return True
            else:
                # HTML, XML, YAML, Markdown
                return len(text.strip()) > 0
        except Exception:
            return False

    async def extract_tables(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        """Extract tables from markup."""
        try:
            text = file_bytes.decode("utf-8", errors="replace")

            if text.strip().startswith("<"):
                return await self._extract_html_tables(text)
            else:
                return []
        except Exception as e:
            logger.error(f"Error extracting tables: {e}")
            return []

    async def _extract_html_tables(self, html_text: str) -> List[Dict[str, Any]]:
        """Extract HTML tables."""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_text, "html.parser")
            tables = []

            for table_idx, table in enumerate(soup.find_all("table")):
                table_data = {
                    "index": table_idx,
                    "rows": [],
                }

                for row in table.find_all("tr"):
                    row_data = []
                    for cell in row.find_all(["td", "th"]):
                        row_data.append(cell.get_text(strip=True))
                    if row_data:
                        table_data["rows"].append(row_data)

                if table_data["rows"]:
                    tables.append(table_data)

            return tables
        except Exception as e:
            logger.error(f"Error extracting HTML tables: {e}")
            return []

    async def extract_metadata(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Extract metadata from markup/JSON."""
        try:
            text = file_bytes.decode("utf-8", errors="replace")

            metadata = {
                "filename": filename,
                "file_size": len(file_bytes),
                "char_count": len(text),
                "line_count": len(text.splitlines()),
            }

            # Extract from HTML metadata
            if text.strip().startswith("<"):
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(text, "html.parser")

                # Title
                title_tag = soup.find("title")
                if title_tag:
                    metadata["title"] = title_tag.get_text()

                # Meta description
                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc:
                    metadata["description"] = meta_desc.get("content")

                # Meta keywords
                meta_keywords = soup.find("meta", attrs={"name": "keywords"})
                if meta_keywords:
                    metadata["keywords"] = meta_keywords.get("content")

            # Extract from JSON
            elif text.strip().startswith("{"):
                data = json.loads(text)
                if isinstance(data, dict):
                    metadata["json_keys"] = list(data.keys())

            return metadata
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return {
                "filename": filename,
                "file_size": len(file_bytes),
            }


class XmlExtractor(MarkupJsonExtractor):
    """Extractor for XML files."""

    SUPPORTED_EXTENSIONS = ["xml"]

    async def extract_metadata(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Extract metadata from XML."""
        try:
            import xml.etree.ElementTree as ET

            text = file_bytes.decode("utf-8", errors="replace")
            root = ET.fromstring(text)

            return {
                "filename": filename,
                "file_size": len(file_bytes),
                "root_tag": root.tag,
                "root_attribs": root.attrib,
                "child_count": len(root),
            }
        except Exception as e:
            logger.error(f"Error extracting XML metadata: {e}")
            return {
                "filename": filename,
                "file_size": len(file_bytes),
            }


class YamlExtractor(MarkupJsonExtractor):
    """Extractor for YAML files."""

    SUPPORTED_EXTENSIONS = ["yml", "yaml"]

    async def extract_metadata(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Extract metadata from YAML."""
        try:
            import yaml

            text = file_bytes.decode("utf-8", errors="replace")
            data = yaml.safe_load(text)

            metadata = {
                "filename": filename,
                "file_size": len(file_bytes),
            }

            if isinstance(data, dict):
                metadata["yaml_keys"] = list(data.keys())

            return metadata
        except Exception as e:
            logger.error(f"Error extracting YAML metadata: {e}")
            return {
                "filename": filename,
                "file_size": len(file_bytes),
            }
