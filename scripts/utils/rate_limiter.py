"""
Rate Limiter for Multi-Tool Caching Pipeline

Tracks daily quotas for Claude Max, Gemini AI Studio, ChatGPT Plus, and NotebookLM
to ensure we stay within subscription limits.

Author: Nuzantara Team
Date: 2026-02-09
Reference: docs/caching/WORKFLOW_GUIDE.md
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict


@dataclass
class ServiceQuota:
    """Quota limits for a service."""
    name: str
    daily_limit: int
    current_usage: int
    reset_at: str  # ISO 8601 timestamp


class RateLimiter:
    """
    Track API usage across multiple services.

    Quotas (per subscription):
    - Claude Max: 100 messages/3 hours (conservative: 600/day)
    - Gemini AI Studio: 1,500 requests/day (Free tier)
    - ChatGPT Plus: ~40 messages/3 hours (conservative: 200/day)
    - NotebookLM: Unlimited podcast generation
    """

    DEFAULT_QUOTAS = {
        "claude_max": 600,  # Conservative estimate
        "gemini_ai_studio": 1500,  # Free tier
        "chatgpt_plus": 200,  # Conservative estimate
        "notebooklm": 999999  # Effectively unlimited
    }

    def __init__(self, state_file: str = "data/rate_limiter_state.json"):
        """
        Initialize rate limiter.

        Args:
            state_file: Path to state persistence file
        """
        self.state_file = Path(state_file)
        self.quotas: Dict[str, ServiceQuota] = {}
        self._load_state()

    def _load_state(self):
        """Load state from disk or initialize defaults."""
        if self.state_file.exists():
            with open(self.state_file, "r") as f:
                data = json.load(f)

            for service_name, service_data in data.items():
                self.quotas[service_name] = ServiceQuota(**service_data)

            # Check if any quotas need reset
            now = datetime.now()
            for service_name, quota in self.quotas.items():
                reset_time = datetime.fromisoformat(quota.reset_at)
                if now >= reset_time:
                    # Reset quota
                    self.quotas[service_name] = ServiceQuota(
                        name=service_name,
                        daily_limit=self.DEFAULT_QUOTAS[service_name],
                        current_usage=0,
                        reset_at=(now + timedelta(days=1)).isoformat()
                    )
        else:
            # Initialize defaults
            now = datetime.now()
            for service_name, limit in self.DEFAULT_QUOTAS.items():
                self.quotas[service_name] = ServiceQuota(
                    name=service_name,
                    daily_limit=limit,
                    current_usage=0,
                    reset_at=(now + timedelta(days=1)).isoformat()
                )

        self._save_state()

    def _save_state(self):
        """Persist state to disk."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            service_name: {
                "name": quota.name,
                "daily_limit": quota.daily_limit,
                "current_usage": quota.current_usage,
                "reset_at": quota.reset_at
            }
            for service_name, quota in self.quotas.items()
        }

        with open(self.state_file, "w") as f:
            json.dump(data, f, indent=2)

    def check_quota(self, service: str, amount: int = 1) -> bool:
        """
        Check if service has quota available.

        Args:
            service: Service name (claude_max, gemini_ai_studio, etc.)
            amount: Number of requests to check

        Returns:
            True if quota available, False otherwise
        """
        if service not in self.quotas:
            raise ValueError(f"Unknown service: {service}")

        quota = self.quotas[service]
        return (quota.current_usage + amount) <= quota.daily_limit

    def consume_quota(self, service: str, amount: int = 1):
        """
        Consume quota for a service.

        Args:
            service: Service name
            amount: Number of requests consumed

        Raises:
            ValueError: If quota exceeded
        """
        if not self.check_quota(service, amount):
            quota = self.quotas[service]
            raise ValueError(
                f"Quota exceeded for {service}. "
                f"Used: {quota.current_usage}/{quota.daily_limit}. "
                f"Resets at: {quota.reset_at}"
            )

        self.quotas[service].current_usage += amount
        self._save_state()

    def get_remaining(self, service: str) -> int:
        """
        Get remaining quota for service.

        Args:
            service: Service name

        Returns:
            Remaining requests available
        """
        quota = self.quotas[service]
        return max(0, quota.daily_limit - quota.current_usage)

    def get_status(self) -> Dict[str, Dict]:
        """
        Get status for all services.

        Returns:
            Dict mapping service name to status dict
        """
        status = {}
        for service_name, quota in self.quotas.items():
            remaining = self.get_remaining(service_name)
            pct_used = (quota.current_usage / quota.daily_limit * 100) if quota.daily_limit > 0 else 0

            status[service_name] = {
                "daily_limit": quota.daily_limit,
                "current_usage": quota.current_usage,
                "remaining": remaining,
                "percent_used": pct_used,
                "reset_at": quota.reset_at
            }

        return status

    def reset_service(self, service: str):
        """
        Manually reset quota for a service.

        Args:
            service: Service name to reset
        """
        if service not in self.quotas:
            raise ValueError(f"Unknown service: {service}")

        now = datetime.now()
        self.quotas[service] = ServiceQuota(
            name=service,
            daily_limit=self.DEFAULT_QUOTAS[service],
            current_usage=0,
            reset_at=(now + timedelta(days=1)).isoformat()
        )
        self._save_state()

    def reset_all(self):
        """Reset all quotas."""
        for service in self.quotas.keys():
            self.reset_service(service)


# CLI for testing
if __name__ == "__main__":
    import click

    @click.group()
    def cli():
        """Rate limiter CLI for testing."""
        pass

    @cli.command()
    def status():
        """Show current quota status."""
        limiter = RateLimiter()
        status = limiter.get_status()

        click.echo("\n" + "="*70)
        click.echo("📊 RATE LIMITER STATUS")
        click.echo("="*70)

        for service, data in status.items():
            click.echo(f"\n🔹 {service.upper().replace('_', ' ')}:")
            click.echo(f"   Used: {data['current_usage']:,}/{data['daily_limit']:,} ({data['percent_used']:.1f}%)")
            click.echo(f"   Remaining: {data['remaining']:,}")
            click.echo(f"   Resets: {data['reset_at']}")

        click.echo("\n" + "="*70)

    @cli.command()
    @click.argument("service")
    @click.argument("amount", type=int)
    def consume(service: str, amount: int):
        """Consume quota for a service."""
        limiter = RateLimiter()

        try:
            limiter.consume_quota(service, amount)
            remaining = limiter.get_remaining(service)
            click.echo(f"✅ Consumed {amount} from {service}. Remaining: {remaining}")
        except ValueError as e:
            click.echo(f"❌ {e}")

    @cli.command()
    @click.argument("service")
    def reset(service: str):
        """Reset quota for a service."""
        limiter = RateLimiter()
        limiter.reset_service(service)
        click.echo(f"✅ Reset quota for {service}")

    @cli.command()
    def reset_all():
        """Reset all quotas."""
        limiter = RateLimiter()
        limiter.reset_all()
        click.echo("✅ Reset all quotas")

    cli()
