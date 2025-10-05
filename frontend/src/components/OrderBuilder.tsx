import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { api } from "../api/client";
import { ORDER_DEFINITIONS, ORDER_TYPES, OrderDefinition } from "../api/orderDefinitions";
import { ArmySummary, OrderCreateRequest } from "../api/types";
import styles from "./OrderBuilder.module.css";

interface CommanderBrief {
  name: string;
  faction_id: number | null;
  current_hex_id: number | null;
}

interface OrderBuilderProps {
  campaignId: number;
  armies: ArmySummary[];
  commanders: Record<string, CommanderBrief>;
  selectedArmyId: number | null;
  onSelectArmy: (armyId: number | null) => void;
  onOrderCreated: () => void;
}

interface MovementLegForm {
  to_hex_id: string;
  distance_miles: string;
  on_road: boolean;
  has_river_ford: boolean;
  is_night: boolean;
  has_fork: boolean;
  alternate_hex_id: string;
}

const defaultLeg = (): MovementLegForm => ({
  to_hex_id: "",
  distance_miles: "",
  on_road: true,
  has_river_ford: false,
  is_night: false,
  has_fork: false,
  alternate_hex_id: ""
});

const DAY_PART_OPTIONS = [
  { value: "", label: "Automatic" },
  { value: "morning", label: "Morning" },
  { value: "midday", label: "Midday" },
  { value: "evening", label: "Evening" },
  { value: "night", label: "Night" }
];

export const OrderBuilder = ({
  campaignId,
  armies,
  commanders,
  selectedArmyId,
  onSelectArmy,
  onOrderCreated
}: OrderBuilderProps) => {
  const [orderType, setOrderType] = useState<string>(ORDER_TYPES[0]);
  const [fieldState, setFieldState] = useState<Record<string, unknown>>({});
  const [legs, setLegs] = useState<MovementLegForm[]>([defaultLeg()]);
  const [commanderId, setCommanderId] = useState<number | null>(null);
  const [executeDay, setExecuteDay] = useState<string>("");
  const [executePart, setExecutePart] = useState<string>("");
  const [priority, setPriority] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  const orderDefinition = useMemo<OrderDefinition>(() => ORDER_DEFINITIONS[orderType], [orderType]);

  const selectedArmy = useMemo(
    () => armies.find((army) => army.id === selectedArmyId) ?? null,
    [armies, selectedArmyId]
  );

  const commanderOptions = useMemo(() => {
    const pairs = Object.entries(commanders).map(([id, value]) => ({
      id: Number(id),
      label: value.name || `Commander ${id}`
    }));
    const armyCommanders = armies
      .map((army) => ({ id: army.commander_id, label: army.commander_name || `Commander ${army.commander_id}` }))
      .filter((candidate, index, arr) => arr.findIndex((row) => row.id === candidate.id) === index);
    const merged = [...pairs, ...armyCommanders];
    return merged.reduce<{ id: number; label: string }[]>((acc, entry) => {
      if (acc.some((existing) => existing.id === entry.id)) {
        return acc;
      }
      acc.push(entry);
      return acc;
    }, []);
  }, [commanders, armies]);

  const resetFields = (definition: OrderDefinition) => {
    const base: Record<string, unknown> = {};
    definition.fields.forEach((field) => {
      if (field.type === "checkbox") {
        base[field.name] = Boolean(field.defaultValue);
      } else if (field.type === "movement_legs") {
        base[field.name] = [];
      } else if (field.type === "number") {
        base[field.name] = field.defaultValue ?? "";
      } else if (field.type === "select") {
        base[field.name] = field.defaultValue ?? (field.options?.[0]?.value ?? "");
      } else {
        base[field.name] = field.defaultValue ?? "";
      }
    });
    setFieldState(base);
    if (definition.fields.some((field) => field.type === "movement_legs")) {
      setLegs([defaultLeg()]);
    }
    setError(null);
  };

  useEffect(() => {
    resetFields(orderDefinition);
  }, [orderDefinition]);

  useEffect(() => {
    if (selectedArmy && (!commanderId || commanderId !== selectedArmy.commander_id)) {
      setCommanderId(selectedArmy.commander_id);
    }
    if (!selectedArmy && commanderOptions.length && !commanderId) {
      setCommanderId(commanderOptions[0].id);
    }
  }, [selectedArmy, commanderOptions, commanderId]);

  const createOrder = useMutation({
    mutationFn: (payload: OrderCreateRequest) => api.createOrder(campaignId, payload),
    onSuccess: () => {
      setPriority(0);
      setExecuteDay("");
      setExecutePart("");
      resetFields(orderDefinition);
      onOrderCreated();
    },
    onError: (mutationError: unknown) => {
      if (mutationError instanceof Error) {
        setError(mutationError.message);
      }
    }
  });

  const updateField = (name: string, value: unknown) => {
    setFieldState((previous) => ({ ...previous, [name]: value }));
  };

  const addLeg = () => {
    setLegs((previous) => [...previous, defaultLeg()]);
  };

  const removeLeg = (index: number) => {
    setLegs((previous) => previous.filter((_, idx) => idx !== index));
  };

  const updateLeg = (index: number, patch: Partial<MovementLegForm>) => {
    setLegs((previous) => previous.map((leg, idx) => (idx === index ? { ...leg, ...patch } : leg)));
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setError(null);

    if (orderDefinition.requiresArmy && !selectedArmyId) {
      setError("Select an army to issue this order.");
      return;
    }
    if (!commanderId) {
      setError("Select a commander to authorise the order.");
      return;
    }

    const parameters: Record<string, unknown> = {};
    for (const field of orderDefinition.fields) {
      const value = fieldState[field.name];
      if (field.type === "movement_legs") {
        const preparedLegs = legs
          .filter((leg) => leg.to_hex_id.trim() && leg.distance_miles.trim())
          .map((leg) => ({
            to_hex_id: Number(leg.to_hex_id),
            distance_miles: Number(leg.distance_miles),
            on_road: leg.on_road,
            has_river_ford: leg.has_river_ford,
            is_night: leg.is_night,
            has_fork: leg.has_fork,
            alternate_hex_id: leg.alternate_hex_id ? Number(leg.alternate_hex_id) : undefined
          }));
        if (orderType === "move" && preparedLegs.length === 0) {
          setError("Provide at least one movement leg.");
          return;
        }
        parameters[field.name] = preparedLegs;
        continue;
      }

      if (field.type === "checkbox") {
        parameters[field.name] = Boolean(value);
        continue;
      }

      if (field.type === "list") {
        const raw = typeof value === "string" ? value : "";
        const entries = raw
          .split(",")
          .map((entry) => entry.trim())
          .filter(Boolean);
        parameters[field.name] = field.listValueType === "number"
          ? entries.map((entry) => Number(entry))
          : entries;
        continue;
      }

      if (field.type === "json") {
        if (!value || value === "") {
          parameters[field.name] = {};
          continue;
        }
        try {
          parameters[field.name] = JSON.parse(String(value));
        } catch (jsonError) {
          setError(`Invalid JSON for ${field.label}`);
          return;
        }
        continue;
      }

      if (field.type === "number") {
        if (value === "" || value === null || value === undefined) {
          continue;
        }
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) {
          setError(`${field.label} must be a number.`);
          return;
        }
        parameters[field.name] = numeric;
        continue;
      }

      if (field.type === "select" || field.type === "text" || field.type === "textarea") {
        if (typeof value === "string" && value.trim() === "" && field.required) {
          setError(`${field.label} is required.`);
          return;
        }
        if (value !== undefined && value !== "") {
          parameters[field.name] = value;
        }
      }
    }

    const executeDayValue = executeDay.trim() ? Number(executeDay) : null;
    if (executeDayValue !== null && Number.isNaN(executeDayValue)) {
      setError("Execution day must be numeric.");
      return;
    }

    const payload: OrderCreateRequest = {
      army_id: orderDefinition.requiresArmy ? selectedArmyId : selectedArmyId ?? null,
      commander_id: commanderId,
      order_type: orderType,
      parameters,
      execute_day: executeDayValue,
      execute_part: executePart || null,
      priority
    };

    createOrder.mutate(payload);
  };

  const commanderLabel = (id: number | null) => {
    if (!id) {
      return "Select";
    }
    const found = commanderOptions.find((option) => option.id === id);
    return found?.label ?? `Commander ${id}`;
  };

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Issue Orders</h2>
        <span className="helper-text">Author directives for your captains.</span>
      </div>
      <form className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.row}>
          <label>
            Order Type
            <select
              value={orderType}
              onChange={(event) => {
                setOrderType(event.target.value);
              }}
            >
              {ORDER_TYPES.map((type) => (
                <option key={type} value={type}>
                  {ORDER_DEFINITIONS[type].label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Acting Army
            <select
              value={selectedArmyId ?? ""}
              onChange={(event) => {
                const next = event.target.value ? Number(event.target.value) : null;
                onSelectArmy(next);
              }}
            >
              <option value="">None</option>
              {armies.map((army) => (
                <option key={army.id} value={army.id}>
                  #{army.id} – {army.commander_name ?? `Commander ${army.commander_id}`}
                </option>
              ))}
            </select>
          </label>
          <label>
            Commander
            <select
              value={commanderId ?? ""}
              onChange={(event) => setCommanderId(event.target.value ? Number(event.target.value) : null)}
            >
              <option value="">Select Commander</option>
              {commanderOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <p className={styles.description}>{orderDefinition.description}</p>

        {orderDefinition.fields.map((field) => {
          const value = fieldState[field.name];
          if (field.type === "movement_legs") {
            return (
              <fieldset key={field.name} className={styles.legs}>
                <legend>March Legs</legend>
                {legs.map((leg, index) => (
                  <div key={index} className={styles.legRow}>
                    <label>
                      To Hex
                      <input
                        type="number"
                        value={leg.to_hex_id}
                        onChange={(event) => updateLeg(index, { to_hex_id: event.target.value })}
                        required
                      />
                    </label>
                    <label>
                      Distance (miles)
                      <input
                        type="number"
                        step="0.1"
                        value={leg.distance_miles}
                        onChange={(event) => updateLeg(index, { distance_miles: event.target.value })}
                        required
                      />
                    </label>
                    <div className={styles.checkGroup}>
                      <label>
                        <input
                          type="checkbox"
                          checked={leg.on_road}
                          onChange={(event) => updateLeg(index, { on_road: event.target.checked })}
                        />
                        On Road
                      </label>
                      <label>
                        <input
                          type="checkbox"
                          checked={leg.has_river_ford}
                          onChange={(event) => updateLeg(index, { has_river_ford: event.target.checked })}
                        />
                        River Ford
                      </label>
                      <label>
                        <input
                          type="checkbox"
                          checked={leg.is_night}
                          onChange={(event) => updateLeg(index, { is_night: event.target.checked })}
                        />
                        Night
                      </label>
                      <label>
                        <input
                          type="checkbox"
                          checked={leg.has_fork}
                          onChange={(event) => updateLeg(index, { has_fork: event.target.checked })}
                        />
                        Fork
                      </label>
                    </div>
                    {leg.has_fork && (
                      <label>
                        Alternate Hex
                        <input
                          type="number"
                          value={leg.alternate_hex_id}
                          onChange={(event) => updateLeg(index, { alternate_hex_id: event.target.value })}
                        />
                      </label>
                    )}
                    <button
                      type="button"
                      className={`${styles.removeLeg} action secondary`}
                      onClick={() => removeLeg(index)}
                      disabled={legs.length === 1}
                    >
                      Remove Leg
                    </button>
                  </div>
                ))}
                <button type="button" className="action" onClick={addLeg}>
                  Add Leg
                </button>
                {field.helper && <p className="helper-text">{field.helper}</p>}
              </fieldset>
            );
          }

          if (field.type === "checkbox") {
            return (
              <label key={field.name} className={styles.checkboxRow}>
                <input
                  type="checkbox"
                  checked={Boolean(value)}
                  onChange={(event) => updateField(field.name, event.target.checked)}
                />
                {field.label}
                {field.helper && <span className="helper-text">{field.helper}</span>}
              </label>
            );
          }

          if (field.type === "select") {
            return (
              <label key={field.name}>
                {field.label}
                <select
                  value={String(value ?? "")}
                  onChange={(event) => updateField(field.name, event.target.value)}
                >
                  {(field.options ?? []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                {field.helper && <span className="helper-text">{field.helper}</span>}
              </label>
            );
          }

          if (field.type === "textarea" || field.type === "json") {
            return (
              <label key={field.name}>
                {field.label}
                <textarea
                  value={String(value ?? "")}
                  onChange={(event) => updateField(field.name, event.target.value)}
                  placeholder={field.placeholder}
                  rows={field.type === "json" ? 4 : 3}
                />
                {field.helper && <span className="helper-text">{field.helper}</span>}
              </label>
            );
          }

          if (field.type === "list") {
            return (
              <label key={field.name}>
                {field.label}
                <input
                  type="text"
                  value={String(value ?? "")}
                  placeholder={field.placeholder}
                  onChange={(event) => updateField(field.name, event.target.value)}
                />
                {field.helper && <span className="helper-text">{field.helper}</span>}
              </label>
            );
          }

          if (field.type === "number") {
            return (
              <label key={field.name}>
                {field.label}
                <input
                  type="number"
                  value={value === undefined ? "" : String(value)}
                  onChange={(event) => updateField(field.name, event.target.value)}
                />
                {field.helper && <span className="helper-text">{field.helper}</span>}
              </label>
            );
          }

          return (
            <label key={field.name}>
              {field.label}
              <input
                type="text"
                value={String(value ?? "")}
                placeholder={field.placeholder}
                onChange={(event) => updateField(field.name, event.target.value)}
              />
              {field.helper && <span className="helper-text">{field.helper}</span>}
            </label>
          );
        })}

        <hr />
        <div className={styles.row}>
          <label>
            Execute Day
            <input
              type="number"
              value={executeDay}
              onChange={(event) => setExecuteDay(event.target.value)}
              placeholder="Current day"
              min={0}
            />
          </label>
          <label>
            Execute Part
            <select value={executePart} onChange={(event) => setExecutePart(event.target.value)}>
              {DAY_PART_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Priority
            <input
              type="number"
              value={priority}
              onChange={(event) => setPriority(Number(event.target.value))}
            />
          </label>
        </div>

        {error && <p className={styles.error}>{error}</p>}

        <div className={styles.actions}>
          <button className="action" type="submit" disabled={createOrder.isPending}>
            {createOrder.isPending ? "Dispatching…" : "Issue Order"}
          </button>
          {orderDefinition.advancedNote && (
            <span className="helper-text">{orderDefinition.advancedNote}</span>
          )}
        </div>
      </form>
    </section>
  );
};
