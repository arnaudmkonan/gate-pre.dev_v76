from app.parsers.registry import ParserRegistry
from app.parsers.txt_parser import TxtParser
from app.parsers.md_parser import MdParser
from app.parsers.pdf_parser import PdfParser

# Register parsers
_txt_parser = TxtParser()
_md_parser = MdParser()
_pdf_parser = PdfParser()

ParserRegistry.register("txt", _txt_parser)
ParserRegistry.register("md", _md_parser)
ParserRegistry.register("markdown", _md_parser)
ParserRegistry.register("pdf", _pdf_parser)

__all__ = [
    "ParserRegistry",
    "TxtParser",
    "MdParser",
    "PdfParser",
]
