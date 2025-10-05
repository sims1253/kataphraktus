import { Fragment } from "react";

import { OrderSummary } from "../api/types";
import styles from "./OrderList.module.css";

interface OrderListProps {
  orders: OrderSummary[];
  statusFilter: string;
  onFilterChange: (value: string) => void;
  onCancel: (orderId: number) => void;
  isCancelling: boolean;
}

export const OrderList = ({ orders, statusFilter, onFilterChange, onCancel, isCancelling }: OrderListProps) => {
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Order Ledger</h2>
        <div className={styles.filterRow}>
          <label>
            Show Status
            <select value={statusFilter} onChange={(event) => onFilterChange(event.target.value)}>
              <option value="">All</option>
              <option value="pending">Pending</option>
              <option value="executing">Executing</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </label>
        </div>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Type</th>
              <th>Status</th>
              <th>Army</th>
              <th>Exec</th>
              <th>Details</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 ? (
              <tr>
                <td colSpan={7}>No orders on record.</td>
              </tr>
            ) : (
              orders.map((order) => (
                <Fragment key={order.id}>
                  <tr>
                    <td>#{order.id}</td>
                    <td>{order.order_type}</td>
                    <td>{order.status}</td>
                    <td>{order.army_id ?? "—"}</td>
                    <td>
                      Day {order.execute_day ?? "current"}
                      {order.execute_part ? ` (${order.execute_part})` : ""}
                    </td>
                    <td className={styles.parameters}>
                      <pre>{JSON.stringify(order.parameters, null, 2)}</pre>
                    </td>
                    <td>
                      {order.status === "pending" || order.status === "executing" ? (
                        <button
                          className="action secondary"
                          onClick={() => onCancel(order.id)}
                          disabled={isCancelling}
                        >
                          Cancel
                        </button>
                      ) : null}
                    </td>
                  </tr>
                  {order.result && (
                    <tr className={styles.resultRow}>
                      <td colSpan={7}>
                        <strong>Result:</strong> {JSON.stringify(order.result)}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
};
