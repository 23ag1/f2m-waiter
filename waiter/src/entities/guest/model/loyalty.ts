// Mock loyalty profiles assigned on QR check-in (no backend yet).
export interface LoyaltyProfile {
  name: string;
  hunger: string;
  allergies: string[];
  dislikes: string[];
}

const MOCK_LOYALTY_PROFILES: LoyaltyProfile[] = [
  { name: "Маша С.",    hunger: "средний",  allergies: ["Рыба"],     dislikes: [] },
  { name: "Катя В.",    hunger: "низкий",   allergies: ["Орехи"],    dislikes: ["Лук"] },
  { name: "Алексей П.", hunger: "высокий",  allergies: [],           dislikes: [] },
  { name: "Дмитрий К.", hunger: "средний",  allergies: ["Лактоза"],  dislikes: ["Грибы"] },
  { name: "Ирина М.",   hunger: "низкий",   allergies: ["Глютен"],   dislikes: [] },
];

let idx = 0;
export function nextLoyaltyProfile(): LoyaltyProfile {
  const p = MOCK_LOYALTY_PROFILES[idx % MOCK_LOYALTY_PROFILES.length];
  idx++;
  return p;
}
