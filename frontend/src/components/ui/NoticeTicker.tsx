"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";

const SPEED = 45; // pixels per second

/**
 * The notice list. If every notice fits, it stays still. If they do not fit, it slides across
 * on its own (pauses on hover / focus / the pause button) so nothing is cut off and hidden.
 * Without JavaScript, or with "reduce motion" on, it is a plain list that can be swiped or scrolled.
 */
export function NoticeTicker({ items }: { items: string[] }) {
  const box = useRef<HTMLDivElement>(null);
  const one = useRef<HTMLUListElement>(null);
  const [moving, setMoving] = useState(false);
  const [seconds, setSeconds] = useState(30);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const measure = () => {
      const outer = box.current;
      const list = one.current;
      if (!outer || !list) return;
      const fits = list.scrollWidth <= outer.clientWidth;
      setMoving(!reduce.matches && !fits);
      setSeconds(Math.max(12, Math.round(list.scrollWidth / SPEED)));
    };
    measure();
    const watcher = new ResizeObserver(measure);
    if (box.current) watcher.observe(box.current);
    reduce.addEventListener("change", measure);
    return () => {
      watcher.disconnect();
      reduce.removeEventListener("change", measure);
    };
  }, [items]);

  return (
    <>
      <div
        ref={box}
        className="ticker"
        data-moving={moving}
        data-paused={paused}
        style={{ "--ticker-seconds": `${seconds}s` } as React.CSSProperties}
      >
        <div className="ticker-track">
          <ul ref={one}>
            {items.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
          {moving && (
            <ul aria-hidden="true">
              {items.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
      {moving && (
        <button
          type="button"
          className="ticker-btn"
          onClick={() => setPaused((p) => !p)}
          aria-label={paused ? "Play moving notices" : "Pause moving notices"}
        >
          <Icon name={paused ? "play" : "pause"} />
        </button>
      )}
    </>
  );
}
