"use client";

import { useEffect, useRef, useState } from "react";

const REFRESH_SECONDS = 60;

export default function RefreshControls({ onRefresh }) {
  const [secondsLeft, setSecondsLeft] = useState(REFRESH_SECONDS);
  const [refreshing, setRefreshing] = useState(false);
  const refreshingRef = useRef(false);
  const onRefreshRef = useRef(onRefresh);

  useEffect(() => {
    onRefreshRef.current = onRefresh;
  }, [onRefresh]);

  async function refreshNow() {
    if (refreshingRef.current) return;
    refreshingRef.current = true;
    setRefreshing(true);
    try {
      await onRefreshRef.current?.();
    } finally {
      refreshingRef.current = false;
      setRefreshing(false);
      setSecondsLeft(REFRESH_SECONDS);
    }
  }

  useEffect(() => {
    const timer = window.setInterval(() => {
      setSecondsLeft((current) => {
        if (current <= 1) {
          void refreshNow();
          return current;
        }
        return current - 1;
      });
    }, 1000);

    return () => window.clearInterval(timer);
  }, []);

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
