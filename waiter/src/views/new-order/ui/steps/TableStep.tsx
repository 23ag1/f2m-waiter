"use client";

import type { IikoTable } from "../../model/types";

// Wizard step 1: search + pick a table, grouped by section, colour-coded by ownership.
export function TableStep({
  tableSearch,
  onSearch,
  tablesLoading,
  tablesError,
  sections,
  myTableNumbers,
  onSelect,
}: {
  tableSearch: string;
  onSearch: (v: string) => void;
  tablesLoading: boolean;
  tablesError: string;
  sections: Record<string, IikoTable[]>;
  myTableNumbers: Set<string>;
  onSelect: (table: IikoTable) => void;
}) {
  return (
    <main className="flex-1 overflow-y-auto p-4 pb-8">
      {/* Search */}
      <div className="relative mb-4">
        <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-subtle" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          type="text"
          value={tableSearch}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Поиск стола..."
          className="w-full bg-surface border border-hair rounded-2xl pl-9 pr-4 py-3 text-ink placeholder-gray-400 focus:outline-none focus:border-gray-400"
        />
      </div>

      {tablesLoading && (
        <div className="flex items-center justify-center p-10 text-ink-subtle">
          <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Загрузка...
        </div>
      )}
      {tablesError && (
        <div className="bg-red-50 text-red-700 p-4 rounded-xl text-sm">{tablesError}</div>
      )}

      {!tablesLoading && !tablesError && (
        <div className="space-y-5">
          {/* Legend */}
          <div className="flex items-center gap-4 text-xs text-ink-muted">
            <span className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-green-500 inline-block" />Свободен</span>
            <span className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-blue-500 inline-block" />Мой стол</span>
          </div>

          {Object.keys(sections).length === 0 && (
            <div className="text-center text-ink-subtle py-8">Столы не найдены</div>
          )}

          {Object.entries(sections).map(([sectionName, sectionTables]) => (
            <div key={sectionName}>
              <h3 className="text-sm font-semibold text-ink-muted mb-3">{sectionName}</h3>
              <div className="grid grid-cols-7 gap-2">
                {sectionTables.map((table) => {
                  const isMine = myTableNumbers.has(String(table.number));
                  return (
                    <button
                      key={table.id}
                      onClick={() => onSelect(table)}
                      className={`h-10 rounded-xl flex items-center justify-center font-bold text-white text-sm active:scale-95 transition-transform shadow-sm ${
                        isMine ? "bg-blue-500" : "bg-green-500"
                      }`}
                    >
                      {table.number}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
