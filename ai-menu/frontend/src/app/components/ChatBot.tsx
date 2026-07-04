import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  MessageCircle, X, Send, Sparkles, Leaf, Drumstick, Fish, Shell, Flame,
  Cookie, Soup, Coffee, Snowflake, Wine, Bot, ShoppingCart, Eye,
  Wheat, Milk, Nut, Plus, BanIcon, RefreshCw,
} from 'lucide-react';
import { usePreferences } from '../context/PreferencesContext';
import { useBasket } from '../context/BasketContext';
import { generateRecommendations, getReplacementDish } from '../utils/recommendations';
import { submitQuestionnaire, getRecommendations, logEvent, logOutcome } from '../api/f2mClient';
import { mapQuizToQuestionnaire } from '../utils/quizMapper';
import { menuItems, menuCalories } from '../pages/Menu';
import MushroomIcon from './icons/MushroomIcon';

// Module-level: safe to reference imported components
const optionIconMap: Record<string, any> = {
  'овощи': Leaf, 'мясо': Drumstick, 'рыба': Fish, 'морепродукты': Shell,
  'острое': Flame, 'сладкое': Cookie, 'суп': Soup,
  'теплое': Coffee, 'холодное': Snowflake, 'алкогольное': Wine, 'без напитков': BanIcon,
};

const hydrateOptions = (opts: Array<{ label: string; value: string }>) =>
  opts.map(o => ({ ...o, icon: optionIconMap[o.value] }));

function loadSession() {
  try {
    const raw = localStorage.getItem('chatSession');
    if (raw) return JSON.parse(raw);
  } catch {}
  return null;
}

interface Message {
  id: number;
  text: string;
  sender: 'user' | 'ai';
  timestamp: Date;
  options?: Array<{ label: string; value: string; icon?: any }>;
  type?: 'text' | 'options' | 'multi-select' | 'recommendations';
  recommendations?: Array<{
    id: number;
    name: string;
    category: string;
    image: string;
    reason: string;
  }>;
}

type QuizStep =
  | 'hasAccount'
  | 'loginPhone'
  | 'loginAuthCode'
  | 'preferences'
  | 'hunger'
  | 'drinks'
  | 'allergyIntro'
  | 'allergies'
  | 'savePreferences'
  | 'phoneNumber'
  | 'saveAuthCode'
  | 'complete';

const accountOptions = [
  { label: 'Да, есть карта лояльности', value: 'Да' },
  { label: 'Нет аккаунта', value: 'Нет' },
];

const preferencesOptions = [
  { label: 'Больше овощей', value: 'овощи', icon: Leaf },
  { label: 'Мясо', value: 'мясо', icon: Drumstick },
  { label: 'Рыба', value: 'рыба', icon: Fish },
  { label: 'Морепродукты', value: 'морепродукты', icon: Shell },
  { label: 'Острое', value: 'острое', icon: Flame },
  { label: 'Сладкое', value: 'сладкое', icon: Cookie },
  { label: 'Суп', value: 'суп', icon: Soup },
];

const hungerOptions = [
  { label: 'Хочу перекусить', value: 'Хочу перекусить' },
  { label: 'Голоден', value: 'Голоден' },
  { label: 'Очень голоден', value: 'Очень голоден' },
];

const drinksOptions = [
  { label: 'Горячие напитки', value: 'теплое', icon: Coffee },
  { label: 'Холодные напитки', value: 'холодное', icon: Snowflake },
  { label: 'Алкоголь', value: 'алкогольное', icon: Wine },
  { label: 'Без напитков', value: 'без напитков', icon: BanIcon },
];

const allergiesOptions = [
  { label: 'Арахис', value: 'Арахис' },
  { label: 'Орехи', value: 'Орехи' },
  { label: 'Рыба', value: 'Рыба' },
  { label: 'Яйца', value: 'Яйца' },
  { label: 'Лактоза', value: 'Лактоза' },
  { label: 'Курица', value: 'Курица' },
  { label: 'Глютен', value: 'Глютен' },
  { label: 'Кинза', value: 'Кинза' },
  { label: 'Говядина', value: 'Говядина' },
  { label: 'Свинина', value: 'Свинина' },
  { label: 'Лук', value: 'Лук' },
  { label: 'Сахар', value: 'Сахар' },
  { label: 'Морепродукты', value: 'Морепродукты' },
  { label: 'Чеснок', value: 'Чеснок' },
  { label: 'Грибы', value: 'Грибы' },
];

const savePreferencesOptions = [
  { label: 'Да, сохранить', value: 'Да' },
  { label: 'Нет, спасибо', value: 'Нет' },
];

interface ChatBotProps {
  onRecommendationClick?: (dishId: number) => void;
  isFullPage?: boolean;
  onClose?: () => void;
  onOpenFullPage?: () => void;
}

// Helper: compute recommendation card tags
function getRecTags(dishId: number, hungerLevel: string, preferences: string[]): string[] {
  const dish = menuItems.find(i => i.id === dishId);
  if (!dish) return [];
  const tags: string[] = [];

  const cal = menuCalories[dishId] ?? 0;
  const weightNum = parseInt(dish.weight);

  if (cal > 0 && cal < 300 && dish.category !== 'drinks' && dish.category !== 'alcohol') tags.push('Некалорийно');
  if (cal >= 600 && (hungerLevel === 'Очень голоден' || hungerLevel === 'Голоден')) tags.push('Сытное блюдо');
  if (!isNaN(weightNum) && weightNum >= 350) tags.push('Большая порция');

  const prefTagLabels: Record<string, string> = {
    'овощ': 'Много овощей',
    'мясо': 'Мясо',
    'рыба': 'Рыба',
    'морепродукт': 'Морепродукты',
    'остр': 'Острое',
    'сладк': 'Десерт',
    'суп': 'Суп',
  };

  const matchedPref = preferences.find(pref => {
    const p = pref.toLowerCase();
    if (p.includes('овощ')) return dish.category === 'salad' || dish.ingredients.some(i => i.toLowerCase().includes('овощ') || i.toLowerCase().includes('томат') || i.toLowerCase().includes('огур'));
    if (p.includes('мясо')) return dish.ingredients.some(i => i.toLowerCase().includes('мясо') || i.toLowerCase().includes('курица') || i.toLowerCase().includes('бекон') || i.toLowerCase().includes('говяд'));
    if (p.includes('рыба')) return dish.ingredients.some(i => i.toLowerCase().includes('рыб') || i.toLowerCase().includes('лосос') || i.toLowerCase().includes('тунец'));
    if (p.includes('морепродукт')) return dish.ingredients.some(i => i.toLowerCase().includes('креветк') || i.toLowerCase().includes('морепродукт') || i.toLowerCase().includes('мидии') || i.toLowerCase().includes('кальмар'));
    if (p.includes('остр')) return dish.allergens.some(a => a.toLowerCase().includes('остр'));
    if (p.includes('сладк')) return dish.category === 'dessert';
    if (p.includes('суп')) return dish.category === 'soup';
    return false;
  });
  if (matchedPref) {
    const key = Object.keys(prefTagLabels).find(k => matchedPref.toLowerCase().includes(k));
    tags.push(key ? prefTagLabels[key] : matchedPref);
  }

  return tags;
}

const recTagColors: Record<string, string> = {
  'Некалорийно': 'bg-blue-100 text-blue-700',
  'Сытное блюдо': 'bg-orange-100 text-orange-700',
  'Большая порция': 'bg-purple-100 text-purple-700',
  'Много овощей': 'bg-green-100 text-green-700',
  'Мясо': 'bg-green-100 text-green-700',
  'Рыба': 'bg-green-100 text-green-700',
  'Морепродукты': 'bg-green-100 text-green-700',
  'Острое': 'bg-green-100 text-green-700',
  'Десерт': 'bg-green-100 text-green-700',
  'Суп': 'bg-green-100 text-green-700',
};

export default function ChatBot({ onRecommendationClick, isFullPage, onClose, onOpenFullPage }: ChatBotProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>(() => {
    const s = loadSession();
    if (!s?.messages?.length) return [];
    return s.messages.map((m: any) => ({
      ...m,
      timestamp: new Date(m.timestamp),
      options: m.options ? hydrateOptions(m.options) : undefined,
    }));
  });
  const [inputValue, setInputValue] = useState('');
  const [quizStep, setQuizStep] = useState<QuizStep>(() => loadSession()?.quizStep ?? 'hasAccount');
  const [selectedPreferences, setSelectedPreferences] = useState<string[]>(() => loadSession()?.selectedPreferences ?? []);
  const [selectedAllergies, setSelectedAllergies] = useState<string[]>(() => {
    const s = loadSession();
    if (s?.selectedAllergies) return s.selectedAllergies;
    try {
      const p = localStorage.getItem('userProfile');
      if (p) return JSON.parse(p).restrictions ?? [];
    } catch {}
    return [];
  });
  const [customAllergy, setCustomAllergy] = useState('');
  const [selectedDrinks, setSelectedDrinks] = useState<string[]>(() => loadSession()?.selectedDrinks ?? []);
  const [showNotification, setShowNotification] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [isReturningUser, setIsReturningUser] = useState<boolean>(() => {
    const s = loadSession();
    if (s?.isReturningUser) return true;
    try {
      return !!localStorage.getItem('userProfile');
    } catch {}
    return false;
  });
  const [otpTimer, setOtpTimer] = useState(0);
  const [otpTimerActive, setOtpTimerActive] = useState(false);
  const [shownRecommendationIds, setShownRecommendationIds] = useState<number[]>(() => loadSession()?.shownRecommendationIds ?? []);
  const [lastRequestId, setLastRequestId] = useState<string>(() => loadSession()?.lastRequestId ?? '');
  const [quizData, setQuizData] = useState(() => {
    const s = loadSession();
    if (s?.quizData) return s.quizData;
    try {
      const p = localStorage.getItem('userProfile');
      if (p) {
        const profile = JSON.parse(p);
        return { hasAccount: false, preferences: [], allergies: profile.restrictions ?? [], hungerLevel: '', drinks: [], phoneNumber: '' };
      }
    } catch {}
    return { hasAccount: false, preferences: [] as string[], allergies: [] as string[], hungerLevel: '', drinks: [] as string[], phoneNumber: '' };
  });

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const suppressScrollRef = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { preferences, updatePreferences } = usePreferences();
  const { addItem, orderPlaced } = useBasket();


  // Persist full session whenever any session state changes
  useEffect(() => {
    if (messages.length === 0) return;
    const session = {
      messages: messages.map(m => ({
        ...m,
        options: m.options?.map(({ icon: _i, ...o }) => o),
      })),
      quizStep,
      quizData,
      selectedPreferences,
      selectedAllergies,
      selectedDrinks,
      shownRecommendationIds,
      lastRequestId,
      isReturningUser,
    };
    localStorage.setItem('chatSession', JSON.stringify(session));
  }, [messages, quizStep, quizData, selectedPreferences, selectedAllergies, selectedDrinks, shownRecommendationIds, lastRequestId]);

  // Reset session when order is placed
  useEffect(() => {
    if (!orderPlaced) return;
    localStorage.removeItem('chatSession');
    setMessages([]);
    setQuizStep('hasAccount');
    setSelectedPreferences([]);
    setSelectedAllergies([]);
    setSelectedDrinks([]);
    setShownRecommendationIds([]);
    setLastRequestId('');
    setQuizData({ hasAccount: false, preferences: [], allergies: [], hungerLevel: '', drinks: [], phoneNumber: '' });
  }, [orderPlaced]);

  // OTP countdown timer
  useEffect(() => {
    if (!otpTimerActive || otpTimer <= 0) return;
    const interval = setInterval(() => {
      setOtpTimer(prev => {
        if (prev <= 1) { setOtpTimerActive(false); return 0; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [otpTimerActive, otpTimer]);

  // Auto-scroll
  useEffect(() => {
    if (suppressScrollRef.current) { suppressScrollRef.current = false; return; }
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Show tooltip notification after 3 seconds (once)
  useEffect(() => {
    const seen = localStorage.getItem('chatNotificationSeen');
    if (!seen && !isOpen) {
      const timer = setTimeout(() => setShowNotification(true), 3000);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Start quiz when chat opens for the first time
  useEffect(() => {
    if ((isOpen || isFullPage) && messages.length === 0) {
      if (preferences?.name) {
        setQuizStep('complete');
        addAIMessage(`Привет, ${preferences.name}! Чем могу помочь?`);
      } else {
        startQuiz();
      }
    }
  }, [isOpen, isFullPage]);

  const dismissNotification = () => {
    setShowNotification(false);
    localStorage.setItem('chatNotificationSeen', 'true');
  };

  const handleOpenChat = () => {
    dismissNotification();
    if (onOpenFullPage) onOpenFullPage();
    else setIsOpen(true);
  };

  const addAIMessage = (text: string, options?: Message['options'], type: Message['type'] = 'text') => {
    setMessages(prev => [...prev, { id: Date.now() + Math.random(), text, sender: 'ai', timestamp: new Date(), options, type }]);
  };

  const addUserMessage = (text: string) => {
    setMessages(prev => [...prev, { id: Date.now() + Math.random(), text, sender: 'user', timestamp: new Date() }]);
  };

  const getSessionUserId = () => {
    const key = 'f2m_engine_session_user_id';
    const existing = localStorage.getItem(key);
    if (existing && /^\d+$/.test(existing)) return Number(existing);
    const generated = 100000 + Math.floor(Math.random() * 900000);
    localStorage.setItem(key, String(generated));
    return generated;
  };

  const getEngineUserId = () => {
    const strategy = String(import.meta.env.VITE_F2M_USER_ID_STRATEGY ?? 'session').toLowerCase();
    if (strategy === 'phone') {
      const digits = String(quizData.phoneNumber ?? '').replace(/\D/g, '');
      if (digits.length >= 6) return Number(digits.slice(-9));
    }
    return getSessionUserId();
  };

  const buildLocalRecommendations = (data: {
    preferences: string[];
    allergies: string[];
    hungerLevel: string;
    drinks: string[];
  }) =>
    generateRecommendations({
      name: 'Гость',
      birthday: '',
      favoriteIngredients: data.preferences,
      hatedIngredients: data.allergies,
      hungerLevel: data.hungerLevel,
      mood: '',
      drinks: data.drinks,
    });

  const mapEngineResultsToCards = (results: Array<{ dish_id: string; score: number }>) => {
    return results
      .map((row) => {
        const dish = menuItems.find(item => String(item.id) === String(row.dish_id));
        if (!dish) return null;
        return {
          id: dish.id,
          name: dish.name,
          category: dish.category,
          image: dish.image,
          reason: `Подобрано движком (score: ${row.score.toFixed(2)})`,
        };
      })
      .filter(Boolean) as Array<{
      id: number;
      name: string;
      category: string;
      image: string;
      reason: string;
    }>;
  };

  const startQuiz = () => {
    addAIMessage('Привет! 👋 Я ваш AI-помощник в ресторане. Давайте подберём идеальные блюда!');
    setTimeout(() => {
      setQuizStep('hasAccount');
      addAIMessage('У вас есть карта лояльности нашего ресторана?', accountOptions, 'options');
    }, 1000);
  };

  // ─── Loyalty step ──────────────────────────────────────────────────────────
  const handleOptionClick = (value: string) => {
    addUserMessage(value);

    if (quizStep === 'hasAccount') {
      const hasAcc = value === 'Да';
      setQuizData(prev => ({ ...prev, hasAccount: hasAcc }));
      if (hasAcc) {
        setQuizStep('loginPhone');
        setIsTyping(true);
        setTimeout(() => {
          setIsTyping(false);
          addAIMessage('Введите ваш номер телефона для входа: 📱');
        }, 800);
      } else {
        setQuizStep('preferences');
        setIsTyping(true);
        setTimeout(() => {
          setIsTyping(false);
          addAIMessage('Что бы вы хотели поесть сегодня? Выберите один или несколько вариантов:', preferencesOptions, 'multi-select');
        }, 800);
      }
      return;
    }

    if (quizStep === 'hunger') {
      setQuizData(prev => ({ ...prev, hungerLevel: value }));
      setQuizStep('drinks');
      setIsTyping(true);
      setTimeout(() => {
        setIsTyping(false);
        addAIMessage('Понял! 🍽️');
        setTimeout(() => {
          addAIMessage('Что насчёт напитков?', drinksOptions, 'multi-select');
        }, 800);
      }, 800);
      return;
    }

    if (quizStep === 'allergyIntro') {
      setSelectedAllergies([]);
      setQuizStep('allergies');
      setIsTyping(true);
      setTimeout(() => {
        setIsTyping(false);
        addAIMessage('Выберите из списка или введите своё:', allergiesOptions, 'multi-select');
      }, 600);
      return;
    }

    if (quizStep === 'savePreferences') {
      if (value === 'Да') {
        setQuizStep('phoneNumber');
        setIsTyping(true);
        setTimeout(() => {
          setIsTyping(false);
          addAIMessage('Введите ваш номер телефона:');
        }, 800);
      } else {
        setQuizStep('complete');
        setIsTyping(true);
        setTimeout(() => {
          setIsTyping(false);
          addAIMessage('Хорошо! Ваши ограничения сохранены локально. Приятного аппетита! 😊');
        }, 800);
      }
      return;
    }
  };

  // ─── Phone / OTP steps ─────────────────────────────────────────────────────
  const processQuizStep = (response: string) => {
    switch (quizStep) {
      case 'loginPhone': {
        setQuizData(prev => ({ ...prev, phoneNumber: response }));
        setQuizStep('loginAuthCode');
        setOtpTimer(60);
        setOtpTimerActive(true);
        addAIMessage('Код отправлен на ваш номер. Введите 6 цифр: 🔐');
        break;
      }

      case 'loginAuthCode': {
        const code = response.trim();
        if (code.length === 6 && /^\d+$/.test(code)) {
          setOtpTimerActive(false);
          setIsTyping(true);
          setTimeout(() => {
            setIsTyping(false);
            addAIMessage('Вход выполнен! 🎉');
            setTimeout(() => {
              setQuizStep('preferences');
              addAIMessage('Что бы вы хотели поесть сегодня?', preferencesOptions, 'multi-select');
            }, 800);
          }, 800);
        } else {
          const timerMsg = otpTimerActive && otpTimer > 0 ? ` Повторная отправка через ${otpTimer} сек.` : '';
          addAIMessage(`Неверный код.${timerMsg} Попробуйте ещё раз:`);
        }
        break;
      }

      case 'phoneNumber': {
        setQuizData(prev => ({ ...prev, phoneNumber: response }));
        setQuizStep('saveAuthCode');
        setOtpTimer(60);
        setOtpTimerActive(true);
        addAIMessage('Код отправлен на ваш номер. Введите 4 цифры из сообщения: 🔐');
        break;
      }

      case 'saveAuthCode': {
        const code = response.trim();
        if (code.length === 4 && /^\d+$/.test(code)) {
          setOtpTimerActive(false);
          setIsTyping(true);
          setTimeout(() => {
            setIsTyping(false);
            setQuizStep('complete');
            updatePreferences({
              preferences: quizData.preferences,
              hungerLevel: quizData.hungerLevel,
              drinks: quizData.drinks,
              restrictions: quizData.allergies,
            });
            addAIMessage('Всё сохранено! В следующий раз просто откройте помощник — анкету заполнять не придётся. Приятного аппетита! 🎉');
          }, 800);
        } else {
          const timerMsg = otpTimerActive && otpTimer > 0 ? ` Повторная отправка через ${otpTimer} сек.` : '';
          addAIMessage(`Неверный код.${timerMsg} Попробуйте ещё раз:`);
        }
        break;
      }
    }
  };

  // ─── Preferences step ──────────────────────────────────────────────────────
  const togglePreference = (value: string) => {
    setSelectedPreferences(prev => prev.includes(value) ? prev.filter(v => v !== value) : [...prev, value]);
  };

  const handlePreferencesComplete = () => {
    if (selectedPreferences.length === 0) return;
    addUserMessage(`Выбрано: ${selectedPreferences.join(', ')}`);
    setQuizData(prev => ({ ...prev, preferences: selectedPreferences }));
    setQuizStep('hunger');
    setIsTyping(true);
    setTimeout(() => {
      setIsTyping(false);
      addAIMessage('Отличный выбор! 👨‍🍳 Насколько вы голодны?', hungerOptions, 'options');
    }, 800);
  };

  // ─── Drinks step ───────────────────────────────────────────────────────────
  const toggleDrink = (value: string) => {
    if (value === 'без напитков') {
      setSelectedDrinks(prev => prev.includes(value) ? [] : ['без напитков']);
    } else {
      setSelectedDrinks(prev => {
        const withoutNone = prev.filter(v => v !== 'без напитков');
        return withoutNone.includes(value) ? withoutNone.filter(v => v !== value) : [...withoutNone, value];
      });
    }
  };

  const handleDrinksComplete = () => {
    const noDrinks = selectedDrinks.includes('без напитков') || selectedDrinks.length === 0;
    addUserMessage(noDrinks ? 'Без напитков' : `Напитки: ${selectedDrinks.join(', ')}`);
    const finalDrinks = noDrinks ? [] : selectedDrinks;
    const updatedData = { ...quizData, drinks: finalDrinks };
    setQuizData(updatedData);

    updatePreferences({
      preferences: updatedData.preferences,
      hungerLevel: updatedData.hungerLevel,
      drinks: finalDrinks,
      restrictions: updatedData.allergies,
    });

    setIsTyping(true);
    setTimeout(() => {
      setIsTyping(false);
      addAIMessage('Подбираю блюда для вас... ✨');
      setTimeout(() => {
        setIsTyping(true);
        setTimeout(() => {
          setIsTyping(false);
          void (async () => {
            let recs = [] as Array<{ id: number; name: string; category: string; image: string; reason: string }>;

            try {
              const userId = getEngineUserId();
              const mapped = mapQuizToQuestionnaire({
                preferences: updatedData.preferences ?? [],
                hungerLevel: updatedData.hungerLevel ?? '',
                drinks: finalDrinks ?? [],
                allergies: updatedData.allergies ?? [],
              });

              await submitQuestionnaire(
                userId,
                mapped.raw_answers_json,
                Array.isArray(mapped.raw_answers_json.allergies) ? (mapped.raw_answers_json.allergies as string[]) : [],
              );

              const scoreResponse = await getRecommendations(userId, 10, {
                source: 'chatbot',
                surface: 'waiter_web',
              });

              setLastRequestId(scoreResponse.request_id ?? '');
              recs = mapEngineResultsToCards(scoreResponse.results ?? []);
            } catch {
              // Silent fallback to local engine
            }

            if (!recs.length) {
              recs = buildLocalRecommendations({
                preferences: updatedData.preferences ?? [],
                allergies: updatedData.allergies ?? [],
                hungerLevel: updatedData.hungerLevel ?? '',
                drinks: finalDrinks,
              });
            }

            if (!recs || recs.length === 0) {
              addAIMessage('Не удалось подобрать блюда — попробуйте изменить запрос. 😊');
            } else {
              setShownRecommendationIds(recs.map(r => r.id));
              setMessages(prev => [...prev, {
                id: Date.now(),
                text: 'Вот мои рекомендации специально для вас:',
                sender: 'ai',
                timestamp: new Date(),
                type: 'recommendations',
                recommendations: recs,
              }]);
            }
          })();

          // After recommendations
          setTimeout(() => {
            if (!updatedData.hasAccount) {
              setQuizStep('allergyIntro');
              addAIMessage(
                'Кстати, есть ли у вас аллергии или продукты, которые вы не едите? Расскажите один раз — больше спрашивать не будем.',
                [{ label: 'Перейти', value: 'Перейти' }],
                'options',
              );
            } else {
              setQuizStep('complete');
              addAIMessage('Приятного аппетита! Чем ещё могу помочь? 😊');
            }
          }, 1500);
        }, 1000);
      }, 800);
    }, 800);
  };

  // ─── Allergies step ────────────────────────────────────────────────────────
  const toggleAllergy = (value: string) => {
    setSelectedAllergies(prev => prev.includes(value) ? prev.filter(v => v !== value) : [...prev, value]);
  };

  const addCustomAllergy = () => {
    const val = customAllergy.trim();
    if (val && !selectedAllergies.includes(val)) {
      setSelectedAllergies(prev => [...prev, val]);
    }
    setCustomAllergy('');
  };

  const handleAllergiesComplete = () => {
    const all = [...selectedAllergies];
    addUserMessage(all.length > 0 ? `Ограничения: ${all.join(', ')}` : 'Нет ограничений');
    setQuizData(prev => ({ ...prev, allergies: all }));

    // Save profile to localStorage
    localStorage.setItem('userProfile', JSON.stringify({
      restrictions: all,
      savedAt: new Date().toISOString(),
    }));

    setQuizStep('savePreferences');
    setIsTyping(true);
    setTimeout(() => {
      setIsTyping(false);
      addAIMessage('Сохранено! 🎉');
      setTimeout(() => {
        addAIMessage(
          'Хотите, чтобы мы запомнили вас? Тогда в следующий раз не придётся заполнять анкету заново.',
          savePreferencesOptions,
          'options',
        );
      }, 800);
    }, 800);
  };

  // ─── Show more recommendations ─────────────────────────────────────────────
  const handleShowMore = () => {
    addUserMessage('Покажи другие блюда');
    setIsTyping(true);
    setTimeout(() => {
      setIsTyping(false);
      addAIMessage('Ищу ещё варианты... ✨');
      setTimeout(() => {
        setIsTyping(true);
        setTimeout(() => {
          setIsTyping(false);
          try {
            const allRecs = buildLocalRecommendations({
              preferences: quizData.preferences,
              allergies: quizData.allergies,
              hungerLevel: quizData.hungerLevel,
              drinks: quizData.drinks,
            });
            const newRecs = allRecs.filter(r => !shownRecommendationIds.includes(r.id));
            if (!newRecs || newRecs.length === 0) {
              addAIMessage('Больше подходящих блюд нет — это все варианты по вашему запросу. Попробуйте изменить предпочтения? 😊');
            } else {
              setShownRecommendationIds(prev => [...prev, ...newRecs.map(r => r.id)]);
              setMessages(prev => [...prev, {
                id: Date.now(),
                text: 'Вот ещё варианты:',
                sender: 'ai',
                timestamp: new Date(),
                type: 'recommendations',
                recommendations: newRecs,
              }]);
            }
          } catch {
            addAIMessage('Что-то пошло не так. Попробуйте ещё раз. 😊');
          }
        }, 1000);
      }, 800);
    }, 600);
  };

  // ─── Change request (restart from preferences) ─────────────────────────────
  const handleChangeRequest = () => {
    addUserMessage('Изменить запрос');
    setSelectedPreferences([]);
    setSelectedDrinks([]);
    setShownRecommendationIds([]);
    setQuizData(prev => ({ ...prev, preferences: [], hungerLevel: '', drinks: [] }));
    setIsTyping(true);
    setTimeout(() => {
      setIsTyping(false);
      addAIMessage('Хорошо, давайте начнём заново! Что бы вы хотели поесть сегодня?', preferencesOptions, 'multi-select');
      setQuizStep('preferences');
    }, 800);
  };

  // ─── Free chat ─────────────────────────────────────────────────────────────
  const generateAIResponse = (userMessage: string): string => {
    const m = userMessage.toLowerCase();
    if (m.match(/привет|здравствуй|добрый/)) return `Здравствуйте${preferences?.name ? `, ${preferences.name}` : ''}! Чем могу помочь?`;
    if (m.match(/люблю|нравится/) && m.match(/креветк|морепродукт/)) return 'У нас есть: Спагетти Неро с креветками, Ризотто с морепродуктами, Том Ям с креветками. Очень популярны!';
    if (m.match(/люблю|нравится/) && m.match(/паст/)) return 'Отличный выбор! Карбонара, Феттучини с грибами, Пенне Аррабьята — все блюда на высоте!';
    if (m.match(/грустн|устал|плох/)) return 'Порекомендую Тирамису или Чизкейк — сладкое поднимет настроение! 🍰';
    if (m.match(/романтик|свидани/)) return 'Для романтического вечера: Ризотто с морепродуктами, Стейк из лосося, на десерт — Панна-котта.';
    if (m.match(/голоден|очень хоч|сытн/)) return 'Для сытного ужина: Ризотто с морепродуктами, Паста Карбонара, Стейк Рибай. Большие порции, много белка!';
    if (m.match(/лёгк|диет|калори/)) return 'Для лёгкого перекуса: Томатный суп с морепродуктами или Салат с креветками и авокадо. Некалорийно и вкусно!';
    if (m.match(/десерт|сладк/)) return 'Десерты: Тирамису, Чизкейк Нью-Йорк, Панна-котта, Шоколадный фондан. Что предпочитаете?';
    if (m.match(/суп/)) return 'Наши супы: Томатный с морепродуктами, Крем-суп из чечевицы, Грибной крем-суп, Том Ям, Тыквенный. На любой вкус!';
    if (m.match(/напит|кофе|чай|сок/)) return 'Напитки: Эспрессо, Капучино, Латте, Апельсиновый фреш, Лимонад, Смузи ягодный, Зелёный чай.';
    if (m.match(/цен|стоимост|сколько/)) return 'Основные блюда 329–899₽, супы 279–379₽, салаты 329–459₽, десерты 189–349₽, напитки 119–219₽.';
    if (m.match(/вегетариан|без мяс/)) return 'Вегетарианские варианты: Пенне Аррабьята, Греческий салат, Грибной крем-суп, Тыквенный крем-суп.';
    if (m.match(/аллерг|непереносим/)) return 'Расскажите о вашей аллергии — уточню, какие блюда безопасны.';
    if (m.match(/спасиб|благодар/)) return 'Всегда пожалуйста! Приятного аппетита! 😊';
    const defaults = [
      'Расскажите подробнее — помогу с выбором!',
      'Могу рассказать про ингредиенты, аллергены или подобрать блюда. Что интересует?',
      'Попробуйте описать, что хочется — постараюсь помочь!',
    ];
    return defaults[Math.floor(Math.random() * defaults.length)];
  };

  const handleSendMessage = () => {
    if (!inputValue.trim()) return;
    if (quizStep !== 'complete') {
      handleQuizResponse(inputValue);
    } else {
      const msg = inputValue;
      addUserMessage(msg);
      setIsTyping(true);
      setTimeout(() => {
        setIsTyping(false);
        addAIMessage(generateAIResponse(msg));
      }, 800 + Math.random() * 600);
    }
    setInputValue('');
  };

  const handleQuizResponse = (response: string) => {
    addUserMessage(response);
    setIsTyping(true);
    setTimeout(() => {
      setIsTyping(false);
      processQuizStep(response);
    }, 800);
    setInputValue('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); }
  };

  const handleAddToBasket = (dishId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const dish = menuItems.find(i => i.id === dishId);
    if (!dish) return;

    addItem({ id: dish.id, name: dish.name, price: dish.price, weight: dish.weight, image: dish.image });

    const userId = getEngineUserId();
    void logEvent(userId, 'add_to_cart', dish.id).catch(() => {});
    if (lastRequestId) {
      void logOutcome(lastRequestId, dish.id, 'add_to_cart').catch(() => {});
    }
  };

  const handleReplaceRecommendation = (messageId: number, recId: number) => {
    const rec = messages.find(m => m.id === messageId)?.recommendations?.find(r => r.id === recId);
    if (!rec) return;

    const replacement = getReplacementDish(rec.category, [...shownRecommendationIds, recId], {
      name: 'Гость',
      favoriteIngredients: quizData.preferences,
      hatedIngredients: quizData.allergies,
      hungerLevel: quizData.hungerLevel,
      mood: '',
      drinks: quizData.drinks,
    });
    if (!replacement) return;

    suppressScrollRef.current = true;
    setShownRecommendationIds(prev => [...prev, replacement.id]);
    setMessages(prev => prev.map(m => {
      if (m.id !== messageId || !m.recommendations) return m;
      return {
        ...m,
        recommendations: m.recommendations.map(r => r.id === recId ? replacement : r),
      };
    }));
  };

  const handleResendOtp = () => {
    setOtpTimer(60);
    setOtpTimerActive(true);
    addAIMessage('Новый код отправлен! Введите 6 цифр: 🔐');
  };

  // ─── Shared messages renderer ───────────────────────────────────────────────
  const renderMessages = () => {
    // Only the last interactive AI message should show clickable controls.
    // Older messages are already answered and must be read-only.
    const lastInteractiveMsgId = [...messages].reverse().find(
      m => m.sender === 'ai' && (m.type === 'options' || m.type === 'multi-select' || m.type === 'recommendations')
    )?.id ?? null;

    return (
    <>
      {messages.map((message) => (
        <motion.div
          key={message.id}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div className="max-w-[85%]">
            <div className={`rounded-2xl px-4 py-2.5 ${
              message.sender === 'user'
                ? 'bg-green-600 text-white rounded-br-sm'
                : 'bg-white text-gray-800 shadow-sm rounded-bl-sm'
            }`}>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.text}</p>
            </div>

            {/* Single-choice options */}
            {message.sender === 'ai' && message.options && message.type === 'options' && message.id === lastInteractiveMsgId && (
              <div className="mt-3 flex flex-col gap-2">
                {message.options.map((opt, idx) => (
                  <motion.button
                    key={idx}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleOptionClick(opt.value)}
                    className="bg-white border-2 border-green-200 hover:border-green-400 text-gray-800 px-4 py-2.5 rounded-xl text-sm font-medium transition-all text-left shadow-sm"
                  >
                    {opt.label}
                  </motion.button>
                ))}
              </div>
            )}

            {/* OTP resend button (shown below the loginAuthCode message) */}
            {message.sender === 'ai' && quizStep === 'loginAuthCode' && message.text.includes('Введите 6 цифр') && (
              <div className="mt-2">
                {otpTimerActive && otpTimer > 0 ? (
                  <p className="text-xs text-gray-500">Повторная отправка через {otpTimer} сек.</p>
                ) : (
                  <button
                    onClick={handleResendOtp}
                    className="text-xs text-green-600 underline mt-1"
                  >
                    Отправить код повторно
                  </button>
                )}
              </div>
            )}

            {/* Multi-select: preferences */}
            {message.sender === 'ai' && message.options && message.type === 'multi-select' && quizStep === 'preferences' && message.id === lastInteractiveMsgId && (
              <div className="mt-3 space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  {message.options.map((opt, idx) => {
                    const Icon = opt.icon;
                    const sel = selectedPreferences.includes(opt.value);
                    return (
                      <motion.button
                        key={idx}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => togglePreference(opt.value)}
                        className={`rounded-xl border-2 transition-all flex flex-col items-center justify-center gap-1.5 py-2.5 px-2 ${sel ? 'bg-green-100 border-green-500 shadow-md' : 'bg-white border-gray-200 hover:border-green-300'}`}
                      >
                        {Icon && <Icon className={`w-6 h-6 ${sel ? 'text-green-600' : 'text-gray-600'}`} />}
                        <span className={`text-xs font-medium text-center leading-tight ${sel ? 'text-green-700' : 'text-gray-700'}`}>{opt.label}</span>
                      </motion.button>
                    );
                  })}
                </div>
                {selectedPreferences.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {selectedPreferences.map((item, idx) => (
                      <span key={idx} className="px-2.5 py-1 bg-green-100 text-green-700 rounded-full text-xs font-medium">{item}</span>
                    ))}
                  </div>
                )}
                <button
                  onClick={handlePreferencesComplete}
                  disabled={selectedPreferences.length === 0}
                  className="w-full bg-green-600 text-white px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Продолжить
                </button>
              </div>
            )}

            {/* Multi-select: allergies */}
            {message.sender === 'ai' && message.options && message.type === 'multi-select' && quizStep === 'allergies' && message.id === lastInteractiveMsgId && (
              <div className="mt-3 space-y-3">
                <div className="grid grid-cols-3 gap-2">
                  {message.options.map((opt, idx) => {
                    const Icon = opt.icon;
                    const sel = selectedAllergies.includes(opt.value);
                    return (
                      <motion.button
                        key={idx}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => toggleAllergy(opt.value)}
                        className={`rounded-xl border-2 transition-all flex flex-col items-center justify-center gap-1 p-2 min-h-[64px] ${sel ? 'bg-red-100 border-red-500 shadow-md' : 'bg-white border-gray-200 hover:border-red-300'}`}
                      >
                        {Icon && <Icon className={`w-5 h-5 ${sel ? 'text-red-600' : 'text-gray-500'}`} />}
                        <span className={`text-xs font-medium text-center leading-tight ${sel ? 'text-red-700' : 'text-gray-700'}`}>{opt.label}</span>
                      </motion.button>
                    );
                  })}
                </div>

                {/* Custom allergy input */}
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={customAllergy}
                    onChange={e => setCustomAllergy(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCustomAllergy(); } }}
                    placeholder="Другое..."
                    className="flex-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-300"
                  />
                  {customAllergy.trim() && (
                    <button
                      onClick={addCustomAllergy}
                      className="w-9 h-9 bg-red-500 text-white rounded-lg flex items-center justify-center hover:bg-red-600 transition-colors"
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                  )}
                </div>

                {selectedAllergies.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {selectedAllergies.map((item, idx) => (
                      <button
                        key={idx}
                        onClick={() => setSelectedAllergies(prev => prev.filter(v => v !== item))}
                        className="px-2.5 py-1 bg-red-100 text-red-700 rounded-full text-xs font-medium flex items-center gap-1"
                      >
                        {item} <X className="w-3 h-3" />
                      </button>
                    ))}
                  </div>
                )}

                <div className="flex gap-2">
                  <button
                    onClick={handleAllergiesComplete}
                    className="flex-1 bg-green-600 text-white px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-green-700 transition-colors"
                  >
                    {selectedAllergies.length > 0 ? 'Продолжить' : 'Нет ограничений'}
                  </button>
                </div>
              </div>
            )}

            {/* Multi-select: drinks */}
            {message.sender === 'ai' && message.options && message.type === 'multi-select' && quizStep === 'drinks' && message.id === lastInteractiveMsgId && (
              <div className="mt-3 space-y-3">
                <div className="grid grid-cols-1 gap-2">
                  {message.options.map((opt, idx) => {
                    const Icon = opt.icon;
                    const sel = selectedDrinks.includes(opt.value);
                    return (
                      <motion.button
                        key={idx}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => toggleDrink(opt.value)}
                        className={`rounded-xl border-2 transition-all flex items-center gap-3 p-3 ${sel ? 'bg-blue-100 border-blue-500 shadow-md' : 'bg-white border-gray-200 hover:border-blue-300'}`}
                      >
                        {Icon && <Icon className={`w-6 h-6 ${sel ? 'text-blue-600' : 'text-gray-600'}`} />}
                        <span className={`text-sm font-medium ${sel ? 'text-blue-700' : 'text-gray-700'}`}>{opt.label}</span>
                      </motion.button>
                    );
                  })}
                </div>
                {selectedDrinks.filter(d => d !== 'без напитков').length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {selectedDrinks.filter(d => d !== 'без напитков').map((item, idx) => (
                      <span key={idx} className="px-2.5 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">{item}</span>
                    ))}
                  </div>
                )}
                <button
                  onClick={handleDrinksComplete}
                  className="w-full bg-green-600 text-white px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-green-700 transition-colors"
                >
                  {selectedDrinks.length > 0 ? 'Продолжить' : 'Пропустить'}
                </button>
              </div>
            )}

            {/* Recommendations */}
            {message.sender === 'ai' && message.type === 'recommendations' && message.recommendations && (() => {
              const lastRecMsgId = [...messages].reverse().find(m => m.type === 'recommendations')?.id;
              const isLatest = message.id === lastRecMsgId;
              return (
                <div className="mt-3 space-y-3">
                  {message.recommendations.map((rec, idx) => {
                    const dish = menuItems.find(i => i.id === rec.id);
                    const tags = getRecTags(rec.id, quizData.hungerLevel, quizData.preferences);
                    return (
                      <div key={idx} className="w-full bg-white rounded-xl overflow-hidden shadow-md border border-gray-100 hover:shadow-lg transition-all">
                        <div className="flex gap-3 p-3">
                          <div className="w-20 h-20 rounded-lg overflow-hidden bg-gray-100 flex-shrink-0">
                            <img src={rec.image} alt={rec.name} className="w-full h-full object-cover" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between gap-2 mb-1">
                              <h4 className="font-semibold text-sm line-clamp-2 leading-tight">{rec.name}</h4>
                              {dish && <span className="text-xs font-bold text-green-600 flex-shrink-0">{dish.price}₽</span>}
                            </div>
                            <p className="text-xs text-gray-600 leading-relaxed mb-2">{rec.reason}</p>
                            {tags.length > 0 && (
                              <div className="flex flex-wrap gap-1">
                                {tags.map((tag, ti) => (
                                  <span key={ti} className={`px-2 py-0.5 rounded-full text-xs font-medium ${recTagColors[tag] ?? 'bg-gray-100 text-gray-700'}`}>{tag}</span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="flex gap-2 px-3 pb-3">
                          <button
                            onClick={e => handleAddToBasket(rec.id, e)}
                            className="flex-1 bg-green-600 text-white px-3 py-2 rounded-lg text-xs font-medium hover:bg-green-700 transition-colors flex items-center justify-center gap-1.5"
                          >
                            <ShoppingCart className="w-3.5 h-3.5" />
                            В корзину
                          </button>
                          <button
                            onClick={() => onRecommendationClick?.(rec.id)}
                            className="flex-1 bg-gray-100 text-gray-700 px-3 py-2 rounded-lg text-xs font-medium hover:bg-gray-200 transition-colors flex items-center justify-center gap-1.5"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            Подробнее
                          </button>
                          <button
                            onClick={() => handleReplaceRecommendation(message.id, rec.id)}
                            title="Заменить"
                            className="w-9 h-9 bg-gray-100 text-gray-600 rounded-lg flex items-center justify-center hover:bg-gray-200 transition-colors flex-shrink-0"
                          >
                            <RefreshCw className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    );
                  })}

                  {/* Action buttons — only on the latest recommendations message */}
                  {isLatest && !isTyping && (
                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={handleShowMore}
                        className="flex-1 bg-white border-2 border-gray-200 hover:border-green-400 text-gray-700 px-3 py-2 rounded-xl text-xs font-medium transition-all"
                      >
                        🔄 Показать ещё
                      </button>
                      <button
                        onClick={handleChangeRequest}
                        className="flex-1 bg-white border-2 border-gray-200 hover:border-green-400 text-gray-700 px-3 py-2 rounded-xl text-xs font-medium transition-all"
                      >
                        ✏️ Изменить запрос
                      </button>
                    </div>
                  )}
                </div>
              );
            })()}
          </div>
        </motion.div>
      ))}

      {isTyping && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex justify-start">
          <div className="bg-white rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
            <div className="flex gap-1.5">
              {[0, 0.2, 0.4].map((delay, i) => (
                <motion.div
                  key={i}
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay }}
                  className="w-2 h-2 bg-gray-400 rounded-full"
                />
              ))}
            </div>
          </div>
        </motion.div>
      )}
      <div ref={messagesEndRef} />
    </>
    );
  };

  const renderInput = () => (
    <div className="p-4 bg-white border-t border-gray-200">
      <div className="flex gap-2">
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={quizStep === 'complete' ? 'Напишите сообщение...' : 'Введите ответ...'}
          className="flex-1 px-4 py-2.5 bg-gray-100 border-none rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
        />
        <button
          onClick={handleSendMessage}
          disabled={!inputValue.trim()}
          className="w-10 h-10 bg-green-600 text-white rounded-full flex items-center justify-center hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );

  // ─── Full page mode ─────────────────────────────────────────────────────────
  if (isFullPage) {
    return (
      <div className="fixed inset-0 bg-white z-40 flex flex-col">
        <div className="bg-gradient-to-r from-green-600 to-green-700 text-white px-4 py-4 flex items-center justify-between shadow-md">
          <div className="flex items-center gap-3">
            <button onClick={onClose} className="w-10 h-10 hover:bg-white/20 rounded-full flex items-center justify-center transition-colors">
              <X className="w-5 h-5" />
            </button>
            <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-lg">AI-Помощник</h3>
              <p className="text-xs text-green-100">{quizStep === 'complete' ? 'Всегда на связи' : 'Подбираем блюда для вас'}</p>
            </div>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">{renderMessages()}</div>
        {renderInput()}
      </div>
    );
  }

  // ─── Floating mode ──────────────────────────────────────────────────────────
  return (
    <>
      <AnimatePresence>
        {!isOpen && !isFullPage && (
          <>
            <motion.button
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={handleOpenChat}
              className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-gradient-to-br from-green-500 to-green-600 text-white rounded-2xl shadow-2xl flex flex-col items-center justify-center z-50 hover:from-green-600 hover:to-green-700 transition-all px-6 py-4 gap-2 border-2 border-green-400"
            >
              <div className="flex items-center gap-2">
                <Sparkles className="w-6 h-6" />
                <Bot className="w-6 h-6" />
              </div>
              <span className="text-sm font-bold tracking-wide">Подбери себе блюдо</span>
            </motion.button>

            {/* Tooltip near the button */}
            {showNotification && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 20 }}
                transition={{ type: 'spring', damping: 20, stiffness: 300 }}
                className="fixed bottom-32 left-1/2 -translate-x-1/2 bg-white rounded-xl shadow-xl border border-gray-200 p-4 z-50 max-w-xs w-[calc(100vw-3rem)]"
              >
                {/* Arrow pointing down toward button */}
                <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-4 h-4 bg-white border-b border-r border-gray-200 rotate-45" />
                <button
                  onClick={dismissNotification}
                  className="absolute -top-2 -right-2 w-6 h-6 bg-gray-600 hover:bg-gray-700 text-white rounded-full flex items-center justify-center transition-colors"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
                <div className="flex gap-3">
                  <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center flex-shrink-0">
                    <Bot className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-900 mb-1">Нажмите, чтобы подобрать блюда</h4>
                    <p className="text-sm text-gray-600 leading-relaxed">
                      AI-помощник учтёт ваши вкусы, аллергии и уровень голода
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </>
        )}
      </AnimatePresence>

      {/* Chat window (floating) */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 100, scale: 0.8 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 100, scale: 0.8 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="fixed bottom-6 right-6 w-[calc(100vw-3rem)] sm:w-96 h-[600px] bg-white rounded-2xl shadow-2xl z-50 flex flex-col overflow-hidden"
          >
            <div className="bg-gradient-to-r from-green-600 to-green-700 text-white px-5 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold">AI-Помощник</h3>
                  <p className="text-xs text-green-100">{quizStep === 'complete' ? 'Всегда на связи' : 'Подбираем блюда для вас'}</p>
                </div>
              </div>
              <button onClick={() => setIsOpen(false)} className="w-8 h-8 hover:bg-white/20 rounded-full flex items-center justify-center transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">{renderMessages()}</div>
            {renderInput()}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
