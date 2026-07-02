"use client";

import { useState } from "react";
import { sendSessionOrder, sendOrder, printBill } from "@/shared/api";

const errMsg = (e: unknown) => (e instanceof Error ? e.message : "Unknown error");

/** Send the order to iiko / print the pre-check. Multi-guest sends the table session. */
export function useSendOrder({
  tableId,
  clientId,
  tableNum,
  showToast,
  onDone,
}: {
  tableId: string | null;
  clientId: number;
  tableNum: string;
  showToast: (m: string, t?: "ok" | "err") => void;
  onDone: () => void;
}) {
  const [sending, setSending] = useState(false);

  const send = async (comment?: string) => {
    if (tableId) {
      setSending(true);
      try {
        const res = await sendSessionOrder(Number(tableId), comment || undefined);
        showToast(res.message || "Заказ отправлен!");
        onDone();
      } catch (e) {
        showToast("Ошибка отправки: " + errMsg(e), "err");
      } finally {
        setSending(false);
      }
    } else {
      if (!tableNum) { showToast("Введите номер стола", "err"); return; }
      try {
        await sendOrder(clientId, tableNum);
        showToast("Заказ отправлен в iiko!");
      } catch (e) {
        showToast("Ошибка отправки: " + errMsg(e), "err");
      }
    }
  };

  const print = async () => {
    if (!tableNum) { showToast("Введите номер стола", "err"); return; }
    try {
      await printBill(clientId, tableNum);
      showToast("Пречек отправлен!");
      onDone();
    } catch (e) {
      showToast("Ошибка печати: " + errMsg(e), "err");
    }
  };

  return { sending, send, print };
}
