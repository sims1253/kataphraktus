export interface HealthPayload {
  status: string;
  rules_version: string;
  tick_interval_seconds: number;
  debug_tick_multiplier?: number;
}

export interface CampaignSummary {
  id: number;
  name: string;
  start_date: string;
  current_day: number;
  current_part: string;
  season: string;
  status: string;
  faction_count: number;
  commander_count: number;
  army_count: number;
  pending_orders: number;
}

export interface CampaignDetail extends CampaignSummary {
  map: {
    hex_count: number;
    road_count: number;
    river_crossing_count: number;
  };
  armies: Record<string, ArmySummary>;
  strongholds: Record<
    string,
    {
      type: string;
      hex_id: number;
      controlling_faction_id: number | null;
      current_threshold: number;
    }
  >;
  orders: Record<string, OrderSummary>;
}

export interface ArmySummary {
  id?: number;
  commander_id: number;
  commander_name: string | null;
  status: string;
  current_hex_id: number | null;
  supplies_current: number;
  supplies_capacity: number;
  morale_current: number;
  movement_points_remaining: number;
  orders_queue: number[];
  faction_id: number | null;
}

export interface OrderSummary {
  id: number;
  army_id: number | null;
  commander_id: number;
  order_type: string;
  status: string;
  priority: number;
  issued_at: string;
  execute_at: string;
  execute_day: number | null;
  execute_part: string | null;
  parameters: Record<string, unknown>;
  result: Record<string, unknown> | null;
}

export interface TickStatusResponse {
  enabled: boolean;
  interval_seconds: number;
  debug_multiplier: number;
  effective_interval_seconds: number;
}

export interface TickScheduleUpdate {
  enabled: boolean;
  interval_seconds?: number;
  debug_multiplier?: number;
}

export interface OrderCreateRequest {
  army_id: number | null;
  commander_id: number;
  order_type: string;
  parameters: Record<string, unknown>;
  execute_day: number | null;
  execute_part: string | null;
  priority: number;
}

export interface CampaignCreateRequest {
  name: string;
  start_date: string;
  season: string;
  status: string;
}
