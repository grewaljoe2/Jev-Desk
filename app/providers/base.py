from abc import ABC, abstractmethod
from app.core.models import TokenSnapshot

class DiscoveryProvider(ABC):
    @abstractmethod
    async def discover(self) -> list[TokenSnapshot]:
        raise NotImplementedError
