export type OrderFieldType =
  | "text"
  | "number"
  | "textarea"
  | "checkbox"
  | "select"
  | "list"
  | "movement_legs"
  | "json";

export interface OrderFieldDefinition {
  name: string;
  label: string;
  type: OrderFieldType;
  required?: boolean;
  helper?: string;
  options?: { value: string; label: string }[];
  placeholder?: string;
  listValueType?: "string" | "number";
  defaultValue?: string | number | boolean;
}

export interface OrderDefinition {
  label: string;
  requiresArmy: boolean;
  description: string;
  fields: OrderFieldDefinition[];
  advancedNote?: string;
}

export const ORDER_DEFINITIONS: Record<string, OrderDefinition> = {
  move: {
    label: "March",
    requiresArmy: true,
    description: "Plan a series of legs to reposition an army.",
    fields: [
      {
        name: "movement_type",
        label: "Movement Style",
        type: "select",
        options: [
          { value: "standard", label: "Standard" },
          { value: "forced", label: "Forced March" },
          { value: "night", label: "Night March" }
        ],
        defaultValue: "standard",
        helper: "Forced marches strain morale; night marches risk mishaps."
      },
      {
        name: "weather_modifier",
        label: "Weather Modifier",
        type: "number",
        defaultValue: 0,
        helper: "Negative values slow travel; positive values speed it."
      },
      {
        name: "legs",
        label: "Legs",
        type: "movement_legs",
        helper: "Add each hex transition with its distance." 
      }
    ]
  },
  rest: {
    label: "Rest",
    requiresArmy: true,
    description: "Recover morale and readiness by remaining in place.",
    fields: [
      {
        name: "duration_days",
        label: "Days of Rest",
        type: "number",
        defaultValue: 1,
        helper: "Army will remain idle for this many days."
      }
    ]
  },
  forage: {
    label: "Forage",
    requiresArmy: true,
    description: "Gather supplies from neighbouring hexes.",
    fields: [
      {
        name: "hex_ids",
        label: "Hex IDs",
        type: "list",
        listValueType: "number",
        placeholder: "12, 15, 18",
        helper: "Comma-separated hex identifiers for the foraging route."
      }
    ]
  },
  torch: {
    label: "Torch",
    requiresArmy: true,
    description: "Burn and devastate selected hexes.",
    fields: [
      {
        name: "hex_ids",
        label: "Hex IDs",
        type: "list",
        listValueType: "number",
        placeholder: "12, 15, 18"
      }
    ]
  },
  supply_transfer: {
    label: "Transfer Supplies",
    requiresArmy: true,
    description: "Share rations with an allied army.",
    fields: [
      {
        name: "target_army_id",
        label: "Recipient Army ID",
        type: "number",
        required: true
      },
      {
        name: "amount",
        label: "Amount of Supplies",
        type: "number",
        required: true
      }
    ]
  },
  besiege: {
    label: "Lay Siege",
    requiresArmy: true,
    description: "Begin or reinforce a siege on a stronghold.",
    fields: [
      {
        name: "stronghold_id",
        label: "Stronghold ID",
        type: "number",
        required: true
      },
      {
        name: "siege_engines",
        label: "Siege Engines Committed",
        type: "number",
        helper: "Bonus applied to threshold reduction."
      }
    ]
  },
  assault: {
    label: "Assault",
    requiresArmy: true,
    description: "Resolve a full assault on a besieged stronghold.",
    fields: [
      { name: "stronghold_id", label: "Stronghold ID", type: "number", required: true },
      { name: "pillage", label: "Pillage on success", type: "checkbox" },
      {
        name: "attacker_modifier",
        label: "Attacker Modifier",
        type: "number",
        defaultValue: 0
      },
      {
        name: "defender_modifier",
        label: "Defender Modifier",
        type: "number",
        defaultValue: 0
      },
      {
        name: "attacker_fixed_roll",
        label: "Attacker Fixed Roll",
        type: "number",
        helper: "Optional deterministic roll for testing."
      },
      {
        name: "defender_fixed_roll",
        label: "Defender Fixed Roll",
        type: "number"
      }
    ]
  },
  embark: {
    label: "Embark",
    requiresArmy: true,
    description: "Load troops onto a transport fleet.",
    fields: [{ name: "ship_id", label: "Ship ID", type: "number", required: true }]
  },
  disembark: {
    label: "Disembark",
    requiresArmy: true,
    description: "Unload troops from a transport fleet.",
    fields: [{ name: "ship_id", label: "Ship ID", type: "number", required: true }]
  },
  naval_move: {
    label: "Naval Move",
    requiresArmy: false,
    description: "Direct a fleet along a plotted course.",
    fields: [
      { name: "ship_id", label: "Ship ID", type: "number", required: true },
      {
        name: "route",
        label: "Route Hex IDs",
        type: "list",
        listValueType: "number",
        placeholder: "45, 46, 52"
      }
    ]
  },
  send_message: {
    label: "Dispatch Message",
    requiresArmy: false,
    description: "Send a courier between commanders.",
    fields: [
      { name: "recipient_id", label: "Recipient Commander ID", type: "number", required: true },
      { name: "content", label: "Message", type: "textarea", required: true },
      {
        name: "territory_type",
        label: "Territory",
        type: "select",
        options: [
          { value: "friendly", label: "Friendly" },
          { value: "neutral", label: "Neutral" },
          { value: "hostile", label: "Hostile" }
        ],
        defaultValue: "friendly"
      }
    ]
  },
  launch_operation: {
    label: "Launch Operation",
    requiresArmy: false,
    description: "Resolve intelligence, sabotage, or assassination missions.",
    fields: [
      {
        name: "operation_type",
        label: "Operation Type",
        type: "select",
        options: [
          { value: "intelligence", label: "Intelligence" },
          { value: "sabotage", label: "Sabotage" },
          { value: "assassination", label: "Assassination" }
        ],
        defaultValue: "intelligence"
      },
      {
        name: "target_descriptor",
        label: "Target Descriptor (JSON)",
        type: "json",
        helper: "Describe the target in JSON, e.g. {\"stronghold_id\": 12}."
      },
      {
        name: "difficulty_modifier",
        label: "Difficulty Modifier",
        type: "number",
        defaultValue: 0
      },
      {
        name: "loot_cost",
        label: "Loot Cost",
        type: "number",
        helper: "Defaults to rulebook value if omitted."
      },
      {
        name: "territory_type",
        label: "Territory",
        type: "select",
        options: [
          { value: "friendly", label: "Friendly" },
          { value: "neutral", label: "Neutral" },
          { value: "hostile", label: "Hostile" }
        ],
        defaultValue: "friendly"
      },
      {
        name: "complexity",
        label: "Operation Complexity",
        type: "select",
        options: [
          { value: "standard", label: "Standard" },
          { value: "complex", label: "Complex" },
          { value: "audacious", label: "Audacious" }
        ],
        defaultValue: "standard"
      }
    ],
    advancedNote: "Provide operation_id to continue an existing plot."
  },
  raise_army: {
    label: "Raise Army",
    requiresArmy: false,
    description: "Launch or complete a recruitment project from a stronghold.",
    fields: [
      { name: "stronghold_id", label: "Stronghold ID", type: "number", required: true },
      { name: "new_commander_id", label: "Commander ID", type: "number", required: true },
      {
        name: "infantry_unit_type_id",
        label: "Infantry Unit Type ID",
        type: "number",
        required: true
      },
      {
        name: "cavalry_unit_type_id",
        label: "Cavalry Unit Type ID",
        type: "number",
        helper: "Optional."
      },
      {
        name: "rally_hex_id",
        label: "Rally Hex ID",
        type: "number",
        required: true
      },
      { name: "army_name", label: "Army Name", type: "text" }
    ],
    advancedNote: "If _project_id is returned, re-issue the order with that id to finish recruitment."
  },
  harry: {
    label: "Harry",
    requiresArmy: true,
    description: "Conduct raiding actions with selected detachments.",
    fields: [
      {
        name: "detachment_ids",
        label: "Detachment IDs",
        type: "list",
        listValueType: "number",
        placeholder: "11, 12",
        helper: "Detachment identifiers belonging to the acting army."
      },
      {
        name: "target_army_id",
        label: "Target Army ID",
        type: "number",
        required: true
      },
      {
        name: "objective",
        label: "Objective",
        type: "select",
        options: [
          { value: "kill", label: "Kill" },
          { value: "steal", label: "Steal" },
          { value: "burn", label: "Burn" }
        ],
        defaultValue: "kill"
      }
    ]
  }
};

export const ORDER_TYPES = Object.keys(ORDER_DEFINITIONS);
