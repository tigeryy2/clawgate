# Documentation Home

## V1 HTTP Contract

- Canonical base path: `/v1`
- Optional alias path: `/api` (disabled unless `ENABLE_API_ALIAS=true`)
- Read endpoints are REST resource routes.
- Mutating or side-effect actions use `POST ...:{action}/propose|execute`.
- Core approval APIs live under `/v1/approvals/*`.
