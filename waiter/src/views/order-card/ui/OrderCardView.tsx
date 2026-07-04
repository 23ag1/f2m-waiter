"use client";

import { useSearchParams } from "next/navigation";
import { TableOrderView } from "./TableOrderView";
import { SingleGuestBasketView } from "./SingleGuestBasketView";

/**
 * Order-card entry point. A `tableId` in the URL means a table order (many
 * guests, inline menu); without it we show a single-client basket (QR-scan /
 * menu-add flow). Each mode is a fully self-contained view.
 */
export function OrderCardView() {
  const tableIdParam = useSearchParams().get("tableId");
  return tableIdParam ? <TableOrderView /> : <SingleGuestBasketView />;
}
