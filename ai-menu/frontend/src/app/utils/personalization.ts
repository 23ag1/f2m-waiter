interface MenuItem {
  id: number;
  name: string;
  price: number;
  weight: string;
  category: string;
  image: string;
  description?: string;
  emoji?: string | null;
  ingredients: string[];
  allergens: string[];
}

interface Preferences {
  phoneNumber?: string;
  name?: string;
  birthday?: string;
  preferences?: string[];
  hungerLevel?: string;
  drinks?: string[];
}

// Predefined ingredient options from quiz
const predefinedFavorites = ['Креветки', 'Сыр', 'Грибы', 'Томаты', 'Курица', 'Рис', 'Паста', 'Морепродукты'];
const predefinedHated = ['Лактоза', 'Глютен', 'Орехи', 'Грибы', 'Мясо', 'Рыба', 'Морепродукты', 'Острое'];

// Generate personalized AI comment
export const getPersonalizedComment = (item: MenuItem, preferences?: Preferences | null): string => {
  // Ensure item has required properties
  if (!item || !item.ingredients || !item.allergens) {
    return 'Прекрасное блюдо из нашего меню!';
  }

  if (!preferences) {
    const ingredientsText = item.ingredients.length > 0 
      ? `с ${item.ingredients.slice(0, 2).join(' и ').toLowerCase()}` 
      : '';
    const descriptionFirst = item.description ? item.description.split('.')[0] : 'вкусное блюдо';
    return `Это ${item.category === 'dessert' ? 'восхитительный десерт' : 'прекрасное блюдо'} ${ingredientsText}. ${descriptionFirst}.`.trim();
  }

  const preferenceMatches: string[] = [];

  // Safely get preference array
  const userPreferences = preferences?.preferences || [];

  // Find all matching preferences
  userPreferences.forEach(pref => {
    if (!pref) return;
    const prefLower = pref.toLowerCase();
    
    let hasMatch = false;
    
    // Map preference categories to item properties
    if (prefLower.includes('овощ')) {
      hasMatch = item.category === 'salad' || 
                 item.ingredients.some(ing => 
                   ing.toLowerCase().includes('овощ') || 
                   ing.toLowerCase().includes('томат') ||
                   ing.toLowerCase().includes('салат')
                 );
    } else if (prefLower.includes('мясо')) {
      hasMatch = item.ingredients.some(ing => 
        ing.toLowerCase().includes('мясо') ||
        ing.toLowerCase().includes('курица') ||
        ing.toLowerCase().includes('говяд')
      );
    } else if (prefLower.includes('рыба')) {
      hasMatch = item.ingredients.some(ing => 
        ing.toLowerCase().includes('рыб') ||
        ing.toLowerCase().includes('лосос')
      );
    } else if (prefLower.includes('морепродукт')) {
      hasMatch = item.ingredients.some(ing => 
        ing.toLowerCase().includes('креветк') ||
        ing.toLowerCase().includes('морепродукт')
      );
    } else if (prefLower.includes('остр')) {
      hasMatch = item.allergens.some(all => all.toLowerCase().includes('остр'));
    } else if (prefLower.includes('сладк')) {
      hasMatch = item.category === 'dessert';
    } else if (prefLower.includes('суп')) {
      hasMatch = item.category === 'soup';
    }
    
    if (hasMatch) {
      preferenceMatches.push(pref);
    }
  });

  // Generate comment based on matches
  if (preferenceMatches.length > 0) {
    // Matches user preferences - sell the dish!
    const dishType = item.category === 'main' ? 'блюдо' : 
                     item.category === 'dessert' ? 'десерт' :
                     item.category === 'soup' ? 'суп' :
                     item.category === 'salad' ? 'салат' : 
                     item.category === 'pasta' ? 'паста' : 'блюдо';
    
    if (preferenceMatches.length === 1) {
      return `Отличный выбор! Это ${dishType} идеально подходит под ваше предпочтение "${preferenceMatches[0]}". Рекомендуем попробовать!`;
    } else {
      return `Специально для вас! Это ${dishType} соответствует вашим предпочтениям: ${preferenceMatches.join(', ')}. Настоятельно рекомендуем!`;
    }
  } else {
    // No matches - general recommendation
    const ingredientsText = item.ingredients.length > 0 
      ? `с ${item.ingredients.slice(0, 2).join(' и ').toLowerCase()}` 
      : '';
    const descriptionFirst = item.description ? item.description.split('.')[0] : 'вкусное блюдо';
    return `Это ${item.category === 'dessert' ? 'восхитительный десерт' : 'прекрасное блюдо'} ${ingredientsText}. ${descriptionFirst}.`.trim();
  }
};

export default getPersonalizedComment;