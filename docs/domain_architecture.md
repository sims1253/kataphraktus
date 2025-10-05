# Domain Architecture

The legacy ORM/service stack has been removed. Everything now lives in the
domain-first layer under `src/cataphract/domain`, which provides:

* Dataclasses describing the full ruleset (`domain.models`).
* Enumerations and rule configuration (`domain.enums`, `domain.rules_config`).
* Pure rule implementations (supply, movement, morale, battle, siege, and order execution).

## Completed

1. **Domain Model Skeleton**: Dataclasses covering the full ruleset live in
   `domain.models`, alongside enums and rule configuration.
2. **Supply, Movement, Morale, Battle & Siege**: Core logistics and conflict
   rules run entirely on the domain dataclasses. Examples live in
   `tests/unit/test_domain_supply.py`, `tests/unit/test_domain_movement.py`,
   `tests/unit/test_domain_morale.py`, `tests/unit/test_domain_battle.py`, and
   `tests/unit/test_domain_siege.py`.
3. **Orders & Daily Tick Pipeline**: `domain.orders` provides order execution
   (move, rest, forage, torch, besiege, assault) and `domain.tick` orchestrates
   day-part processing with supply consumption and siege advancement. See
   `tests/unit/test_domain_orders.py` and `tests/unit/test_domain_tick.py`.
4. **Messaging, Mercenaries, Naval & Operations**: The new modules
   (`domain.messaging`, `domain.mercenaries`, `domain.naval`, `domain.operations`)
   implement courier delivery, contract upkeep, embarkation/movement and
   espionage resolution on the in-memory models.
5. **Savegame Format**: Scenario and save import/export is handled via
   `savegame`, which persists entire campaigns as `.cataphract` archives. See
   `docs/savegame_format.md` for details.

## Next Steps

1. **Persistence Adapter**
   - Use `repository.JsonCampaignRepository` or extend with alternate storage
     backends (sqlite, cloud, etc.).

2. **Subsystem Ports**
   - Expand naval conflict (blockades, interception) and riverine logistics
   - Mercenary recruitment workflows and detachment tagging
   - Deeper espionage outcomes and cascading narrative events
   - Build out the savegame tooling with delta exports and richer metadata

3. **Interface Layer**
   - Once the rules are complete, expose them through a lightweight API or CLI
     without reintroducing heavyweight service layers.

4. **Documentation**
   - Keep the rule summaries and module responsibilities updated as new
     subsystems land.

## Guiding Principles

* **Single Source of Truth** – All rules live in `domain`. Storage is a thin
  adapter.
* **Pure Functions First** – Each subsystem should expose deterministic
  operations with explicit randomness inputs.
* **Small Surface Area** – Only keep modules actively used by the rules; avoid
  recreating the previous service sprawl.
