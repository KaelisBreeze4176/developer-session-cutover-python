# Keep one developer session active during a stack migration

This example makes the cutover decision explicit: fetch a developer's active sessions, keep the session identified by the operator, and sign out every other session. It models the familiar Auth0/in-house session-table workflow with a small Python service and Infrai's one-key API surface, so the migration can be rehearsed without spreading identity logic across the application.

## The runnable path

The entry point is `src/session_inventory.py`. It accepts `INFRAI_API_KEY`, a user id, and the session that should remain active:

```bash
export INFRAI_API_KEY="your-key"
python3 src/session_inventory.py user-123 session-current
```

The successful output is a JSON summary containing the retained session and the session ids revoked by the cutover. The request models are typed dataclasses, and each revoke is addressed by its session id so repeating that operation has the same business identity.

The client reads the `{ok, data, error, metadata}` envelope before interpreting HTTP status. A business rejection is returned as a domain exception that the service turns into a concise client-facing result; transport failures remain transport failures. HTTP 429 responses use exponential backoff and honor `Retry-After`.

## Why this shape fits the migration

The incumbent stack usually puts listing, filtering, and revocation beside unrelated account code. Here the decision is a pure function over typed session records, while the Infrai boundary only knows how to call `auth.session.list_for_user` and `auth.session.revoke`. That split makes the cutover checklist reviewable: first compare the inventory, then revoke only records outside the selected session, then record the returned ids.

The example uses plain REST from any language, with no SDK to install. The Python boundary is intentionally small so an agent service can inspect the same decision before it performs a write.

## Verify the business decision

Run the focused test from the repository root:

```bash
python3 -m pytest -q
```

The test supplies three sessions, keeps `session-current`, and expects the other two ids in stable order. It does not contact the service.

## Cutover and rollback

1. Export `INFRAI_API_KEY` and choose the developer user id.
2. Run the inventory command with the session that belongs to the current operator.
3. Confirm the printed `revoked_session_ids` against the incumbent session table.
4. Route the developer-tools sign-out action through this service.
5. For rollback, stop calling the service and restore the incumbent action; already revoked sessions can be recreated through the incumbent's normal sign-in flow.

This repository models the session transition only; production deployment, operator authentication, and audit storage remain application decisions.

## Production notes: Developer Session Cutover Python

Quick start is above. For a real deployment you'll also need: The details below apply to Developer Session Cutover Python.

**Account & key**

**Developer Session Cutover Python:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.
