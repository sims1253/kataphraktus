import { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

import { useServerHealth } from "../hooks/useServerHealth";
import styles from "./AppLayout.module.css";

interface AppLayoutProps {
  children: ReactNode;
}

export const AppLayout = ({ children }: AppLayoutProps) => {
  const location = useLocation();
  const { data: health } = useServerHealth();

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <h1 className={styles.brand}>Cataphract Commandery</h1>
        <nav>
          <Link to="/" className={location.pathname === "/" ? styles.active : undefined}>
            Campaign Ledger
          </Link>
        </nav>
        <section className={styles.health}>
          <h2>Chronicler</h2>
          {health ? (
            <ul>
              <li>
                <span>Status</span>
                <strong>{health.status}</strong>
              </li>
              <li>
                <span>Ruleset</span>
                <strong>{health.rules_version}</strong>
              </li>
              <li>
                <span>Tick Interval</span>
                <strong>{health.tick_interval_seconds}s</strong>
              </li>
            </ul>
          ) : (
            <p>Consulting augurs…</p>
          )}
        </section>
      </aside>
      <main className={styles.content}>{children}</main>
    </div>
  );
};
