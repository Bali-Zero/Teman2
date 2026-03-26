"""Metabolic cost tracker — every action costs energy.
Enforces daily budget with partitions. Reserve partition is NEVER accessible by CELL."""
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class CostEntry:
    provider: str
    amount: float
    partition: str
    timestamp: datetime

class MetabolismTracker:
    def __init__(self, daily_limit: float = 10.0, partitions: dict[str, float] | None = None, safety_threshold: float = 0.9) -> None:
        self._daily_limit = daily_limit
        self._partitions = partitions or {}
        self._safety_threshold = safety_threshold
        self._entries: list[CostEntry] = []
        self._partition_spend: dict[str, float] = {k: 0.0 for k in self._partitions}

    @property
    def daily_spend(self) -> float:
        return sum(e.amount for e in self._entries)

    @property
    def remaining_budget(self) -> float:
        return self._daily_limit - self.daily_spend

    def record(self, provider: str, amount: float, partition: str = "routine") -> None:
        self._entries.append(CostEntry(provider=provider, amount=amount, partition=partition, timestamp=datetime.now(timezone.utc)))
        if partition in self._partition_spend:
            self._partition_spend[partition] += amount

    def can_afford(self, amount: float, partition: str = "routine") -> bool:
        if partition == "reserve":
            return False
        threshold = self._daily_limit * self._safety_threshold
        if (self.daily_spend + amount) > threshold:
            return False
        if partition in self._partitions:
            partition_limit = self._partitions[partition]
            partition_spent = self._partition_spend.get(partition, 0.0)
            if (partition_spent + amount) > partition_limit:
                return False
        return True

    def daily_reset(self) -> None:
        self._entries.clear()
        self._partition_spend = {k: 0.0 for k in self._partitions}
