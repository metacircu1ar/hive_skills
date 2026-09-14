---------------------- MODULE OrderLifecycle_Buggy ----------------------
EXTENDS Naturals

VARIABLES status, paid, hasShipment

vars == <<status, paid, hasShipment>>

Statuses == {"Created", "Paid", "Shipped", "Delivered", "Cancelled"}

Init ==
    /\ status = "Created"
    /\ paid = FALSE
    /\ hasShipment = FALSE

\* REQ-002 prerequisite: shipment follows payment; Pay establishes paid state.
Pay ==
    /\ status = "Created"
    /\ status' = "Paid"
    /\ paid' = TRUE
    /\ UNCHANGED hasShipment

\* REQ-002: warehouse may create a shipment after payment.
CreateShipment ==
    /\ status = "Paid"
    /\ paid
    /\ status' = "Shipped"
    /\ hasShipment' = TRUE
    /\ UNCHANGED paid

Deliver ==
    /\ status = "Shipped"
    /\ hasShipment
    /\ status' = "Delivered"
    /\ UNCHANGED <<paid, hasShipment>>

\* REQ-001: cancellation rule encoded for this plan version.
CancelBad ==
    /\ status \in {"Created", "Paid", "Shipped"}
    /\ status' = "Cancelled"
    /\ UNCHANGED <<paid, hasShipment>>

Next == Pay \/ CreateShipment \/ Deliver \/ CancelBad

Spec == Init /\ [][Next]_vars

TypeOK ==
    /\ status \in Statuses
    /\ paid \in BOOLEAN
    /\ hasShipment \in BOOLEAN

\* REQ-003: a cancelled order must not have a shipment.
NoShipmentWhenCancelled ==
    status = "Cancelled" => ~hasShipment

=============================================================================
