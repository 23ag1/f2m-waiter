import { useState } from 'react';
import { useNavigate } from 'react-router';
import { type LucideIcon, Shell, Drumstick, Flame, Fish, Nut, Pizza, Wheat, Heart, Milk, Cookie, ShoppingBag } from 'lucide-react';
import MenuItem from '../components/MenuItem';
import MenuDetail from '../components/MenuDetail';
import ChatBot from '../components/ChatBot';
import { usePreferences } from '../context/PreferencesContext';
import { useBasket } from '../context/BasketContext';
import { getPersonalizedComment } from '../utils/personalization';

// Predefined ingredient options from quiz
const predefinedFavorites = ['Креветки', 'Сыр', 'Грибы', 'Томаты', 'Курица', 'Рис', 'Паста', 'Морепродукты'];
const predefinedHated = ['Лактоза', 'Глютен', 'Орехи', 'Грибы', 'Мясо', 'Рыба', 'Морепродукты', 'Острое'];

// Allergen icon mapping
const allergenIcons: Record<string, LucideIcon> = {
  'Лактоза': Milk,
  'Глютен': Wheat,
  'Морепродукты': Shell,
  'Мясо': Drumstick,
  'Острое': Flame,
  'Рыба': Fish,
  'Орехи': Nut,
};

// Ingredient icon mapping for favorites
const ingredientIcons: Record<string, LucideIcon> = {
  'Креветки': Shell,
  'Томаты': Flame,
  'Паста': Wheat,
  'Рикотта': Pizza,
  'Ягоды': Heart,
  'Мясо': Drumstick,
  'Рис': Wheat,
  'Курица': Drumstick,
  'Морепродукты': Shell,
  'Бекон': Drumstick,
  'Рыба': Fish,
  'Орехи': Nut,
  'Сыр': Pizza,
  'Грибы': Nut,
};

export const menuItems = [
  {
    id: 1,
    name: 'Спагетти Неро с креветками в томатном соусе',
    price: 339,
    weight: '250 г',
    category: 'main',
    image: '/menu_id_1.png',
    description: 'Угольно-чёрные спагетти, окрашенные чернилами каракатицы, в ярком томатном соусе из помидоров черри. Состав: паста неро, тигровые креветки, томаты черри, каперсы, чеснок, оливковое масло, пармезан, свежий базилик.',
    emoji: '🥰',
    ingredients: ['Креветки', 'Томаты', 'Паста'],
    allergens: ['Морепродукты', 'Глютен'],
  },
  {
    id: 4,
    name: 'Курица в азиатском соусе',
    price: 339,
    weight: '250 г',
    category: 'main',
    image: '/menu_id_4.png',
    description: 'Нежное куриное филе, обжаренное с хрустящими овощами в насыщенном азиатском соусе. Состав: куриное филе, брокколи, болгарский перец, морковь, соевый соус, имбирь, чеснок, кунжут, рис на гарнир.',
    emoji: null,
    ingredients: ['Курица'],
    allergens: ['Глютен'],
  },
  {
    id: 5,
    name: 'Томатный суп с морепродуктами',
    price: 339,
    weight: '250 г',
    category: 'soup',
    image: '/menu_id_5.jpeg',
    description: 'Насыщенный томатный суп на морском бульоне с ассорти из морепродуктов. Состав: томаты, мидии, кальмары, креветки, чеснок, лук, оливковое масло, базилик, тимьян.',
    emoji: null,
    ingredients: ['Томаты', 'Морепродукты'],
    allergens: ['Морепродукты'],
  },
  {
    id: 6,
    name: 'Крем-суп из чечевицы с беконом',
    price: 339,
    weight: '250 г',
    category: 'soup',
    image: '/menu_id_6.png',
    description: 'Бархатистый крем-суп из красной чечевицы с хрустящим беконом. Состав: красная чечевица, бекон, морковь, лук, сельдерей, сливки, чеснок, тмин, оливковое масло.',
    emoji: null,
    ingredients: ['Бекон'],
    allergens: ['Лактоза'],
  },
  {
    id: 7,
    name: 'Паста Карбонара',
    price: 389,
    weight: '280 г',
    category: 'pasta',
    image: '/menu_id_7.png',
    description: 'Классическая итальянская паста в сливочно-яичном соусе с беконом. Состав: паста спагетти, гуанчале (бекон), яичный желток, сыр пармезан, сыр пекорино, чёрный перец.',
    emoji: null,
    ingredients: ['Паста', 'Сыр', 'Бекон'],
    allergens: ['Глютен', 'Лактоза'],
  },
  {
    id: 8,
    name: 'Феттучини с грибами в сливочном соусе',
    price: 369,
    weight: '270 г',
    category: 'pasta',
    image: '/menu_id_8.png',
    description: 'Нежная феттучини в сливочном соусе с лесными грибами и пармезаном. Состав: паста феттучини, белые грибы, шампиньоны, сливки, чеснок, пармезан, тимьян, сливочное масло.',
    emoji: null,
    ingredients: ['Паста', 'Грибы', 'Сыр'],
    allergens: ['Глютен', 'Лактоза', 'Грибы'],
  },
  {
    id: 9,
    name: 'Пенне Аррабьята',
    price: 329,
    weight: '250 г',
    category: 'pasta',
    image: '/menu_id_9.png',
    description: 'Острая паста в томатном соусе для настоящих любителей пикантного. Состав: паста пенне, томаты, чеснок, перец чили, оливковое масло, базилик, пекорино.',
    emoji: null,
    ingredients: ['Паста', 'Томаты'],
    allergens: ['Глютен', 'Острое'],
  },
  {
    id: 10,
    name: 'Ризотто с морепродуктами',
    price: 429,
    weight: '280 г',
    category: 'main',
    image: '/menu_id_10.png',
    description: 'Кремовое ризотто с ассорти из свежих морепродуктов. Состав: рис арборио, креветки, мидии, кальмары, белое вино, лук-шалот, пармезан, сливочное масло, петрушка.',
    emoji: null,
    ingredients: ['Рис', 'Морепродукты', 'Креветки'],
    allergens: ['Морепродукты', 'Лактоза'],
  },
  {
    id: 11,
    name: 'Стейк из лосося на гриле',
    price: 459,
    weight: '200 г',
    category: 'main',
    image: '/menu_id_11.png',
    description: 'Сочный стейк из норвежского лосося на гриле с лимонным маслом. Состав: филе лосося, спаржа, помидоры черри, картофель, шпинат, лимонное масло, укроп, морская соль.',
    emoji: null,
    ingredients: ['Рыба'],
    allergens: ['Рыба'],
  },
  {
    id: 12,
    name: 'Грибной крем-суп',
    price: 299,
    weight: '300 г',
    category: 'soup',
    image: '/menu_id_12.png',
    description: 'Бархатистый крем-суп из белых грибов с трюфельным маслом. Состав: белые грибы, сливки, лук-шалот, чеснок, куриный бульон, трюфельное масло, тимьян, пармезан.',
    emoji: null,
    ingredients: ['Грибы'],
    allergens: ['Грибы', 'Лактоза'],
  },
  {
    id: 13,
    name: 'Том Ям с креветками',
    price: 379,
    weight: '350 г',
    category: 'soup',
    image: '/menu_id_13.png',
    description: 'Пряный тайский суп на кокосовом бульоне с тигровыми креветками. Состав: креветки, грибы шиитаке, лемонграсс, кафир-лайм, галангал, кокосовое молоко, рыбный соус, перец чили.',
    emoji: null,
    ingredients: ['Креветки', 'Грибы', 'Морепродукты'],
    allergens: ['Морепродукты', 'Острое', 'Грибы'],
  },
  {
    id: 14,
    name: 'Тирамису классический',
    price: 319,
    weight: '150 г',
    category: 'dessert',
    image: '/menu_id_14.png',
    description: 'Классический итальянский десерт на основе маскарпоне и кофе. Состав: печенье савоярди, маскарпоне, яйца, сахар, эспрессо, амаретто, какао-порошок.',
    emoji: null,
    ingredients: ['Сыр'],
    allergens: ['Лактоза', 'Глютен'],
  },
  {
    id: 15,
    name: 'Чизкейк Нью-Йорк',
    price: 339,
    weight: '180 г',
    category: 'dessert',
    image: '/menu_id_15.png',
    description: 'Классический нью-йоркский чизкейк с нежной кремовой текстурой. Состав: сыр сливочный, сметана, яйца, сахар, ваниль, печенье, сливочное масло.',
    emoji: null,
    ingredients: ['Сыр'],
    allergens: ['Лактоза', 'Глютен'],
  },
  {
    id: 16,
    name: 'Панна-котта с ягодным соусом',
    price: 289,
    weight: '140 г',
    category: 'dessert',
    image: '/menu_id_16.png',
    description: 'Нежный итальянский десерт из сливок с ванилью и ягодным соусом. Состав: сливки, сахар, ваниль, желатин, соус из клубники, малины и черники.',
    emoji: null,
    ingredients: [],
    allergens: ['Лактоа'],
  },
  {
    id: 17,
    name: 'Эспрессо',
    price: 129,
    weight: '30 мл',
    category: 'drinks',
    image: '/menu_id_17.png',
    description: 'Крепкий эспрессо с насыщенным вкусом и золотистой крема. Состав: 100% арабика, двойная порция, 30 мл. Подаётся с долькой тёмного шоколада.',
    emoji: null,
    ingredients: [],
    allergens: [],
  },
  {
    id: 18,
    name: 'Капучино',
    price: 179,
    weight: '250 мл',
    category: 'drinks',
    temperature: 'hot',
    image: '/menu_id_18.png',
    description: 'Классический капучино с воздушной молочной пенкой и рисунком. Состав: двойной эспрессо, вспененное молоко 3.2%, 250 мл. Можно заказать на растительном молоке.',
    emoji: null,
    ingredients: [],
    allergens: ['Лактоза'],
  },
  {
    id: 19,
    name: 'Латте',
    price: 189,
    weight: '300 мл',
    category: 'drinks',
    temperature: 'hot',
    image: '/menu_id_19.png',
    description: 'Нежный латте с большим количеством молока и тонким слоем пенки. Состав: двойной эспрессо, горячее молоко 3.2%, молочная пенка, 300 мл.',
    emoji: null,
    ingredients: [],
    allergens: ['Лактоза'],
  },
  {
    id: 20,
    name: 'Апельсиновый фреш',
    price: 199,
    weight: '250 мл',
    category: 'drinks',
    temperature: 'cold',
    image: '/menu_id_20.png',
    description: 'Свежевыжатый сок из спелых апельсинов, богатый витамином C. Состав: апельсины сорта Валенсия, без сахара и консервантов, 250 мл.',
    emoji: null,
    ingredients: [],
    allergens: [],
  },
  {
    id: 21,
    name: 'Лимонад домашний',
    price: 169,
    weight: '300 мл',
    category: 'drinks',
    temperature: 'cold',
    image: '/menu_id_21.png',
    description: 'Освежающий домашний лимонад по фирменному рецепту. Состав: лимонный сок, мята, тростниковый сахар, газированная вода, 300 мл.',
    emoji: null,
    ingredients: [],
    allergens: [],
  },
  {
    id: 22,
    name: 'Смузи ягодный',
    price: 219,
    weight: '300 мл',
    category: 'drinks',
    temperature: 'cold',
    image: '/menu_id_22.png',
    description: 'Густой ягодный смузи без добавления сахара. Состав: клубника, малина, черника, банан, йогурт, 300 мл.',
    emoji: null,
    ingredients: [],
    allergens: [],
  },
  {
    id: 23,
    name: 'Чай зеленый',
    price: 119,
    weight: '300 мл',
    category: 'drinks',
    temperature: 'hot',
    image: '/menu_id_23.png',
    description: 'Ароматный зелёный чай с лёгкими травяными нотами. Состав: листовой зелёный чай сенча, 300 мл. Подаётся с мёдом.',
    emoji: null,
    ingredients: [],
    allergens: [],
  },
  {
    id: 24,
    name: 'Цезарь с курицей',
    price: 359,
    weight: '280 г',
    category: 'salad',
    image: '/menu_id_24.png',
    description: 'Классический салат Цезарь с сочной куриной грудкой. Состав: куриное филе гриль, листья романо, сухарики, пармезан, соус цезарь (анчоусы, лимон, чеснок, оливковое масло).',
    emoji: null,
    ingredients: ['Курица', 'Сыр'],
    allergens: ['Глютен', 'Лактоза'],
  },
  {
    id: 25,
    name: 'Греческий салат',
    price: 329,
    weight: '260 г',
    category: 'salad',
    image: '/menu_id_25.png',
    description: 'Свежий греческий салат с сыром фета и оливками. Состав: огурцы, томаты, болгарский перец, красный лук, оливки каламата, сыр фета, оливковое масло, орегано.',
    emoji: null,
    ingredients: ['Томаты', 'Сыр', 'Овощи'],
    allergens: ['Лактоза'],
  },
  {
    id: 26,
    name: 'Салат с креветками и авокадо',
    price: 399,
    weight: '240 г',
    category: 'salad',
    image: '/menu_id_26.png',
    description: 'Лёгкий салат с тигровыми креветками и авокадо. Состав: тигровые креветки, авокадо, микс-салат, огурец, редис, лимонная заправка, кунжутное масло.',
    emoji: null,
    ingredients: ['Креветки', 'Морепродукты'],
    allergens: ['Морепродукты'],
  },
  {
    id: 28,
    name: 'Стейк Рибай с картофелем',
    price: 899,
    weight: '350 г',
    category: 'main',
    image: '/menu_id_28.png',
    description: 'Сочный стейк рибай средней прожарки с жареным картофелем. Состав: мраморная говядина рибай 300г, картофель розмариновый, томаты черри, спаржа, болгарский перец, соус демиглас.',
    emoji: null,
    ingredients: ['Мясо'],
    allergens: [],
  },
  // {
  //   id: 29,
  //   name: 'Утиная грудка с апельсиновым соусом',
  //   price: 749,
  //   weight: '280 г',
  //   category: 'main',
  //   image: 'https://images.unsplash.com/photo-1701120006891-87186be6c59c?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080',
  //   description: 'Нежная утиная грудка с карамелизированными апельсинами и медовым соусом.',
  //   emoji: null,
  //   ingredients: ['Мясо'],
  //   allergens: [],
  // },
  {
    id: 30,
    name: 'Боул с тунцом и киноа',
    price: 429,
    weight: '320 г',
    category: 'salad',
    image: '/menu_id_30.png',
    description: 'Питательный боул с обжаренным тунцом и суперфудами. Состав: тунец, киноа, авокадо, эдамаме, огурец, редис, нори, кунжутный соус, имбирь маринованный.',
    emoji: null,
    ingredients: ['Рыба'],
    allergens: ['Рыба', 'Глютен'],
  },
  {
    id: 32,
    name: 'Бургер с говядиной',
    price: 459,
    weight: '320 г',
    category: 'main',
    image: '/menu_id_32.png',
    description: 'Сочный бургер из мраморной говядины с картофелем фри. Состав: котлета из говядины 200г, бриошь-булочка, сыр чеддер, салат айсберг, томат, маринованный огурец, карамелизированный лук, фирменный соус.',
    emoji: null,
    ingredients: ['Мясо', 'Сыр'],
    allergens: ['Глютен', 'Лактоза'],
  },
  {
    id: 33,
    name: 'Пицца Маргарита',
    price: 529,
    weight: '450 г',
    category: 'main',
    image: '/menu_id_33.png',
    description: 'Классическая неаполитанская пицца на тонком хрустящем тесте. Состав: тесто на закваске, томатный соус Сан-Марцано, моцарелла фиор ди латте, свежий базилик, оливковое масло.',
    emoji: null,
    ingredients: ['Томаты', 'Сыр'],
    allergens: ['Глютен', 'Лактоза'],
  },
  {
    id: 34,
    name: 'Пицца с прошутто и рукколой',
    price: 629,
    weight: '480 г',
    category: 'main',
    image: '/menu_id_34.png',
    description: 'Хрустящая пицца с итальянской ветчиной и рукколой. Состав: тесто на закваске, сливочный соус, моцарелла, прошутто крудо, руккола, пармезан, бальзамический крем.',
    emoji: null,
    ingredients: ['Мясо', 'Сыр'],
    allergens: ['Глютен', 'Лактоза'],
  },
  {
    id: 35,
    name: 'Лазанья болоньезе',
    price: 449,
    weight: '350 г',
    category: 'pasta',
    image: '/menu_id_35.png',
    description: 'Традиционная итальянская лазанья с богатым мясным соусом. Состав: листы пасты, говяжий фарш, томатный соус болоньезе, соус бешамель, моцарелла, пармезан.',
    emoji: null,
    ingredients: ['Паста', 'Мясо', 'Сыр'],
    allergens: ['Глютен', 'Лактоза'],
  },
  {
    id: 36,
    name: 'Шоколадный фондан',
    price: 349,
    weight: '130 г',
    category: 'dessert',
    image: '/menu_id_36.png',
    description: 'Тёплый шоколадный кекс с жидкой начинкой. Состав: тёмный шоколад 70%, масло, яйца, сахар, мука. Подаётся с шариком ванильного мороженого и малиновым соусом.',
    emoji: null,
    ingredients: [],
    allergens: ['Глютен', 'Лактоза'],
  },
  {
    id: 37,
    name: 'Медовик классический',
    price: 299,
    weight: '160 г',
    category: 'dessert',
    image: '/menu_id_37.png',
    description: 'Многослойный торт с медовыми коржами и нежным кремом. Состав: медовые коржи, заварной крем, грецкие орехи, чернослив.',
    emoji: null,
    ingredients: [],
    allergens: ['Глютен', 'Лактоза'],
  },
  {
    id: 39,
    name: 'Капрезе салат',
    price: 389,
    weight: '220 г',
    category: 'salad',
    image: '/menu_id_39.png',
    description: 'Классический итальянский салат с томатами и моцареллой. Состав: томаты говяжье сердце, моцарелла буффало, свежий базилик, оливковое масло extra virgin, морская соль, перец.',
    emoji: null,
    ingredients: ['Томаты', 'Сыр'],
    allergens: ['Лактоза'],
  },
  {
    id: 40,
    name: 'Вино красное сухое',
    price: 450,
    weight: '150 мл',
    category: 'alcohol',
    image: '/menu_id_40.png',
    description: 'Бокал красного сухого вина с нотами вишни и тёмных ягод. Состав: виноград Каберне Совиньон, выдержка 12 месяцев, Италия. 150 мл, 13.5% алк.',
    emoji: null,
    ingredients: [],
    allergens: [],
    temperature: 'room',
    isAlcohol: true,
  },
  {
    id: 41,
    name: 'Вино белое сухое',
    price: 430,
    weight: '150 мл',
    category: 'alcohol',
    image: '/menu_id_41.png',
    description: 'Освежающее белое сухое вино с цитрусовыми нотами. Состав: виноград Пино Гриджо, Венето, Италия. 150 мл, 12% алк.',
    emoji: null,
    ingredients: [],
    allergens: [],
    temperature: 'cold',
    isAlcohol: true,
  },
  {
    id: 42,
    name: 'Просекко',
    price: 520,
    weight: '150 мл',
    category: 'alcohol',
    image: '/menu_id_42.png',
    description: 'Лёгкое игристое итальянское вино с фруктовыми нотами. Состав: виноград Глера, Просекко DOC, Италия. 150 мл, 11% алк.',
    emoji: null,
    ingredients: [],
    allergens: [],
    temperature: 'cold',
    isAlcohol: true,
  },
  {
    id: 43,
    name: 'Апероль Шприц',
    price: 390,
    weight: '250 мл',
    category: 'alcohol',
    image: '/menu_id_43.png',
    description: 'Освежающий итальянский аперитив с апельсином. Состав: Апероль, просекко, содовая, долька апельсина, лёд. 250 мл, 8% алк.',
    emoji: null,
    ingredients: [],
    allergens: [],
    temperature: 'cold',
    isAlcohol: true,
  },
  {
    id: 44,
    name: 'Мохито классический',
    price: 350,
    weight: '300 мл',
    category: 'alcohol',
    image: '/menu_id_44.png',
    description: 'Классический кубинский коктейль с ромом и мятой. Состав: белый ром, свежий лайм, листья мяты, тростниковый сахар, содовая, лёд. 300 мл, 10% алк.',
    emoji: null,
    ingredients: [],
    allergens: [],
    temperature: 'cold',
    isAlcohol: true,
  },
  {
    id: 45,
    name: 'Негрони',
    price: 420,
    weight: '100 мл',
    category: 'alcohol',
    image: '/menu_id_45.png',
    description: 'Классический итальянский коктейль с горьковато-сладким вкусом. Состав: джин, Кампари, красный вермут, долька апельсина, лёд. 100 мл, 24% алк.',
    emoji: null,
    ingredients: [],
    allergens: [],
    temperature: 'cold',
    isAlcohol: true,
  },
  {
    id: 46,
    name: 'Пиво светлое',
    price: 280,
    weight: '500 мл',
    category: 'alcohol',
    image: '/menu_id_46.png',
    description: 'Освежающее светлое пиво с лёгким хмелевым ароматом. Состав: вода, ячменный солод, хмель, дрожжи. 500 мл, 4.6% алк.',
    emoji: null,
    ingredients: [],
    allergens: ['Глютен'],
    temperature: 'cold',
    isAlcohol: true,
  },
  {
    id: 47,
    name: 'Пиво темное',
    price: 290,
    weight: '500 мл',
    category: 'alcohol',
    image: '/menu_id_47.png',
    description: 'Тёмное пиво с насыщенным солодовым вкусом и нотами карамели. Состав: вода, тёмный солод, хмель, дрожжи. 500 мл, 5.2% алк.',
    emoji: null,
    ingredients: [],
    allergens: ['Глютен'],
    temperature: 'cold',
    isAlcohol: true,
  },
  {
    id: 48,
    name: 'Виски кола',
    price: 380,
    weight: '250 мл',
    category: 'alcohol',
    image: '/menu_id_48.png',
    description: 'Классическое сочетание выдержанного виски с колой. Состав: виски Jack Daniels, кола, лёд, долька лимона. 250 мл, 8% алк.',
    emoji: null,
    ingredients: [],
    allergens: [],
    temperature: 'cold',
    isAlcohol: true,
  },
  {
    id: 49,
    name: 'Капрезе с буррата',
    price: 459,
    weight: '250 г',
    category: 'salad',
    image: '/menu_id_49.png',
    description: 'Изысканный итальянский салат с кремовой буррата. Состав: буррата 125г, томаты черри, вяленые томаты, базилик, оливковое масло, бальзамический крем, морская соль.',
    emoji: null,
    ingredients: ['Томаты', 'Сыр'],
    allergens: ['Лактоза'],
  },
  {
    id: 50,
    name: 'Рамен с курицей',
    price: 399,
    weight: '400 г',
    category: 'soup',
    image: '/menu_id_50.png',
    description: 'Японский суп с насыщенным бульоном и пшеничной лапшой. Состав: куриный бульон, лапша рамен, куриное филе, варёное яйцо, грибы шиитаке, кукуруза, зелёный лук, нори, кунжутное масло.',
    emoji: null,
    ingredients: ['Курица', 'Паста', 'Грибы'],
    allergens: ['Глютен', 'Грибы'],
  },
];

export const menuCalories: Record<number, number> = {
  1: 520, 4: 380, 5: 180, 6: 230, 7: 620, 8: 560,
  9: 430, 10: 580, 11: 320, 12: 190, 13: 210, 14: 340, 15: 390,
  16: 250, 17: 5, 18: 80, 19: 110, 20: 90, 21: 70, 22: 140, 23: 5,
  24: 320, 25: 210, 26: 280, 28: 750, 30: 350,
  32: 680, 33: 850, 34: 900, 35: 640, 36: 450, 37: 380,
  39: 220, 40: 130, 41: 120, 42: 115, 43: 180, 44: 160, 45: 190,
  46: 200, 47: 220, 48: 230, 49: 240, 50: 420,
};

const categories = [
  { id: 'main', name: 'Основное' },
  { id: 'pasta', name: 'Паста' },
  { id: 'soup', name: 'Супы' },
  { id: 'salad', name: 'Салаты' },
  { id: 'dessert', name: 'Десерты' },
  { id: 'drinks', name: 'Напитки' },
  { id: 'alcohol', name: 'Алкоголь' },
];

export default function Menu() {
  const [activeCategory, setActiveCategory] = useState('main');
  const [selectedItem, setSelectedItem] = useState<typeof menuItems[0] | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const { preferences } = usePreferences();
  const { getTotalItems, addItem, updateQuantity, items: basketItems } = useBasket();
  const navigate = useNavigate();

  // Calculate relevance score for sorting
  const calculateRelevanceScore = (item: typeof menuItems[0]) => {
    let score = 0;

    if (!preferences?.preferences || preferences.preferences.length === 0) {
      return 0; // No sorting if no preferences
    }

    // Check if dish matches user preferences
    preferences.preferences.forEach(pref => {
      const prefLower = pref.toLowerCase();
      
      // Vegetables preference
      if (prefLower.includes('овощ')) {
        if (item.category === 'salad') score += 20;
        if (item.ingredients.some(ing => 
          ing.toLowerCase().includes('овощ') || 
          ing.toLowerCase().includes('томат') ||
          ing.toLowerCase().includes('огур') ||
          ing.toLowerCase().includes('салат')
        )) score += 10;
      }
      
      // Meat preference
      if (prefLower.includes('мясо')) {
        if (item.ingredients.some(ing => 
          ing.toLowerCase().includes('мясо') || 
          ing.toLowerCase().includes('говяд') || 
          ing.toLowerCase().includes('свин') ||
          ing.toLowerCase().includes('курица') ||
          ing.toLowerCase().includes('бекон')
        )) score += 25;
      }
      
      // Fish preference
      if (prefLower.includes('рыба')) {
        if (item.ingredients.some(ing => 
          ing.toLowerCase().includes('рыб') || 
          ing.toLowerCase().includes('лосос') ||
          ing.toLowerCase().includes('тунец')
        )) score += 25;
      }
      
      // Seafood preference
      if (prefLower.includes('морепродукт')) {
        if (item.ingredients.some(ing => 
          ing.toLowerCase().includes('креветк') || 
          ing.toLowerCase().includes('морепродукт') ||
          ing.toLowerCase().includes('мидии') ||
          ing.toLowerCase().includes('кальмар')
        )) score += 25;
      }
      
      // Spicy preference
      if (prefLower.includes('остр')) {
        if (item.description.toLowerCase().includes('остр') ||
            item.ingredients.some(ing => ing.toLowerCase().includes('остр')) ||
            item.allergens.some(all => all.toLowerCase().includes('остр'))) {
          score += 25;
        }
      }
      
      // Sweet preference (desserts)
      if (prefLower.includes('сладк')) {
        if (item.category === 'dessert') score += 30;
      }
      
      // Soup preference
      if (prefLower.includes('суп')) {
        if (item.category === 'soup') score += 30;
      }
    });

    // Hunger level bonus
    if (preferences.hungerLevel === 'Очень голоден' || preferences.hungerLevel === 'Голоден') {
      if (item.category === 'main' || item.category === 'pasta') score += 10;
      const cal = menuCalories[item.id] ?? 0;
      if (cal > 500) score += 8;
    }

    if (preferences.hungerLevel === 'Хочу перекусить' || preferences.hungerLevel === 'Совсем не голоден') {
      if (item.category === 'soup' || item.category === 'salad') score += 10;
      const cal = menuCalories[item.id] ?? 999;
      if (cal < 300) score += 8;
    }

    // Drink preferences
    if (preferences.drinks && preferences.drinks.length > 0) {
      preferences.drinks.forEach(drink => {
        const drinkLower = drink.toLowerCase();
        if (item.category === 'drinks') {
          if (drinkLower.includes('тепл') && 
              (item.name.toLowerCase().includes('кофе') || 
               item.name.toLowerCase().includes('капучино') ||
               item.name.toLowerCase().includes('латте'))) {
            score += 20;
          }
          if (drinkLower.includes('холодн') && 
              (item.name.toLowerCase().includes('фреш') || 
               item.name.toLowerCase().includes('смузи') ||
               item.name.toLowerCase().includes('сок'))) {
            score += 20;
          }
        }
      });
    }

    return score;
  };

  // Generate personalized tags based on preferences
  const getPersonalizedTags = (item: typeof menuItems[0]) => {
    const tags: Array<{ text: string; color: string }> = [];

    // Check if dish matches user preferences - GREEN TAG
    const prefTagLabels: Record<string, string> = {
      'овощ': 'Много овощей',
      'мясо': 'Мясо',
      'рыба': 'Рыба',
      'морепродукт': 'Морепродукты',
      'остр': 'Острое',
      'сладк': 'Десерт',
      'суп': 'Суп',
    };

    const matchedPref = preferences?.preferences?.find(pref => {
      const prefLower = pref.toLowerCase();

      if (prefLower.includes('овощ')) {
        return item.category === 'salad' ||
               item.ingredients.some(ing =>
                 ing.toLowerCase().includes('овощ') ||
                 ing.toLowerCase().includes('томат') ||
                 ing.toLowerCase().includes('огур') ||
                 ing.toLowerCase().includes('салат')
               );
      }
      if (prefLower.includes('мясо')) {
        return item.ingredients.some(ing =>
          ing.toLowerCase().includes('мясо') ||
          ing.toLowerCase().includes('говяд') ||
          ing.toLowerCase().includes('свин') ||
          ing.toLowerCase().includes('курица') ||
          ing.toLowerCase().includes('бекон')
        );
      }
      if (prefLower.includes('рыба')) {
        return item.ingredients.some(ing =>
          ing.toLowerCase().includes('рыб') ||
          ing.toLowerCase().includes('лосос') ||
          ing.toLowerCase().includes('тунец')
        );
      }
      if (prefLower.includes('морепродукт')) {
        return item.ingredients.some(ing =>
          ing.toLowerCase().includes('креветк') ||
          ing.toLowerCase().includes('морепродукт') ||
          ing.toLowerCase().includes('мидии') ||
          ing.toLowerCase().includes('кальмар')
        );
      }
      if (prefLower.includes('остр')) {
        return item.description.toLowerCase().includes('остр') ||
               item.ingredients.some(ing => ing.toLowerCase().includes('остр')) ||
               item.allergens.some(all => all.toLowerCase().includes('остр'));
      }
      if (prefLower.includes('сладк')) {
        return item.category === 'dessert';
      }
      if (prefLower.includes('суп')) {
        return item.category === 'soup';
      }
      return item.description.toLowerCase().includes(prefLower);
    });

    if (matchedPref) {
      const key = Object.keys(prefTagLabels).find(k => matchedPref.toLowerCase().includes(k));
      const tagText = key ? prefTagLabels[key] : matchedPref;
      tags.push({ text: tagText, color: 'green' });
    }

    const cal = menuCalories[item.id] ?? 0;
    const weightNum = parseInt(item.weight);

    // Calorie-based tags
    if (cal > 0 && cal < 300 && item.category !== 'drinks' && item.category !== 'alcohol') {
      tags.push({ text: 'Некалорийно', color: 'blue' });
    }

    if (cal >= 600 && (preferences?.hungerLevel === 'Очень голоден' || preferences?.hungerLevel === 'Голоден')) {
      tags.push({ text: 'Сытное блюдо', color: 'orange' });
    }

    // Large portion tag
    if (!isNaN(weightNum) && weightNum >= 350) {
      tags.push({ text: 'Большая порция', color: 'purple' });
    }

    return tags;
  };

  // Get icon to display on the image
  const getDisplayIcon = (item: typeof menuItems[0]) => {
    // Check if dish matches user's preferences and show GREEN icon
    const matchedPreference = preferences?.preferences?.find(pref => {
      const prefLower = pref.toLowerCase();
      
      // Map preference categories to item properties
      if (prefLower.includes('овощ')) {
        return item.category === 'salad' || 
               item.ingredients.some(ing => 
                 ing.toLowerCase().includes('овощ') || 
                 ing.toLowerCase().includes('томат') ||
                 ing.toLowerCase().includes('огур')
               );
      }
      
      if (prefLower.includes('мясо')) {
        return item.ingredients.some(ing => 
          ing.toLowerCase().includes('мясо') ||
          ing.toLowerCase().includes('говяд') ||
          ing.toLowerCase().includes('курица') ||
          ing.toLowerCase().includes('бекон')
        );
      }
      
      if (prefLower.includes('рыба')) {
        return item.ingredients.some(ing => 
          ing.toLowerCase().includes('рыб') ||
          ing.toLowerCase().includes('лосос')
        );
      }
      
      if (prefLower.includes('морепродукт')) {
        return item.ingredients.some(ing => 
          ing.toLowerCase().includes('креветк') ||
          ing.toLowerCase().includes('морепродукт')
        );
      }
      
      if (prefLower.includes('остр')) {
        return item.allergens.some(all => all.toLowerCase().includes('остр'));
      }
      
      if (prefLower.includes('сладк')) {
        return item.category === 'dessert';
      }
      
      if (prefLower.includes('суп')) {
        return item.category === 'soup';
      }
      
      return false;
    });

    if (matchedPreference) {
      const prefLower = matchedPreference.toLowerCase();
      
      // Map preferences to icons
      if (prefLower.includes('мясо')) {
        return { icon: Drumstick, color: 'green' };
      }
      if (prefLower.includes('рыба')) {
        return { icon: Fish, color: 'green' };
      }
      if (prefLower.includes('морепродукт')) {
        return { icon: Shell, color: 'green' };
      }
      if (prefLower.includes('остр')) {
        return { icon: Flame, color: 'green' };
      }
      if (prefLower.includes('сладк')) {
        return { icon: Cookie, color: 'green' };
      }
      if (prefLower.includes('овощ')) {
        return { icon: Heart, color: 'green' };
      }
      
      // Default green heart for matched preferences
      return { icon: Heart, color: 'green' };
    }

    return null;
  };

  const filteredItems = menuItems
    .filter(item => item.category === activeCategory)
    .map(item => ({
      ...item,
      relevanceScore: calculateRelevanceScore(item)
    }))
    .sort((a, b) => b.relevanceScore - a.relevanceScore); // Sort by relevance (highest first)

  if (isChatOpen) {
    return (
      <ChatBot
        isFullPage={true}
        onClose={() => setIsChatOpen(false)}
        onRecommendationClick={(dishId) => {
          const dish = menuItems.find(item => item.id === dishId);
          if (dish) {
            setIsChatOpen(false);
            setSelectedItem(dish);
          }
        }}
      />
    );
  }

  if (selectedItem) {
    return (
      <MenuDetail
        item={selectedItem}
        tags={getPersonalizedTags(selectedItem)}
        displayIcon={getDisplayIcon(selectedItem)}
        personalizedComment={getPersonalizedComment(selectedItem, preferences)}
        onBack={() => setSelectedItem(null)}
      />
    );
  }

  return (
    <div className="min-h-screen bg-white pb-24">
      {/* Header */}
      <div className="sticky top-0 bg-white z-10 px-4 pt-4 pb-3 shadow-sm">
        {/* Categories */}
        <div className="flex gap-2 overflow-x-auto pb-1 -mx-4 px-4 scrollbar-hide" style={{ WebkitOverflowScrolling: 'touch' }}>
          {categories.map(category => (
            <button
              key={category.id}
              onClick={() => setActiveCategory(category.id)}
              className={`px-2 sm:px-4 py-1.5 sm:py-2.5 rounded-full whitespace-nowrap transition-all text-xs sm:text-sm font-medium flex-shrink-0 ${
                activeCategory === category.id
                  ? 'bg-green-100 text-green-700'
                  : 'bg-gray-100 text-gray-700 active:bg-gray-200'
              }`}
            >
              {category.name}
            </button>
          ))}
        </div>
      </div>

      {/* Menu Items Grid */}
      <div className="px-4 grid grid-cols-2 gap-3 mt-4">
        {filteredItems.map(item => (
          <MenuItem
            key={item.id}
            item={item}
            tags={getPersonalizedTags(item)}
            displayIcon={getDisplayIcon(item)}
            onClick={() => setSelectedItem(item)}
            onAddToCart={() => addItem({ id: item.id, name: item.name, price: item.price, weight: item.weight, image: item.image })}
            quantity={basketItems.find(b => b.id === item.id)?.quantity ?? 0}
            onIncrement={() => updateQuantity(item.id, (basketItems.find(b => b.id === item.id)?.quantity ?? 0) + 1)}
            onDecrement={() => updateQuantity(item.id, (basketItems.find(b => b.id === item.id)?.quantity ?? 0) - 1)}
          />
        ))}
      </div>

      {/* ChatBot */}
      <ChatBot 
        isFullPage={false}
        onOpenFullPage={() => setIsChatOpen(true)}
        onRecommendationClick={(dishId) => {
          const dish = menuItems.find(item => item.id === dishId);
          if (dish) {
            setSelectedItem(dish);
          }
        }} 
      />

      {/* Basket Floating Button */}
      {getTotalItems() > 0 && (
        <button
          onClick={() => navigate('/basket')}
          className="fixed bottom-36 right-6 w-16 h-16 bg-green-600 text-white rounded-full shadow-xl flex items-center justify-center z-40 hover:bg-green-700 transition-all"
        >
          <ShoppingBag className="w-7 h-7" />
          <span className="absolute -top-1 -right-1 w-6 h-6 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
            {getTotalItems()}
          </span>
        </button>
      )}
    </div>
  );
}