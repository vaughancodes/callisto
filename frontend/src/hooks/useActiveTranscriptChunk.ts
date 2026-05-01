import { useEffect, useState } from "react";

interface ChunkLike {
  start_ms: number;
  end_ms: number;
}

/**
 * Tracks the index of the transcript chunk that matches the audio
 * element's current playback position. Returns -1 when nothing is
 * playing, the audio is paused before the first chunk, or the chunks
 * array is empty.
 *
 * Pass the audio element directly (stored via a ref callback into
 * useState — see callers) so React re-runs this effect when the
 * element mounts. A plain RefObject doesn't trigger re-renders, which
 * means listeners would never be attached if the <audio> element is
 * conditionally rendered after the parent's first paint.
 *
 * `offsetMs` lets you align audio time (always starting at 0) with
 * chunk timestamps that are expressed in some other reference frame.
 * For full-call audio it's 0; for sliced voicemail audio it's the
 * voicemail's `started_at_ms` (so audio 0s == voicemail's first word
 * == chunk.start_ms).
 */
export function useActiveTranscriptChunk(
  audioEl: HTMLAudioElement | null,
  chunks: ChunkLike[] | null | undefined,
  offsetMs: number = 0
): number {
  const [activeIndex, setActiveIndex] = useState(-1);

  useEffect(() => {
    if (!audioEl || !chunks || chunks.length === 0) {
      setActiveIndex(-1);
      return;
    }

    const recompute = () => {
      if (audioEl.paused && audioEl.currentTime === 0) {
        setActiveIndex(-1);
        return;
      }
      const tMs = audioEl.currentTime * 1000 + offsetMs;
      // Linear scan; transcripts here are tens of chunks, fine.
      let idx = -1;
      for (let i = 0; i < chunks.length; i++) {
        const c = chunks[i];
        if (tMs >= c.start_ms && tMs < c.end_ms) {
          idx = i;
          break;
        }
        // If we passed the chunk's end but haven't reached the next
        // start yet (gap of silence), keep highlighting the last
        // chunk so the cursor doesn't flicker off.
        if (tMs >= c.end_ms) {
          idx = i;
        }
      }
      setActiveIndex(idx);
    };

    audioEl.addEventListener("timeupdate", recompute);
    audioEl.addEventListener("seeked", recompute);
    audioEl.addEventListener("play", recompute);
    audioEl.addEventListener("pause", recompute);
    recompute();

    return () => {
      audioEl.removeEventListener("timeupdate", recompute);
      audioEl.removeEventListener("seeked", recompute);
      audioEl.removeEventListener("play", recompute);
      audioEl.removeEventListener("pause", recompute);
    };
  }, [audioEl, chunks, offsetMs]);

  return activeIndex;
}
