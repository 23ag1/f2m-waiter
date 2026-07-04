export type QuizAnswers = {
  preferences: string[];
  hungerLevel: string;
  drinks: string[];
  allergies: string[];
};

export type HardConstraint = {
  constraint_key: string;
  scope: 'hard';
  source: 'react_quiz';
  reason_text: string;
};

export type QuestionnaireSubmitPayload = {
  questionnaire_type: 'manual';
  raw_answers_json: Record<string, unknown>;
  extracted_json: Record<string, unknown>;
  hard_constraints: HardConstraint[];
  explicit_features: Array<Record<string, unknown>>;
};

function norm(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/[^a-zа-яё0-9_]/gi, '');
}

export function mapQuizToQuestionnaire(quiz: QuizAnswers): QuestionnaireSubmitPayload {
  const allergies = Array.isArray(quiz.allergies) ? quiz.allergies : [];
  const preferences = Array.isArray(quiz.preferences) ? quiz.preferences : [];
  const drinks = Array.isArray(quiz.drinks) ? quiz.drinks : [];

  return {
    questionnaire_type: 'manual',
    raw_answers_json: {
      preferences,
      hungerLevel: quiz.hungerLevel ?? '',
      drinks,
      allergies,
    },
    extracted_json: {},
    hard_constraints: allergies.map((allergy) => ({
      constraint_key: `allergen_${norm(allergy)}`,
      scope: 'hard',
      source: 'react_quiz',
      reason_text: `allergy:${allergy}`,
    })),
    explicit_features: [],
  };
}