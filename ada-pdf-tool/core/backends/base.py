from abc import ABC, abstractmethod
from core.models import AuditReport


class LLMBackend(ABC):
    @abstractmethod
    def audit(self, extraction: dict) -> AuditReport:
        raise NotImplementedError
