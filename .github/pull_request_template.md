## Summary

<!-- What changed and why? -->

## Money-path checklist

- [ ] Order intake, validation, supplier placement, shipment, and delivery behavior are covered.
- [ ] Supplier cost, shipping, payment fees, and minimum margin are accounted for where prices change.
- [ ] Price changes remain within configured bounds and are written to the audit log.
- [ ] Duplicate webhooks cannot create duplicate supplier orders.
- [ ] Out-of-stock, supplier failure, and refund approval paths are handled safely.
- [ ] No payment, refund, or customer-facing action is performed without its required integration or approval.

## Verification

- [ ] `python -m unittest discover -s tests -v`
- [ ] `python scripts/demo_loop.py` (when workflow behavior changes)