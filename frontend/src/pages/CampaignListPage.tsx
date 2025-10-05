import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { CampaignCreateRequest, CampaignSummary } from "../api/types";
import styles from "./CampaignListPage.module.css";

const DEFAULT_FORM: CampaignCreateRequest = {
  name: "",
  start_date: new Date().toISOString().split("T")[0],
  season: "spring",
  status: "active"
};

export const CampaignListPage = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<CampaignCreateRequest>(DEFAULT_FORM);
  const { data: campaigns, isLoading } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.listCampaigns()
  });

  const createCampaign = useMutation({
    mutationFn: (payload: CampaignCreateRequest) => api.createCampaign(payload),
    onSuccess: (detail) => {
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      setForm(DEFAULT_FORM);
      navigate(`/campaigns/${detail.id}`);
    }
  });

  const sortedCampaigns = useMemo(() => {
    if (!campaigns) {
      return [] as CampaignSummary[];
    }
    return [...campaigns].sort((a, b) => b.id - a.id);
  }, [campaigns]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!form.name.trim()) {
      return;
    }
    createCampaign.mutate(form);
  };

  return (
    <div className={styles.wrapper}>
      <section className="panel">
        <div className="section-heading">
          <h2>Found a New Chronicle</h2>
        </div>
        <form className={styles.form} onSubmit={handleSubmit}>
          <label>
            Campaign Name
            <input
              type="text"
              required
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </label>
          <div className="form-row">
            <label>
              Dawn of the Campaign
              <input
                type="date"
                value={form.start_date}
                onChange={(event) => setForm({ ...form, start_date: event.target.value })}
              />
            </label>
            <label>
              Season
              <select
                value={form.season}
                onChange={(event) => setForm({ ...form, season: event.target.value })}
              >
                <option value="spring">Spring</option>
                <option value="summer">Summer</option>
                <option value="fall">Fall</option>
                <option value="winter">Winter</option>
              </select>
            </label>
            <label>
              Status
              <select
                value={form.status}
                onChange={(event) => setForm({ ...form, status: event.target.value })}
              >
                <option value="active">Active</option>
                <option value="paused">Paused</option>
                <option value="archived">Archived</option>
              </select>
            </label>
          </div>
          <button className="action" type="submit" disabled={createCampaign.isPending}>
            {createCampaign.isPending ? "Inscribing…" : "Create"}
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Campaign Ledger</h2>
          <span className="helper-text">Traverse chronicles to command your forces.</span>
        </div>
        {isLoading ? (
          <p>Consulting the royal scribes…</p>
        ) : sortedCampaigns.length === 0 ? (
          <p>No campaigns recorded yet.</p>
        ) : (
          <div className={styles.list}>
            {sortedCampaigns.map((campaign) => (
              <article key={campaign.id} className={styles.card}>
                <header>
                  <h3>{campaign.name}</h3>
                  <span className="badge">Day {campaign.current_day}</span>
                </header>
                <ul>
                  <li>
                    Season <strong>{campaign.season}</strong>
                  </li>
                  <li>
                    Factions <strong>{campaign.faction_count}</strong>
                  </li>
                  <li>
                    Armies <strong>{campaign.army_count}</strong>
                  </li>
                  <li>
                    Pending Orders <strong>{campaign.pending_orders}</strong>
                  </li>
                </ul>
                <footer>
                  <Link to={`/campaigns/${campaign.id}`} className="action secondary">
                    Enter Theatre
                  </Link>
                </footer>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};
