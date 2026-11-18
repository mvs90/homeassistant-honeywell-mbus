# Protocol boundary and supported profile

`api.py` is the transport/decoder API. It has no dependency on Home Assistant,
MQTT, subprocesses, external packages or filesystem state. It uses standard
`asyncio` TCP streams and a per-client lock. The integration coordinator owns one
client and closes it on setup failure or successful unload.

Only addressed M-Bus `REQ_UD2` frames with control byte `0x5b` or `0x7b` are
constructed. FCB alternates after a valid decoded reply. Timeouts, invalid frames
and replayed access counters get at most one retry after reconnect. Profile,
identity and meter-status errors fail without repeatedly querying the wrong device.
Cancellation discards a possibly partial stream. Concurrent refresh requests are
serialized. No gateway management commands, broadcast, SND_NKE, SND_UD, reset,
baud change or secondary-address selection are generated.

The first request after constructing a client is followed by another request after
1.3 seconds. Both identities must agree and the access counter must advance. Later
readings must differ from the last accepted counter; 255→0 is valid. This protects
against stale frames; it is not a cryptographic authenticity guarantee. The raw
TCP gateway itself should be kept on a trusted local network.

The profile is intentionally narrow: HON manufacturer bytes EE21, device-version
0x15, electrical medium, a 152-byte response and the validated record order. The
version byte is not an exact firmware version. Unsupported record variants are
rejected. Energy VIF04/05 means 0.01/0.1 kWh; power VIF AC/AD means 10/100 W.
Signed active/reactive power is retained. Resettable partial counters are validated
but excluded from sensor output. Raw phase values are not multiplied again by the
reported current-transformer ratio.

Within a client session, a decreasing cumulative total is rejected, including
between the two initial validation replies. This avoids accidental energy resets
from corrupt/stale responses. A deliberate meter replacement needs a new entry;
handling a genuine lifetime-counter reset requires supervised verification.

`tests/fixtures/eem400c_v15.hex` uses a synthetic serial (`12345678`), primary
address 1 and synthetic energy total (1234.5 kWh), based on the validated record
layout. It contains no actual home addresses, credentials or original audit dump.
The loopback simulator checks every transmitted request against the allowed reads.

Current limitations: one primary-addressed meter per TCP bridge; no generic
M-Bus profile decoder; no claim that other vendor/model/firmware combinations are
compatible; no on-device production acceptance in version 0.1.0 preparation.
