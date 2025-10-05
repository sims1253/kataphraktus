import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import { ArmySummary } from "../api/types";
import { ArmyList } from "../components/ArmyList";
import { OrderBuilder } from "../components/OrderBuilder";
import { OrderList } from "../components/OrderList";
import { TickControls } from "../components/TickControls";
import styles from "./CampaignDetailPage.module.css";

export const CampaignDetailPage = () => {
  const params = useParams<{ campaignId: string }>();
  const campaignId = Number(params.campaignId);
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [selectedArmyId, setSelectedArmyId] = useState<number | null>(null);

  const detailQuery = useQuery({
    queryKey: ["campaign", campaignId],
    queryFn: () => api.getCampaign(campaignId),
    enabled: Number.isFinite(campaignId)
  });

  const armiesQuery = useQuery({
    queryKey: ["armies", campaignId],
    queryFn: () => api.listArmies(campaignId),
    enabled: detailQuery.isSuccess
  });

  const ordersQuery = useQuery({
    queryKey: ["orders", campaignId, statusFilter],
    queryFn: () => api.listOrders(campaignId, statusFilter || undefined),
    enabled: detailQuery.isSuccess
  });

  const cancelOrder = useMutation({
    mutationFn: (orderId: number) => api.cancelOrder(campaignId, orderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orders", campaignId] });
      detailQuery.refetch();
    }
  });

  const armies: ArmySummary[] = useMemo(() => armiesQuery.data ?? [], [armiesQuery.data]);

  const strongholdIds = useMemo(
    () => (detailQuery.data ? Object.keys(detailQuery.data.strongholds).map(Number) : []),
    [detailQuery.data]
  );

  const handleOrderCreated = () => {
    queryClient.invalidateQueries({ queryKey: ["orders", campaignId] });
    detailQuery.refetch();
    armiesQuery.refetch();
  };

  const commanders = detailQuery.data?.commanders ?? {};

  return (
    <div className={styles.wrapper}>
      {detailQuery.isLoading ? (
        <p>Consulting the royal archive…</p>
      ) : detailQuery.data ? (
        <>
          <section className="panel">
            <div className="section-heading">
              <h2>{detailQuery.data.name}</h2>
              <span className="helper-text">
                Day {detailQuery.data.current_day} · {detailQuery.data.season.toUpperCase()} · {detailQuery.data.status}
              </span>
            </div>
            <div className={styles.summaryGrid}>
              <div>
                <h3>Map</h3>
                <ul>
                  <li>
                    Hexes <strong>{detailQuery.data.map.hex_count}</strong>
                  </li>
                  <li>
                    Roads <strong>{detailQuery.data.map.road_count}</strong>
                  </li>
                  <li>
                    River Crossings <strong>{detailQuery.data.map.river_crossing_count}</strong>
                  </li>
                </ul>
              </div>
              <div>
                <h3>Ledgers</h3>
                <ul>
                  <li>
                    Armies <strong>{detailQuery.data.army_count}</strong>
                  </li>
                  <li>
                    Commanders <strong>{detailQuery.data.commander_count}</strong>
                  </li>
                  <li>
                    Pending Orders <strong>{detailQuery.data.pending_orders}</strong>
                  </li>
                </ul>
              </div>
              <div>
                <h3>Strongholds</h3>
                <p className="helper-text">
                  {strongholdIds.length ? (
                    <>#{strongholdIds.join(", #")}</>
                  ) : (
                    "None recorded"
                  )}
                </p>
              </div>
            </div>
            <footer className={styles.breadcrumbs}>
              <Link to="/">Return to Ledger</Link>
            </footer>
          </section>

          <TickControls
            campaignId={campaignId}
            onAdvanced={() => {
              detailQuery.refetch();
              armiesQuery.refetch();
              ordersQuery.refetch();
            }}
          />

          <ArmyList armies={armies} selectedArmyId={selectedArmyId} onSelect={setSelectedArmyId} />

          <div className={styles.columns}>
            <OrderBuilder
              campaignId={campaignId}
              armies={armies}
              commanders={commanders}
              selectedArmyId={selectedArmyId}
              onSelectArmy={setSelectedArmyId}
              onOrderCreated={handleOrderCreated}
            />

            <OrderList
              orders={ordersQuery.data ?? []}
              statusFilter={statusFilter}
              onFilterChange={setStatusFilter}
              onCancel={(orderId) => cancelOrder.mutate(orderId)}
              isCancelling={cancelOrder.isPending}
            />
          </div>
        </>
      ) : (
        <p>Campaign not found.</p>
      )}
    </div>
  );
};
