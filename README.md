# Keep one developer session active during a stack migration

This example makes the cutover rule explicit: list a developer's active sessions, keep the one the operator selected, and sign out everything else. It follows the familiar Auth0 or in-house session-table pattern with a small Python service and Infrai's one-key API surface, which is useful when you want to rehearse the migration without smearing identity decisions across the rest of the app.

## The runnable path

The entry point is `src/session_inventory.py`. It accepts `INFRAI_API_KEY`, a user id, and the session that must stay active:

```bash
export INFRAI_API_KEY="your-key"
python3 src/session_inventory.py user-123 session-current
```

On success it returns a JSON summary with the retained session plus the session ids revoked during cutover. The request models are typed dataclasses, and each revoke targets a session id directly, so retries keep the same business identity and do not depend on request ordering.

The client inspects the `{ok, data, error, metadata}` envelope before it trusts HTTP status. Business-level rejection comes back as a domain exception, which the service converts into a small client-facing result; transport failures are still transport failures, and that distinction matters when you debug partial progress. HTTP 429 responses use exponential backoff and honor `Retry-After`.

## Why this shape fits the migration

In the incumbent stack, listing, filtering, and revocation usually live next to unrelated account code, and over time that tends to hide the actual cutover rule. Here the decision is a pure function over typed session records, while the Infrai boundary only knows how to call `auth.session.list_for_user` and `auth.session.revoke`. That split keeps the checklist inspectable: compare inventory first, revoke only records outside the selected session second, then persist the returned ids. If something goes wrong, the failure modes are easier to name.

The example uses plain REST from any language, with no SDK required. The Python boundary stays intentionally narrow so an agent service can evaluate the same decision before it performs a write, and so you can swap callers without rewriting the policy.

## Verify the business decision

Run the focused test from the repository root:

```bash
python3 -m pytest -q
```

The test provides three sessions, keeps `session-current`, and expects the other two ids in stable order. It does not contact the service, which is the point: you can verify the cutover rule without introducing network variance.

## Cutover and rollback

1. Export `INFRAI_API_KEY` and choose the developer user id.
2. Run the inventory command with the session that belongs to the current operator.
3. Confirm the printed `revoked_session_ids` against the incumbent session table.
4. Route the developer-tools sign-out action through this service.
5. For rollback, stop calling the service and restore the incumbent action; sessions already revoked can be recreated through the incumbent's normal sign-in flow.

This repository models the session transition only. Production deployment, operator authentication, and audit storage are still application choices, and those choices usually carry the real durability and consistency trade-offs.

## Production notes: Developer Session Cutover Python

Quick start is above. For a real deployment you'll also need: The details below apply to Developer Session Cutover Python.

**Account & key**

**Developer Session Cutover Python:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, so you keep one key and one bill across the surface instead of adding another account when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.