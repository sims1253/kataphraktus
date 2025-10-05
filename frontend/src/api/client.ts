import {
  ArmySummary,
  CampaignCreateRequest,
  CampaignDetail,
  CampaignSummary,
  HealthPayload,
  OrderCreateRequest,
  OrderSummary,
  TickScheduleUpdate,
  TickStatusResponse
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {})
    },
    ...options
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const api = {
  getHealth: (): Promise<HealthPayload> => request("/health"),
  listCampaigns: (): Promise<CampaignSummary[]> => request("/campaigns"),
  createCampaign: (payload: CampaignCreateRequest): Promise<CampaignDetail> =>
    request("/campaigns", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getCampaign: (campaignId: number): Promise<CampaignDetail> =>
    request(`/campaigns/${campaignId}`),
  listArmies: (campaignId: number): Promise<ArmySummary[]> =>
    request(`/campaigns/${campaignId}/armies`),
  listOrders: (campaignId: number, status?: string): Promise<OrderSummary[]> => {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    return request(`/campaigns/${campaignId}/orders${query}`);
  },
  createOrder: (campaignId: number, payload: OrderCreateRequest): Promise<OrderSummary> =>
    request(`/campaigns/${campaignId}/orders`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  cancelOrder: (campaignId: number, orderId: number): Promise<OrderSummary> =>
    request(`/campaigns/${campaignId}/orders/${orderId}/cancel`, {
      method: "POST"
    }),
  advanceTick: (campaignId: number, days: number): Promise<CampaignSummary> =>
    request(`/campaigns/${campaignId}/tick/advance`, {
      method: "POST",
      body: JSON.stringify({ days })
    }),
  getTickSchedule: (campaignId: number): Promise<TickStatusResponse> =>
    request(`/campaigns/${campaignId}/tick/schedule`),
  updateTickSchedule: (
    campaignId: number,
    payload: TickScheduleUpdate
  ): Promise<TickStatusResponse> =>
    request(`/campaigns/${campaignId}/tick/schedule`, {
      method: "POST",
      body: JSON.stringify(payload)
    })
};
