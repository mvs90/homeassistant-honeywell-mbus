# Contributing

Use Python 3.14 and the dependencies in `requirements-test.txt` plus the desired
Home Assistant version. Run Ruff and the complete test suite before proposing a
change. The TCP simulator binds only to loopback and does not require credentials.

Support for another meter/profile needs anonymized, checksum-valid fixtures, units
derived from the relevant VIF definitions and tests for corrupt/unsupported frames.
Do not relax identity or unit checks to force an unverified device to work. Do not
include real serials, private addresses, credentials or raw user audit exports.

Keep the API independent of HA. Keep I/O asynchronous, retries bounded and unload
cleanup deterministic. Any future control or firmware-update functionality needs
separate design/review; it is outside this read-only integration's scope.
