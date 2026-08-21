"use client";

import { useEffect, useState } from "react";

const REFRESH_SECONDS = 60;

export default function RefreshControls() {
  const [secondsLeft, setSecondsLeft] = useState(REFRESH_SECONDS);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setSecondsLeft((current) => {
        if (current <= 1) {
          window.location.reload();
          return REFRESH_SECONDS;
        }
        return current - 1;
      });
    }, 1000);

    return () => window.clearInterval(timer);
  }, []);

  function refreshNow() {
    if (refreshing) return;
    setRefreshing(true);
    window.location.reload();
  }

  return (
    <span className="refresh-controls" aria-label="看板刷新控制">
      <span className="refresh-countdown">{refreshing ? "刷新中" : `${secondsLeft}s`}</span>
      <button
        className="refresh-button"
        type="button"
        onClick={refreshNow}
        disabled={refreshing}
        aria-label="立即刷新看板"
        title="立即刷新"
      >
        ↻
      </button>
    </span>
  );
}
