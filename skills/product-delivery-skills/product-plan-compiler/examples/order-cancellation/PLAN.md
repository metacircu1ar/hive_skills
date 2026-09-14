# Order Cancellation Plan Example

## Version 0

- `REQ-001`: A customer may cancel any order that has not been delivered.
- `REQ-002`: The warehouse may create a shipment after the order is paid.
- `REQ-003`: A cancelled order must not have a shipment.
- `REQ-004`: Shipment records are immutable and cannot be deleted.

## Counterexample-derived refinement

- `REQ-001-v2`: A customer may cancel an order only before a shipment has been created. After shipment creation, the customer must use the return/refusal workflow instead of cancellation.

## Deferred scope

The return/refusal workflow is intentionally outside this tiny example and must be modeled before making claims about post-shipment customer outcomes.
