"use client";

import { Pause, Play, Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type WaveSurfer from "wavesurfer.js";

interface AudioPlayerProps {
  src: string | null;
  languageLabel: string;
  durationHint: number;
}

function clock(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const minutes = Math.floor(seconds / 60);
  const rest = Math.floor(seconds % 60);
  return `${minutes}:${rest.toString().padStart(2, "0")}`;
}

export function AudioPlayer({ src, languageLabel, durationHint }: AudioPlayerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const waveRef = useRef<WaveSurfer | null>(null);
  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(durationHint);
  const [current, setCurrent] = useState(0);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!src || !containerRef.current) return;

    let cancelled = false;
    let instance: WaveSurfer | null = null;

    import("wavesurfer.js")
      .then(({ default: WaveSurfer }) => {
        if (cancelled || !containerRef.current) return;
        instance = WaveSurfer.create({
          container: containerRef.current,
          url: src,
          height: 52,
          waveColor: "#c0b7a3",
          progressColor: "#0e4b46",
          cursorColor: "#a8342a",
          cursorWidth: 1,
          barWidth: 2,
          barGap: 2,
          barRadius: 2,
          normalize: true,
        });
        waveRef.current = instance;
        instance.on("ready", () => {
          if (!cancelled) setDuration(instance?.getDuration() ?? durationHint);
        });
        instance.on("timeupdate", (time: number) => {
          if (!cancelled) setCurrent(time);
        });
        instance.on("play", () => setPlaying(true));
        instance.on("pause", () => setPlaying(false));
        instance.on("finish", () => setPlaying(false));
        instance.on("error", () => {
          if (!cancelled) setFailed(true);
        });
      })
      .catch(() => setFailed(true));

    return () => {
      cancelled = true;
      instance?.destroy();
      waveRef.current = null;
    };
  }, [src, durationHint]);

  if (!src) {
    return (
      <div className="border border-rule bg-paper px-4 py-5">
        <p className="flex items-center gap-2 text-sm text-soft">
          <Volume2 size={16} aria-hidden="true" />
          No audio was produced for this document.
        </p>
      </div>
    );
  }

  return (
    <div className="border border-rule bg-paper px-4 py-4">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => waveRef.current?.playPause()}
          className="flex h-10 w-10 shrink-0 items-center justify-center border border-seal bg-seal text-[#fbf8f0] transition-colors hover:bg-seal-deep disabled:opacity-50"
          aria-label={playing ? "Pause the briefing" : "Play the briefing"}
          disabled={failed}
        >
          {playing ? (
            <Pause size={18} strokeWidth={2} aria-hidden="true" />
          ) : (
            <Play size={18} strokeWidth={2} aria-hidden="true" />
          )}
        </button>

        <div className="min-w-0 flex-1">
          <div ref={containerRef} aria-hidden="true" className="min-h-[52px] w-full" />
          <div className="mt-1 flex items-center justify-between font-mono text-[0.68rem] text-soft">
            <span>
              {clock(current)} / {clock(duration)}
            </span>
            <span>{languageLabel}</span>
          </div>
        </div>
      </div>

      {failed ? (
        <p className="mt-3 text-sm font-medium text-stamp" role="alert">
          The audio file could not be loaded. The written briefing is still available.
        </p>
      ) : (
        <p className="sr-only">
          Audio briefing in {languageLabel}, about {Math.round(durationHint / 60)} minutes long.
        </p>
      )}
    </div>
  );
}
