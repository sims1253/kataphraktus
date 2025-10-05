"""JSON-based repository for Cataphract campaigns."""

from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter

from cataphract.domain import models as dm


class JsonCampaignRepository:
    """Persist campaigns as JSON snapshots on disk."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._adapter: TypeAdapter[dm.Campaign] = TypeAdapter(dm.Campaign)

    def _path_for(self, campaign_id: dm.CampaignID) -> Path:
        return self.base_path / f"campaign_{int(campaign_id)}.json"

    def save(self, campaign: dm.Campaign) -> Path:
        """Serialize a campaign to disk and return the snapshot path."""

        path = self._path_for(campaign.id)
        payload = self._adapter.dump_json(campaign, indent=2)
        path.write_bytes(payload)
        return path

    def load(self, campaign_id: dm.CampaignID) -> dm.Campaign:
        """Load a previously saved campaign snapshot."""

        path = self._path_for(campaign_id)
        data = path.read_bytes()
        return self._adapter.validate_json(data)

    def list_campaigns(self) -> list[dm.CampaignID]:
        """Return all campaign ids currently persisted in the repository."""

        ids: list[dm.CampaignID] = []
        prefix = "campaign_"
        suffix = ".json"
        for path in self.base_path.glob("campaign_*.json"):
            stem = path.name
            if stem.startswith(prefix) and stem.endswith(suffix):
                raw = stem[len(prefix) : -len(suffix)]
                try:
                    ids.append(dm.CampaignID(int(raw)))
                except ValueError:  # pragma: no cover - ignored malformed file
                    continue
        return sorted(ids, key=int)

    def delete(self, campaign_id: dm.CampaignID) -> None:
        """Remove a campaign snapshot if it exists."""

        path = self._path_for(campaign_id)
        if path.exists():
            path.unlink()
