import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";
import { TickScheduleUpdate } from "../api/types";
import styles from "./TickControls.module.css";

interface TickControlsProps {
  campaignId: number;
  onAdvanced: () => void;
}

export const TickControls = ({ campaignId, onAdvanced }: TickControlsProps) => {
  const queryClient = useQueryClient();
  const [days, setDays] = useState<string>("1");
  const { data: schedule } = useQuery({
    queryKey: ["tickSchedule", campaignId],
    queryFn: () => api.getTickSchedule(campaignId)
  });

  const advanceTick = useMutation({
    mutationFn: (dayCount: number) => api.advanceTick(campaignId, dayCount),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] });
      onAdvanced();
    }
  });

  const updateSchedule = useMutation({
    mutationFn: (payload: TickScheduleUpdate) => api.updateTickSchedule(campaignId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tickSchedule", campaignId] });
    }
  });

  const handleAdvance = (event: FormEvent) => {
    event.preventDefault();
    const count = Number(days);
    if (!Number.isFinite(count) || count <= 0) {
      return;
    }
    advanceTick.mutate(count);
  };

  const handleScheduleToggle = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const enabled = form.get("enabled") === "on";
    const interval = Number(form.get("interval"));
    const multiplier = Number(form.get("multiplier"));
    const payload: TickScheduleUpdate = { enabled };
    if (Number.isFinite(interval) && interval > 0) {
      payload.interval_seconds = interval;
    }
    if (Number.isFinite(multiplier) && multiplier > 0) {
      payload.debug_multiplier = multiplier;
    }
    updateSchedule.mutate(payload);
  };

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Chronomancer</h2>
        <span className="helper-text">Control the passage of campaign days.</span>
      </div>
      <form className={styles.advanceForm} onSubmit={handleAdvance}>
        <label>
          Days to Advance
          <input type="number" min={1} value={days} onChange={(event) => setDays(event.target.value)} />
        </label>
        <button className="action" type="submit" disabled={advanceTick.isPending}>
          {advanceTick.isPending ? "Casting…" : "Advance"}
        </button>
      </form>

      <hr />
      <form className={styles.scheduleForm} onSubmit={handleScheduleToggle}>
        <label className={styles.toggleRow}>
          <input type="checkbox" name="enabled" defaultChecked={schedule?.enabled ?? false} />
          Enable Auto-Tick
        </label>
        <div className="form-row">
          <label>
            Interval (s)
            <input
              name="interval"
              type="number"
              step="1"
              min={1}
              defaultValue={schedule?.interval_seconds ?? 300}
            />
          </label>
          <label>
            Dev Multiplier
            <input
              name="multiplier"
              type="number"
              step="0.1"
              min={0.1}
              defaultValue={schedule?.debug_multiplier ?? 1}
            />
          </label>
        </div>
        <div className={styles.scheduleFooter}>
          <button className="action secondary" type="submit" disabled={updateSchedule.isPending}>
            {updateSchedule.isPending ? "Updating…" : "Update Schedule"}
          </button>
          {schedule && (
            <p className="helper-text">
              Effective cadence: {schedule.effective_interval_seconds.toFixed(1)}s
            </p>
          )}
        </div>
      </form>
    </section>
  );
};
