# Order Refunds

## Status

Draft.

## Overview

Customers can get refunds for orders they are unhappy with.

## Rules

1. Refunds should be processed quickly.
2. Large refunds must be approved by a manager.
3. The order is updated after the refund.
4. Call `processRefund()` in the payments service and insert a row into the `refunds` table.
5. It must not be refunded twice.
6. Partial refunds may be allowed where appropriate.
