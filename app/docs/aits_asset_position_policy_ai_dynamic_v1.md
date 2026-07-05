# AITS Asset Position Policy AI Dynamic v1

Asset `0%` or missing position weight means AI dynamic mode. It is not global
inheritance and it is not a zero allocation. A positive asset weight is a manual
candidate/order-stage override.

ON-start preflight has no candidate symbol, so it validates only account,
order amount, per-order hard cap, and guarded-window cap. Candidate/order stage
may later apply a positive asset override, while `0%` or missing remains AI
dynamic and must still pass RiskGuard, LivePreflight, duplicate/relock, and
one-shot unlock before any order path can proceed.
