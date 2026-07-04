import { getRecommendations } from "@/shared/api";
import type { HintDish } from "./hints-mock";

export async function fetchRealHints(
  clientId: number,
  options?: { hunger?: string; allergies?: string[]; checkedIn?: boolean }
): Promise<HintDish[]> {
  try {
    const data = await getRecommendations(clientId, {
      hunger: options?.hunger,
      allergies: options?.allergies,
    });
    return (data.recommendations || []).map(
      (r: { id: number; name: string; price: number; category: string; tags?: string[] }) => ({
        id: r.id ?? 0,
        name: r.name,
        price: r.price,
        tags: r.tags ?? (options?.checkedIn ? ["по профилю"] : []),
        category: r.category,
      })
    );
  } catch {
    return [];
  }
}
