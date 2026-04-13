import { useEffect, useRef, useState } from "react";

export interface InsightEvent {
  type: "insight";
  call_id: string;
  insight_id: string;
  template_id: string;
  template_name: string;
  confidence: number;
  evidence: string;
  reasoning: string;
  severity: string;
  timestamp: number;
}

export function useInsightStream(callId?: string) {
  const [insights, setInsights] = useState<InsightEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const path = callId ? `/ws/calls/${callId}/live` : "/ws/calls/live";
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}${path}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "insight") {
          setInsights((prev) => [data as InsightEvent, ...prev]);
        }
      } catch {
        // ignore non-JSON messages
      }
    };

    ws.onclose = () => {
      // Reconnect after 3 seconds
      setTimeout(() => {
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
      }, 3000);
    };

    return () => {
      ws.close();
    };
  }, [callId]);

  return insights;
}
