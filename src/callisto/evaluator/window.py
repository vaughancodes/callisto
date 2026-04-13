"""Sliding context window for real-time insight evaluation.

Maintains a rolling window of the last ~60 seconds of transcript per call.
Controls evaluation frequency to manage LLM costs.
"""

from collections import deque
from dataclasses import dataclass


@dataclass
class TranscriptChunk:
    call_id: str
    tenant_id: str
    text: str
    start_ms: int
    end_ms: int
    chunk_index: int
    speaker: str = "unknown"
    confidence: float = 0.0


class SlidingWindow:
    """Rolling window of transcript chunks for a single call."""

    def __init__(self, max_duration_ms: int = 60000, eval_interval: int = 3):
        self.chunks: deque[TranscriptChunk] = deque()
        self.max_duration_ms = max_duration_ms
        self.eval_counter = 0
        self.eval_interval = eval_interval

    def add(self, chunk: TranscriptChunk):
        self.chunks.append(chunk)
        self.eval_counter += 1

        # Evict chunks older than the window
        while len(self.chunks) > 1 and (
            self.chunks[-1].end_ms - self.chunks[0].start_ms > self.max_duration_ms
        ):
            self.chunks.popleft()

    def should_evaluate(self) -> bool:
        return self.eval_counter % self.eval_interval == 0 and len(self.chunks) > 0

    def get_text(self) -> str:
        return " ".join(c.text for c in self.chunks if c.text.strip())

    def get_range(self) -> dict:
        if not self.chunks:
            return {}
        return {
            "start_chunk": self.chunks[0].chunk_index,
            "end_chunk": self.chunks[-1].chunk_index,
            "start_ms": self.chunks[0].start_ms,
            "end_ms": self.chunks[-1].end_ms,
        }

    @property
    def is_empty(self) -> bool:
        return len(self.chunks) == 0
