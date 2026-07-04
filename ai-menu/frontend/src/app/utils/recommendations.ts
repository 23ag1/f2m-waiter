import { getPersonalizedComment } from './personalization';
import { menuItems } from '../pages/Menu';


interface QuizData {
  favoriteIngredients: string[];
  hatedIngredients: string[];
  hungerLevel: string;
  mood: string;
  name: string;
  drinks?: string[];
}

interface Recommendation {
  id: number;
  name: string;
  category: string;
  image: string;
  reason: string;
}

// Helper function to check if ingredient matches (with fuzzy matching)
const ingredientMatches = (ingredient: string, target: string): boolean => {
  const ing = ingredient.toLowerCase();
  const targ = target.toLowerCase();
  return ing.includes(targ) || targ.includes(ing);
};

// Calculate match score for a dish
const calculateScore = (dish: any, data: QuizData): number => {
  let score = 0;
  
  // Check for allergens (dealbreaker)
  const hasAllergen = dish.allergens.some((allergen: string) =>
    data.hatedIngredients.some(hated => ingredientMatches(allergen, hated))
  );
  if (hasAllergen) return -1000; // Exclude dishes with allergens

  // Check for favorite ingredients (big bonus)
  dish.ingredients.forEach((ingredient: string) => {
    if (data.favoriteIngredients.some(fav => ingredientMatches(ingredient, fav))) {
      score += 10;
    }
  });

  // NEW: Handle preference categories from new quiz format
  data.favoriteIngredients.forEach((pref: string) => {
    const prefLower = pref.toLowerCase();
    
    // Vegetables preference
    if (prefLower.includes('овощ')) {
      if (dish.category === 'salad') score += 8;
    }
    
    // Meat preference
    if (prefLower.includes('мясо')) {
      if (dish.ingredients.some((ing: string) => 
        ing.toLowerCase().includes('мясо') || 
        ing.toLowerCase().includes('говяд') || 
        ing.toLowerCase().includes('свин')
      )) score += 10;
    }
    
    // Chicken is also meat
    if (dish.ingredients.some((ing: string) => ing.toLowerCase().includes('курица'))) {
      if (prefLower.includes('мясо')) score += 8;
    }
    
    // Fish preference
    if (prefLower.includes('рыба')) {
      if (dish.ingredients.some((ing: string) => 
        ing.toLowerCase().includes('рыб') || 
        ing.toLowerCase().includes('лосос')
      )) score += 10;
    }
    
    // Seafood preference
    if (prefLower.includes('морепродукт')) {
      if (dish.ingredients.some((ing: string) => 
        ing.toLowerCase().includes('креветк') || 
        ing.toLowerCase().includes('морепродукт')
      )) score += 10;
    }
    
    // Spicy preference
    if (prefLower.includes('остр')) {
      if (dish.allergens.includes('Острое')) score += 10;
    }
    
    // Sweet preference (desserts)
    if (prefLower.includes('сладк')) {
      if (dish.category === 'dessert') score += 15;
    }
    
    // Soup preference
    if (prefLower.includes('суп')) {
      if (dish.category === 'soup') score += 15;
    }
  });

  // Mood-based scoring
  if (data.mood === 'Грустно' || data.mood === 'Устало') {
    if (dish.category === 'dessert') score += 5;
    if (dish.ingredients.some((ing: string) => ing.includes('Сыр'))) score += 3;
  }
  
  if (data.mood === 'Романтично') {
    if (dish.category === 'main' && dish.price > 400) score += 5;
    if (dish.ingredients.some((ing: string) => ing.includes('Морепродукты') || ing.includes('Креветки'))) score += 4;
  }

  if (data.mood === 'Энергично' || data.mood === 'Счастливо') {
    if (dish.category === 'salad') score += 3;
    if (dish.allergens.includes('Острое')) score += 2;
  }

  // Hunger level scoring
  if (data.hungerLevel === 'Очень голоден') {
    if (dish.category === 'main' || dish.category === 'pasta') score += 5;
    if (dish.price > 380) score += 2; // Bigger portions tend to be pricier
  }

  if (data.hungerLevel === 'Немного голоден') {
    if (dish.category === 'soup' || dish.category === 'salad') score += 5;
  }
  
  // Give drinks a base score so they always appear
  if (dish.category === 'drinks' || dish.category === 'alcohol') {
    score += 3;

    if (data.drinks && data.drinks.length > 0) {
      data.drinks.forEach((drinkPref: string) => {
        const prefLower = drinkPref.toLowerCase();
        if (prefLower.includes('тепл') && dish.temperature === 'hot') score += 12;
        if (prefLower.includes('холодн') && dish.temperature === 'cold') score += 12;
        if (prefLower.includes('алкогол') && dish.category === 'alcohol') score += 12;
      });
    }
  }

  return score;
};

function generateRecommendations(data: QuizData): Recommendation[] {
  try {
    // Validate input data
    if (!data) {
      console.error('No data provided to generateRecommendations');
      return [];
    }

    // Ensure arrays exist
    const safeData = {
      ...data,
      favoriteIngredients: Array.isArray(data.favoriteIngredients) ? data.favoriteIngredients : [],
      hatedIngredients: Array.isArray(data.hatedIngredients) ? data.hatedIngredients : [],
    };

    const scored = menuItems.map(dish => ({
      ...dish,
      score: calculateScore(dish, safeData),
    })).filter(dish => dish.score > -1000); // Remove dishes with allergens

    // Sort all dishes by score
    scored.sort((a, b) => b.score - a.score);

    const recommendations: Recommendation[] = [];
    
    // Analyze user preferences to determine what categories to prioritize
    const prefLower = safeData.favoriteIngredients.map(p => p.toLowerCase());
    const wantsSweets = prefLower.some(p => p.includes('сладк'));
    const wantsVegetables = prefLower.some(p => p.includes('овощ'));
    const wantsSoup = prefLower.some(p => p.includes('суп'));
    const wantsMeat = prefLower.some(p => p.includes('мясо'));
    const wantsFish = prefLower.some(p => p.includes('рыба'));
    const wantsSeafood = prefLower.some(p => p.includes('морепродукт'));
    const wantsSpicy = prefLower.some(p => p.includes('остр'));
    
    const hasDrinkPreferences = safeData.drinks && safeData.drinks.length > 0;

    // Category display order for final sorting
    const categoryOrder = ['salad', 'soup', 'main', 'pasta', 'dessert', 'drinks', 'alcohol'];

    // Helper to add top-1 dish from a filtered set, avoiding duplicates
    const addTop1 = (filtered: any[]) => {
      const dish = filtered.find(d => !recommendations.some(r => r.id === d.id));
      if (dish) recommendations.push(createRecommendation(dish, safeData));
    };

    // One recommendation per preference
    if (wantsVegetables) {
      const salads = scored.filter(d => d.category === 'salad');
      addTop1(salads.length > 0 ? salads : scored.filter(d => d.category === 'soup'));
    }

    if (wantsSoup) {
      addTop1(scored.filter(d => d.category === 'soup'));
    }

    if (wantsFish) {
      const fishDishes = scored.filter(d =>
        d.ingredients.some((ing: string) =>
          ing.toLowerCase().includes('рыб') || ing.toLowerCase().includes('лосос')
        )
      );
      addTop1(fishDishes.length > 0 ? fishDishes : scored.filter(d =>
        d.ingredients.some((ing: string) =>
          ing.toLowerCase().includes('креветк') || ing.toLowerCase().includes('морепродукт')
        )
      ));
    }

    if (wantsSeafood) {
      const seafoodDishes = scored.filter(d =>
        d.ingredients.some((ing: string) =>
          ing.toLowerCase().includes('креветк') || ing.toLowerCase().includes('морепродукт')
        )
      );
      addTop1(seafoodDishes.length > 0 ? seafoodDishes : scored.filter(d =>
        d.ingredients.some((ing: string) =>
          ing.toLowerCase().includes('рыб') || ing.toLowerCase().includes('лосос')
        )
      ));
    }

    if (wantsMeat) {
      const meatDishes = scored.filter(d =>
        d.ingredients.some((ing: string) =>
          ing.toLowerCase().includes('мясо') ||
          ing.toLowerCase().includes('говяд') ||
          ing.toLowerCase().includes('свин') ||
          ing.toLowerCase().includes('бекон')
        )
      );
      addTop1(meatDishes.length > 0 ? meatDishes : scored.filter(d =>
        d.ingredients.some((ing: string) => ing.toLowerCase().includes('курица'))
      ));
    }

    if (wantsSpicy) {
      const spicyDishes = scored.filter(d => d.allergens.includes('Острое'));
      addTop1(spicyDishes.length > 0 ? spicyDishes : scored.filter(d => d.category === 'main'));
    }

    if (wantsSweets) {
      addTop1(scored.filter(d => d.category === 'dessert'));
    }

    if (hasDrinkPreferences) {
      const wantsHot = safeData.drinks.some((d: string) => d.toLowerCase().includes('тепл'));
      const wantsCold = safeData.drinks.some((d: string) => d.toLowerCase().includes('холодн'));
      const wantsAlcohol = safeData.drinks.some((d: string) => d.toLowerCase().includes('алкогол'));

      if (wantsAlcohol) {
        addTop1(scored.filter(d => d.category === 'alcohol'));
      } else if (wantsHot) {
        addTop1(scored.filter(d => d.category === 'drinks' && d.temperature === 'hot'));
      } else if (wantsCold) {
        addTop1(scored.filter(d => d.category === 'drinks' && d.temperature === 'cold'));
      } else {
        addTop1(scored.filter(d => d.category === 'drinks'));
      }
    }

    // If no specific preferences, use balanced approach (1 per category)
    if (recommendations.length === 0) {
      const categories = ['salad', 'soup', 'main', 'dessert', 'drinks'];
      categories.forEach(key => {
        const topDish = scored.find(d => d.category === key);
        if (topDish) recommendations.push(createRecommendation(topDish, safeData));
      });
    }

    // Sort by category display order and remove duplicates
    const unique = recommendations.filter((rec, index, self) =>
      index === self.findIndex((r) => r.id === rec.id)
    );
    unique.sort((a, b) => {
      const ai = categoryOrder.indexOf(a.category);
      const bi = categoryOrder.indexOf(b.category);
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    });
    return unique;
  } catch (error) {
    console.error('Error in generateRecommendations:', error);
    return [];
  }
}

// Helper function to create a recommendation object
function createRecommendation(dish: any, safeData: any): Recommendation {
  let personalizedComment = 'Отличный выбор!';
  try {
    if (typeof getPersonalizedComment === 'function') {
      personalizedComment = getPersonalizedComment(dish, {
        favoriteIngredients: safeData.favoriteIngredients,
        hatedIngredients: safeData.hatedIngredients,
        hungerLevel: safeData.hungerLevel,
        mood: safeData.mood,
        name: safeData.name,
      });
    }
  } catch (commentError) {
    console.error('Error getting personalized comment:', commentError);
  }
  
  return {
    id: dish.id,
    name: dish.name,
    category: dish.category,
    image: dish.image,
    reason: personalizedComment,
  };
}

function getReplacementDish(
  category: string,
  excludeIds: number[],
  data: QuizData,
): { id: number; name: string; category: string; image: string; reason: string } | null {
  const safeData = {
    ...data,
    favoriteIngredients: Array.isArray(data.favoriteIngredients) ? data.favoriteIngredients : [],
    hatedIngredients: Array.isArray(data.hatedIngredients) ? data.hatedIngredients : [],
  };

  const candidates = menuItems
    .filter(d => d.category === category && !excludeIds.includes(d.id))
    .map(d => ({ ...d, score: calculateScore(d, safeData) }))
    .filter(d => d.score > -1000)
    .sort((a, b) => b.score - a.score);

  if (candidates.length === 0) return null;
  const dish = candidates[0];
  return { id: dish.id, name: dish.name, category: dish.category, image: dish.image, reason: 'Альтернативный вариант' };
}

export { generateRecommendations, getReplacementDish };
export default generateRecommendations;