from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class ElementType(Enum):
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"
    LINK = "link"


class Classification(Enum):
    AUTO_FIX = "auto-fix"
    HUMAN_REVIEW = "human-review"
    PRESERVE = "preserve"
    INFO = "info"


class Confidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class PageElement:
    id: str
    type: ElementType
    text: Optional[str] = None
    font_size: Optional[float] = None
    font_bold: Optional[bool] = None
    bbox: Optional[list] = None
    current_tag: Optional[str] = None
    has_alt_text: Optional[bool] = None
    rows: Optional[int] = None
    cols: Optional[int] = None
    has_header_row: Optional[str] = None


@dataclass
class DocumentMetadata:
    title: Optional[str]
    language: Optional[str]
    page_count: int


@dataclass
class ExtractionOutput:
    file_type: str
    metadata: DocumentMetadata
    pages: list


@dataclass
class Finding:
    element_id: str
    page: int
    wcag_criterion: str
    severity: str
    classification: str
    confidence: Optional[str]
    current_state: str
    proposed_fix: Optional[str]
    reasoning: str
    verification_path: Optional[str]
    element_subtype: Optional[str] = None
    human_prompt: Optional[str] = None


@dataclass
class FixProposal:
    element_id: str
    page: int
    description: str
    confidence: str
    user_approved: bool = False
    user_value: Optional[str] = None


@dataclass
class AuditReport:
    findings: List[Finding]
    preserve: List[str]
    metadata_fixes: list
    auto_fix: List[Finding] = field(default_factory=list)
    human_review: List[Finding] = field(default_factory=list)
    preserve_findings: List[Finding] = field(default_factory=list)
    info: List[Finding] = field(default_factory=list)
