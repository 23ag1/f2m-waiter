// Mock waiter roster for "Сменить официанта" — no backend endpoint yet.
export interface Waiter {
  id: number;
  name: string;
  initial: string;
}

export const WAITERS: Waiter[] = [
  { id: 1, name: "Официант W", initial: "W" },
  { id: 2, name: "Анна Началова", initial: "А" },
  { id: 3, name: "Дмитрий Козлов", initial: "Д" },
  { id: 4, name: "Мария Соколова", initial: "М" },
  { id: 5, name: "Илья Петров", initial: "И" },
];
