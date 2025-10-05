# Cataphract Savegame Format

Cataphract campaigns and scenarios are distributed as `.cataphract` archives.
Each archive is a ZIP file with a canonical JSON manifest stored at
`cataphract/manifest.json`.

## Manifest Structure

```jsonc
{
  "format_version": 1,
  "kind": "template" | "save",
  "metadata": {
    "id": "uuid",
    "name": "Scenario Name",
    "description": "Narrative summary",
    "author": "Creator",
    "created_at": "2025-10-05T12:00:00Z",
    "rules_version": "1.1",
    "game_version": "0.2.0"
  },
  "players": [
    { "id": 1, "name": "Scenario Admin", "role": "admin", "faction_id": null }
  ],
  "campaign": { /* cataphract.domain.models.Campaign serialised */ },
  "rules_overrides": null | { /* per-scenario rule tweaks */ }
}
```

The `campaign` object is serialised using the same dataclasses that power the
in-memory domain model. Templates omit orders/messages and typically contain a
single administrator player. Live saves can embed additional players, orders,
and historical events.

## Usage

* `cataphract.savegame.load_manifest(path)` loads and validates an archive.
* `cataphract.savegame.import_campaign_from_manifest(manifest)` returns a
  `Campaign` instance ready to persist via `CampaignService`.
* `cataphract.savegame.export_campaign(campaign)` produces a new manifest that
  can be written to disk with `save_manifest`.

## Scenario Authoring Notes

* Hex coordinates use the axial system (`q`, `r`).
* Strongholds, armies, factions, and commanders mirror the domain dataclasses.
* Templates should include at least one admin player so the UI can unlock the
  campaign immediately after import.
* Additional narrative assets (maps, briefings) can be bundled under
  `cataphract/notes/` inside the archive.

The `campaigns/testudis.cataphract` scenario serves as the reference
implementation and a ready-made testing ground for the new architecture.
