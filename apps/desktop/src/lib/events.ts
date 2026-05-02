/**
 * SSE subscription helper for `/api/jobs/{id}/events`.
 *
 * The backend emits one structured event per pipeline phase / log /
 * output / warning / error. We thin-wrap the browser's EventSource
 * with React state so a component just reads the most-recent payload
 * and the rolling history.
 */

import { useEffect, useRef, useState } from "react";

export type EventType =
  | "job_started"
  | "phase"
  | "progress"
  | "log"
  | "output"
  | "warning"
  | "error"
  | "job_finished";

export interface JobEvent {
  type: EventType;
  job_id: string;
  chapter?: string;
  phase?: string;
  message?: string;
  level?: "debug" | "info" | "warn" | "error";
  current?: number;
  total?: number;
  unit?: string;
  path?: string;
  status?: "queued" | "running" | "succeeded" | "failed" | "cancelled";
}

interface UseJobEventsResult {
  events: JobEvent[];
  latest: JobEvent | null;
  closed: boolean;
}

const MAX_HISTORY = 500;

export function useJobEvents(
  jobId: string | null,
  options: { maxHistory?: number } = {},
): UseJobEventsResult {
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [latest, setLatest] = useState<JobEvent | null>(null);
  const [closed, setClosed] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);
  const max = options.maxHistory ?? MAX_HISTORY;

  useEffect(() => {
    if (!jobId) {
      setEvents([]);
      setLatest(null);
      setClosed(false);
      return undefined;
    }

    setEvents([]);
    setLatest(null);
    setClosed(false);

    const source = new EventSource(`/api/jobs/${jobId}/events`);
    sourceRef.current = source;

    source.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data) as JobEvent;
        setLatest(event);
        setEvents((prior) => {
          const next = [...prior, event];
          return next.length > max ? next.slice(-max) : next;
        });
      } catch (err) {
        // Bad JSON shouldn't kill the subscription — log and continue.
        // eslint-disable-next-line no-console
        console.warn("Cannot parse SSE event payload", err);
      }
    };

    source.onerror = () => {
      // The backend closes the stream by reaching end-of-stream; the
      // browser surfaces that as `onerror`. Treat it as "closed".
      setClosed(true);
      source.close();
      sourceRef.current = null;
    };

    return () => {
      source.close();
      sourceRef.current = null;
    };
  }, [jobId, max]);

  return { events, latest, closed };
}
