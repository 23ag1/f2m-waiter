type Dict = Record<string, unknown>;

export type F2MRecommendation = {
  dish_id: string;
  score: number;
};

export type F2MScoreResponse = {
  request_id: string;
  results: F2MRecommendation[];
};

const BASE_URL = String(import.meta.env.VITE_F2M_ENGINE_URL ?? '').replace(/\/+$/, '');
const SOURCE_SYSTEM = 'waiter_web';
const REQUEST_TIMEOUT_MS = 7000;

function uuidLike(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function normalizeConstraintValue(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, '_').replace(/[^a-zа-яё0-9_]/gi, '');
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  if (!BASE_URL) {
    throw new Error('VITE_F2M_ENGINE_URL is empty');
  }

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`F2M request failed: ${path} (${response.status})`);
    }

    return (await response.json()) as T;
  } finally {
    window.clearTimeout(timer);
  }
}

export async function submitQuestionnaire(
  userId: number,
  answers: Dict,
  allergies: string[],
): Promise<{ status: string; user_id: number }> {
  const hard_constraints = allergies.map((allergy) => ({
    constraint_key: `allergen_${normalizeConstraintValue(allergy)}`,
    scope: 'hard',
    source: 'react_quiz',
    reason_text: `allergy:${allergy}`,
  }));

  return postJson('/questionnaire/submit', {
    user_id: userId,
    questionnaire_type: 'manual',
    raw_answers_json: answers,
    extracted_json: {},
    hard_constraints,
    explicit_features: [],
  });
}

export async function getRecommendations(
  userId: number,
  topK: number,
  context: Record<string, string>,
): Promise<F2MScoreResponse> {
  const response = await postJson<any>('/recommendations/score', {
    user_id: userId,
    top_k: topK,
    context,
  });

  const results = Array.isArray(response?.results)
    ? response.results.map((row: any) => ({
      dish_id: String(row?.dish_id ?? ''),
      score: Number(row?.score ?? 0),
    }))
    : [];

  return {
    request_id: String(response?.request_id ?? ''),
    results,
  };
}

export async function logEvent(
  userId: number,
  eventType: string,
  dishId: string | number,
): Promise<{ status: string; event_uuid: string }> {
  return postJson('/events/ingest', {
    source_system: SOURCE_SYSTEM,
    event_uuid: uuidLike(),
    user_id: userId,
    event_type: eventType,
    object_type: 'dish',
    object_id: String(dishId),
    payload_json: {},
  });
}

export async function logOutcome(
  requestId: string,
  dishId: string | number,
  outcome: string,
): Promise<{ status: string }> {
  return postJson(`/recommendations/${encodeURIComponent(requestId)}/outcome`, {
    dish_id: String(dishId),
    outcome,
  });
}