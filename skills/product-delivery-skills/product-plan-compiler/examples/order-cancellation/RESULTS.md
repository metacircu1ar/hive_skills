# Example Results

## Buggy model

Property:

```text
status = Cancelled => hasShipment = false
```

Shortest violating trace:

```text
Created
  -> Pay
Paid
  -> CreateShipment
Shipped, hasShipment = true
  -> CancelBad
Cancelled, hasShipment = true
```

Classification: `PLAN_DEFECT`.

`REQ-001`, `REQ-003`, and `REQ-004` cannot all be maintained after the sequence above.

## Corrected model

The cancellation transition is restricted to `Created` or `Paid` states and requires `hasShipment = false`.

The bundled exhaustive fallback checker reports:

```text
Fixed model
  reachable states: 6
  invariant violation: no
```

This result applies only to the finite abstraction in the example. Execute the `.tla` and `.cfg` files with TLC for native evidence.
