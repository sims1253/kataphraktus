import { ArmySummary } from "../api/types";
import styles from "./ArmyList.module.css";

interface ArmyListProps {
  armies: ArmySummary[];
  selectedArmyId: number | null;
  onSelect: (armyId: number | null) => void;
}

export const ArmyList = ({ armies, selectedArmyId, onSelect }: ArmyListProps) => {
  if (!armies.length) {
    return (
      <section className="panel">
        <div className="section-heading">
          <h2>Armies</h2>
        </div>
        <p>No armies muster under your banner yet.</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Armies in Theatre</h2>
        <span className="helper-text">Select a host to issue battle plans.</span>
      </div>
      <div className={styles.grid}>
        {armies.map((army) => {
          const isSelected = army.id === selectedArmyId;
          return (
            <article
              key={army.id}
              className={`${styles.card} ${styles[`status-${army.status.replace(" ", "-").toLowerCase()}`] ?? ""} ${
                isSelected ? styles.selected : ""
              }`}
              onClick={() => onSelect(isSelected ? null : army.id ?? null)}
            >
              <header>
                <h3>Army #{army.id}</h3>
                <span className="badge">{army.status.toUpperCase()}</span>
              </header>
              <ul>
                <li>
                  Commander <strong>{army.commander_name ?? `#${army.commander_id}`}</strong>
                </li>
                <li>
                  Supplies <strong>{army.supplies_current} / {army.supplies_capacity}</strong>
                </li>
                <li>
                  Morale <strong>{army.morale_current}</strong>
                </li>
                <li>
                  Location <strong>{army.current_hex_id ?? "Unknown"}</strong>
                </li>
              </ul>
              <footer>
                <span>Orders queued: {army.orders_queue.length}</span>
              </footer>
            </article>
          );
        })}
      </div>
    </section>
  );
};
