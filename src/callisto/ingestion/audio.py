"""Audio decoding and buffering for Twilio Media Streams.

Twilio sends base64-encoded mulaw audio at 8kHz. This module decodes it
to 16-bit PCM and resamples to 16kHz for transcription services.

Uses struct-based decoding instead of the deprecated audioop module
(removed in Python 3.13).
"""

import array
import base64
import struct

# mulaw decompression lookup table (ITU-T G.711)
# Each mulaw byte maps to a signed 16-bit PCM sample.
_MULAW_DECODE_TABLE = array.array("h", [0] * 256)


def _build_mulaw_table():
    """Build the mulaw → PCM lookup table per G.711 spec."""
    BIAS = 0x84
    CLIP = 32635
    exp_lut = [0, 132, 396, 924, 1980, 4092, 8316, 16764]

    for i in range(256):
        val = ~i
        sign = val & 0x80
        exponent = (val >> 4) & 0x07
        mantissa = val & 0x0F
        sample = exp_lut[exponent] + (mantissa << (exponent + 3))
        if sign != 0:
            sample = -sample
        _MULAW_DECODE_TABLE[i] = max(-32768, min(32767, sample))


_build_mulaw_table()


def ulaw_decode(mulaw_bytes: bytes) -> bytes:
    """Decode mulaw-encoded bytes to signed 16-bit little-endian PCM."""
    samples = array.array("h", (
        _MULAW_DECODE_TABLE[b] for b in mulaw_bytes
    ))
    if samples.itemsize == 2:
        return samples.tobytes()
    # Fallback: pack explicitly
    return struct.pack(f"<{len(samples)}h", *samples)


def resample_8k_to_16k(pcm_8khz: bytes) -> bytes:
    """Resample 16-bit PCM from 8kHz to 16kHz using linear interpolation.

    Simple but effective for speech audio. Each sample is doubled with
    a linearly interpolated sample inserted between each pair.
    """
    # Unpack as signed 16-bit little-endian samples
    n_samples = len(pcm_8khz) // 2
    if n_samples == 0:
        return b""

    samples = struct.unpack(f"<{n_samples}h", pcm_8khz)
    out = []
    for i in range(n_samples - 1):
        out.append(samples[i])
        # Interpolated midpoint
        mid = (samples[i] + samples[i + 1]) // 2
        out.append(mid)
    # Last sample, duplicated
    out.append(samples[-1])
    out.append(samples[-1])

    return struct.pack(f"<{len(out)}h", *out)


class AudioBuffer:
    """Accumulates decoded PCM audio and emits fixed-size chunks."""

    def __init__(self, chunk_duration_ms: int = 500):
        self.buffer = bytearray()
        # 16kHz, 16-bit (2 bytes per sample)
        self.chunk_size = 16000 * 2 * chunk_duration_ms // 1000

    def ingest(self, audio_bytes: bytes) -> list[bytes]:
        """Add audio bytes to the buffer and return any complete chunks."""
        self.buffer.extend(audio_bytes)
        chunks = []
        while len(self.buffer) >= self.chunk_size:
            chunks.append(bytes(self.buffer[: self.chunk_size]))
            self.buffer = self.buffer[self.chunk_size :]
        return chunks

    def has_remaining(self) -> bool:
        return len(self.buffer) > 0

    def flush(self) -> bytes:
        """Return whatever is left in the buffer."""
        data = bytes(self.buffer)
        self.buffer = bytearray()
        return data


def decode_twilio_media(payload_b64: str) -> bytes:
    """Decode a Twilio media payload to 16kHz 16-bit PCM.

    Twilio sends base64-encoded mulaw at 8kHz single channel.
    We decode to linear PCM and upsample to 16kHz.
    """
    mulaw_bytes = base64.b64decode(payload_b64)
    pcm_8khz = ulaw_decode(mulaw_bytes)
    pcm_16khz = resample_8k_to_16k(pcm_8khz)
    return pcm_16khz
