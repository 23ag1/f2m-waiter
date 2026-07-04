"use client";

import { TableCard, type ActiveTable } from "@/entities/table";

// Orders grouped by iiko section (Зал / Веранда / …), each a labelled block.
export function OrdersList({
  tables,
  sectionMap,
  nameOverrides,
  onCardLongPress,
}: {
  tables: ActiveTable[];
  sectionMap: Record<string, string>;
  nameOverrides?: Record<number, string>;
  onCardLongPress?: (table: ActiveTable, anchor: { x: number; y: number }) => void;
}) {
  const order: string[] = [];
  const sections: Record<string, ActiveTable[]> = {};
  for (const table of tables) {
    const section = sectionMap[String(table.table_number)] || "Зал";
    if (!sections[section]) {
      sections[section] = [];
      order.push(section);
    }
    sections[section].push(table);
  }

  return (
    <>
      {order.map((sectionName) => (
        <div key={sectionName} className="mb-4">
          <h2 className="text-lg font-bold text-ink mb-2 px-1">{sectionName}</h2>
          <div className="grid grid-cols-2 gap-3">
            {sections[sectionName].map((table) => (
              <TableCard
                key={table.id}
                table={table}
                nameOverride={nameOverrides?.[table.id]}
                onLongPress={onCardLongPress ? (anchor) => onCardLongPress(table, anchor) : undefined}
              />
            ))}
          </div>
        </div>
      ))}
    </>
  );
}
