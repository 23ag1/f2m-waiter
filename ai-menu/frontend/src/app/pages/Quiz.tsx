import { useState } from 'react';
import { useNavigate } from 'react-router';
import { motion, AnimatePresence } from 'motion/react';
import { ChevronRight, ChevronLeft, Plus, Shell, Drumstick, Flame, Fish, Nut, Pizza, Wheat, Heart, Milk, UtensilsCrossed, Cookie, LucideIcon } from 'lucide-react';
import { usePreferences } from '../context/PreferencesContext';

// Icon mappings for ingredient options
const favoriteIcons: Record<string, LucideIcon> = {
  'Креветки': Shell,
  'Сыр': Pizza,
  'Грибы': Nut,
  'Томаты': Flame,
  'Курица': Drumstick,
  'Рис': Cookie,
  'Паста': UtensilsCrossed,
  'Морепродукты': Shell,
};

const hatedIcons: Record<string, LucideIcon> = {
  'Лактоза': Milk,
  'Глютен': Wheat,
  'Орехи': Nut,
  'Грибы': Nut,
  'Мясо': Drumstick,
  'Рыба': Fish,
  'Морепродукты': Shell,
  'Острое': Flame,
};

const questions = [
  {
    id: 'name',
    question: 'Как вас зовут?',
    type: 'text',
    placeholder: 'Введите ваше имя',
  },
  {
    id: 'age',
    question: 'Когда у вас день рождения?',
    type: 'date',
    placeholder: '',
  },
  {
    id: 'favoriteIngredients',
    question: 'Ваши любимые ингредиенты?',
    type: 'multiselect',
    options: ['Креветки', 'Сыр', 'Грибы', 'Томаты', 'Курица', 'Рис', 'Паста', 'Морепродукты'],
    allowCustom: true,
  },
  {
    id: 'hatedIngredients',
    question: 'Что вы не едите?',
    type: 'multiselect',
    options: ['Лактоза', 'Глютен', 'Орехи', 'Грибы', 'Мясо', 'Рыба','Морепродукты', 'Острое'],
    allowCustom: true,
  },
  {
    id: 'hungerLevel',
    question: 'Уровень голода?',
    type: 'select',
    options: ['Совсем не голоден', 'Хочу перекусить', 'Голоден', 'Очень голоден'],
  },
  {
    id: 'mood',
    question: 'Как вы себя чувствуете?',
    type: 'select',
    options: ['Отлично', 'Спокойно', 'Устало', 'Расстроено', 'Взволновано', 'Романтично'],
  },
];

export default function Quiz() {
  const [currentStep, setCurrentStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [customInput, setCustomInput] = useState('');
  const [customOptions, setCustomOptions] = useState<string[]>([]);
  const { updatePreferences } = usePreferences();
  const navigate = useNavigate();

  const currentQuestion = questions[currentStep];
  const progress = ((currentStep + 1) / questions.length) * 100;

  const handleNext = () => {
    if (currentStep < questions.length - 1) {
      setCurrentStep(currentStep + 1);
      setCustomInput('');
      setCustomOptions([]);
    } else {
      updatePreferences(answers);
      navigate('/loading');
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
      setCustomInput('');
      setCustomOptions([]);
    }
  };

  const handleAnswer = (value: any) => {
    setAnswers({ ...answers, [currentQuestion.id]: value });
  };

  const toggleMultiSelect = (option: string) => {
    const current = answers[currentQuestion.id] || [];
    const newValue = current.includes(option)
      ? current.filter((item: string) => item !== option)
      : [...current, option];
    handleAnswer(newValue);
  };

  const addCustomOption = () => {
    if (customInput.trim() && !customOptions.includes(customInput.trim())) {
      const newOption = customInput.trim();
      setCustomOptions([...customOptions, newOption]);
      toggleMultiSelect(newOption);
      setCustomInput('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addCustomOption();
    }
  };

  const isAnswered = () => {
    const answer = answers[currentQuestion.id];
    if (currentQuestion.type === 'multiselect') {
      return answer && answer.length > 0;
    }
    return answer && answer.toString().trim() !== '';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-white flex flex-col">
      {/* Progress bar */}
      <div className="w-full h-1.5 bg-gray-200">
        <motion.div
          className="h-full bg-green-600"
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.3 }}
        />
      </div>

      <div className="flex-1 flex items-center justify-center p-4">
        <div className="max-w-md w-full">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentStep}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.3 }}
            >
              <div className="mb-3 text-xs text-gray-500">
                Вопрос {currentStep + 1} из {questions.length}
              </div>

              <h2 className="text-2xl font-bold mb-6">{currentQuestion.question}</h2>

              {/* Text input */}
              {currentQuestion.type === 'text' && (
                <input
                  type="text"
                  placeholder={currentQuestion.placeholder}
                  value={answers[currentQuestion.id] || ''}
                  onChange={(e) => handleAnswer(e.target.value)}
                  className="w-full px-5 py-3.5 border-2 border-gray-200 rounded-xl text-base focus:outline-none focus:border-green-600 transition-colors"
                  autoFocus
                />
              )}

              {/* Date input */}
              {currentQuestion.type === 'date' && (
                <input
                  type="date"
                  value={answers[currentQuestion.id] || ''}
                  onChange={(e) => handleAnswer(e.target.value)}
                  className="w-full px-5 py-3.5 border-2 border-gray-200 rounded-xl text-base focus:outline-none focus:border-green-600 transition-colors"
                  autoFocus
                />
              )}

              {/* Number input */}
              {currentQuestion.type === 'number' && (
                <input
                  type="number"
                  placeholder={currentQuestion.placeholder}
                  value={answers[currentQuestion.id] || ''}
                  onChange={(e) => handleAnswer(e.target.value)}
                  className="w-full px-5 py-3.5 border-2 border-gray-200 rounded-xl text-base focus:outline-none focus:border-green-600 transition-colors"
                  autoFocus
                />
              )}

              {/* Single select */}
              {currentQuestion.type === 'select' && (
                <div className="space-y-2.5">
                  {currentQuestion.options?.map((option) => (
                    <button
                      key={option}
                      onClick={() => handleAnswer(option)}
                      className={`w-full px-5 py-3.5 rounded-xl text-left text-base transition-all ${
                        answers[currentQuestion.id] === option
                          ? 'bg-green-600 text-white shadow-lg'
                          : 'bg-white border-2 border-gray-200'
                      }`}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              )}

              {/* Multi select */}
              {currentQuestion.type === 'multiselect' && (() => {
                const isIngredientQuestion = currentQuestion.id === 'favoriteIngredients' || currentQuestion.id === 'hatedIngredients';
                const iconMap = currentQuestion.id === 'favoriteIngredients' ? favoriteIcons : hatedIcons;
                
                return (
                  <div>
                    {/* Grid layout for ingredient questions */}
                    {isIngredientQuestion ? (
                      <div className="grid grid-cols-2 gap-3 mb-3">
                        {currentQuestion.options?.map((option) => {
                          const selected = (answers[currentQuestion.id] || []).includes(option);
                          const IconComponent = iconMap[option];
                          
                          return (
                            <button
                              key={option}
                              onClick={() => toggleMultiSelect(option)}
                              className={`aspect-square rounded-2xl flex flex-col items-center justify-center gap-2 p-4 transition-all ${
                                selected
                                  ? 'bg-green-600 text-white shadow-lg scale-105'
                                  : 'bg-white border-2 border-gray-200 hover:border-gray-300'
                              }`}
                            >
                              {IconComponent && (
                                <IconComponent className={`w-8 h-8 ${selected ? 'text-white' : 'text-gray-600'}`} />
                              )}
                              <span className={`text-sm font-medium text-center ${selected ? 'text-white' : 'text-gray-800'}`}>
                                {option}
                              </span>
                            </button>
                          );
                        })}
                        
                        {/* Custom options */}
                        {customOptions.map((option) => {
                          const selected = (answers[currentQuestion.id] || []).includes(option);
                          return (
                            <button
                              key={option}
                              onClick={() => toggleMultiSelect(option)}
                              className={`aspect-square rounded-2xl flex flex-col items-center justify-center gap-2 p-4 transition-all ${
                                selected
                                  ? 'bg-green-600 text-white shadow-lg scale-105'
                                  : 'bg-white border-2 border-gray-200 hover:border-gray-300'
                              }`}
                            >
                              <Plus className={`w-8 h-8 ${selected ? 'text-white' : 'text-gray-600'}`} />
                              <span className={`text-sm font-medium text-center ${selected ? 'text-white' : 'text-gray-800'}`}>
                                {option}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      /* List layout for non-ingredient questions */
                      <div className="space-y-2.5 mb-3">
                        {currentQuestion.options?.map((option) => {
                          const selected = (answers[currentQuestion.id] || []).includes(option);
                          return (
                            <button
                              key={option}
                              onClick={() => toggleMultiSelect(option)}
                              className={`w-full px-5 py-3.5 rounded-xl text-left text-base transition-all ${
                                selected
                                  ? 'bg-green-600 text-white shadow-lg'
                                  : 'bg-white border-2 border-gray-200'
                              }`}
                            >
                              {option}
                            </button>
                          );
                        })}

                        {/* Custom options */}
                        {customOptions.map((option) => {
                          const selected = (answers[currentQuestion.id] || []).includes(option);
                          return (
                            <button
                              key={option}
                              onClick={() => toggleMultiSelect(option)}
                              className={`w-full px-5 py-3.5 rounded-xl text-left text-base transition-all ${
                                selected
                                  ? 'bg-green-600 text-white shadow-lg'
                                  : 'bg-white border-2 border-gray-200'
                              }`}
                            >
                              {option}
                            </button>
                          );
                        })}
                      </div>
                    )}

                    {/* Add custom option input */}
                    {currentQuestion.allowCustom && (
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={customInput}
                          onChange={(e) => setCustomInput(e.target.value)}
                          onKeyPress={handleKeyPress}
                          placeholder="Добавить свой вариант"
                          className="flex-1 px-5 py-3.5 border-2 border-dashed border-gray-300 rounded-xl text-base focus:outline-none focus:border-green-600 transition-colors"
                        />
                        <button
                          onClick={addCustomOption}
                          disabled={!customInput.trim()}
                          className={`px-4 py-3.5 rounded-xl transition-all ${
                            customInput.trim()
                              ? 'bg-green-600 text-white hover:bg-green-700'
                              : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                          }`}
                        >
                          <Plus className="w-5 h-5" />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })()}
            </motion.div>
          </AnimatePresence>

          {/* Navigation buttons */}
          <div className="flex gap-3 mt-10">
            {currentStep > 0 && (
              <button
                onClick={handleBack}
                className="flex items-center gap-2 px-5 py-3.5 rounded-full bg-white border-2 border-gray-200 hover:border-gray-300 transition-all"
              >
                <ChevronLeft className="w-5 h-5" />
                Назад
              </button>
            )}

            <button
              onClick={handleNext}
              disabled={!isAnswered()}
              className={`flex-1 flex items-center justify-center gap-2 px-5 py-3.5 rounded-full text-white font-semibold transition-all ${
                isAnswered()
                  ? 'bg-green-600 hover:bg-green-700 shadow-lg'
                  : 'bg-gray-300 cursor-not-allowed'
              }`}
            >
              {currentStep === questions.length - 1 ? 'Завершить' : 'Далее'}
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}