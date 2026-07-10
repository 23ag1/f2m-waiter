"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { getIikoTables, getActiveTables, createTableSession } from "@/shared/api";
import { Toast } from "@/shared/ui/Toast";
import { useToast } from "@/shared/lib/use-toast";
import type { IikoTable } from "../model/types";
import { TableStep } from "./steps/TableStep";
import { GuestsStep } from "./steps/GuestsStep";

export function NewOrderView() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-app flex items-center justify-center text-ink-subtle">Загрузка...</div>}>
      <NewOrderPage />
    </Suspense>
  );
}

// New-order wizard: pick table → pick guests → create session. Then it opens the
// SAME order-card screen used to VIEW an order, so creating and viewing look and
// behave identically (no separate "fill" screen to keep in sync).
function NewOrderPage() {
  const router = useRouter();
  const { toast, showToast } = useToast();

  const [step, setStep] = useState<"table" | "guests">("table");
  const [tables, setTables] = useState<IikoTable[]>([]);
  const [tablesLoading, setTablesLoading] = useState(true);
  const [tablesError, setTablesError] = useState("");
  const [selectedTable, setSelectedTable] = useState<IikoTable | null>(null);
  const [tableSearch, setTableSearch] = useState("");
  const [guestsCount, setGuestsCount] = useState(1);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [myTableNumbers, setMyTableNumbers] = useState<Set<string>>(new Set());

  useEffect(() => {
    setTablesLoading(true);
    Promise.all([
      getIikoTables().then((data) => setTables(data.tables || [])),
      getActiveTables()
        .then((data) => setMyTableNumbers(new Set<string>((data.tables || []).map((t: { table_number: string }) => t.table_number))))
        .catch(() => {}),
    ])
      .catch((e) => setTablesError(e.message))
      .finally(() => setTablesLoading(false));
  }, []);

  const filteredTables = tables.filter(
    (t) =>
      t.name.toLowerCase().includes(tableSearch.toLowerCase()) ||
      String(t.number).includes(tableSearch) ||
      t.section_name.toLowerCase().includes(tableSearch.toLowerCase())
  );

  const sections = filteredTables.reduce<Record<string, IikoTable[]>>((acc, t) => {
    const key = t.section_name || "Без секции";
    (acc[key] ||= []).push(t);
    return acc;
  }, {});

  const handleTableSelect = (table: IikoTable) => {
    setSelectedTable(table);
    setStep("guests");
  };

  const handleCreateSession = async (orderType: "new" | "add") => {
    if (!selectedTable) return;
    setSessionLoading(true);
    try {
      const res = await createTableSession(selectedTable.id, String(selectedTable.number), guestsCount, orderType);
      const firstClient = res.guests?.[0]?.client_id;
      if (firstClient == null) throw new Error("Сессия создана без гостей");
      // Open the order card (same screen as viewing an existing order).
      router.replace(`/dashboard/basket/${firstClient}?table=${selectedTable.number}&tableId=${res.table_id}`);
    } catch (e: unknown) {
      setSessionLoading(false);
      showToast("Ошибка создания сессии: " + (e instanceof Error ? e.message : "Unknown error"), "err");
    }
  };

  return (
    <div className="min-h-[100dvh] bg-app flex flex-col">
      <header className="bg-surface border-b border-hair-soft sticky top-0 z-10">
        <div className="flex items-center px-4 py-3">
          <button
            onClick={() => (step === "guests" ? setStep("table") : router.push("/dashboard"))}
            className="flex items-center gap-1 text-blue-500 font-medium text-sm mr-2 flex-shrink-0"
          >
            <ChevronLeft className="h-5 w-5" />
            Заказы
          </button>
          <div className="flex-1 text-center">
            <h1 className="text-base font-semibold text-ink">
              {step === "table" ? "Выберите стол" : `Стол ${selectedTable?.number}`}
            </h1>
            {step === "guests" && selectedTable && (
              <p className="text-xs text-ink-muted">{selectedTable.section_name}</p>
            )}
          </div>
          <div className="w-16" />
        </div>
      </header>

      {step === "table" && (
        <TableStep
          tableSearch={tableSearch}
          onSearch={setTableSearch}
          tablesLoading={tablesLoading}
          tablesError={tablesError}
          sections={sections}
          myTableNumbers={myTableNumbers}
          onSelect={handleTableSelect}
        />
      )}

      {step === "guests" && selectedTable && (
        <GuestsStep
          table={selectedTable}
          guestsCount={guestsCount}
          onCountChange={setGuestsCount}
          sessionLoading={sessionLoading}
          onCreate={handleCreateSession}
        />
      )}

      <Toast toast={toast} />
    </div>
  );
}
