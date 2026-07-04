import { useEffect } from 'react';
import { useNavigate } from 'react-router';
import { MessageCircle, UtensilsCrossed, BookOpen, Heart, Brain } from 'lucide-react';
import { motion } from 'motion/react';

export default function Onboarding() {
  const navigate = useNavigate();

  useEffect(() => {
    if (localStorage.getItem('onboardingSeen')) {
      navigate('/menu', { replace: true });
    }
  }, [navigate]);

  const handleOpen = () => {
    localStorage.setItem('onboardingSeen', 'true');
    navigate('/menu');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-white flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="max-w-2xl w-full text-center"
      >
        {/* Food and Chat Illustration */}
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="relative mb-8 flex items-center justify-center gap-6"
        >
          <motion.div
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            className="text-6xl"
          >
            🍝
          </motion.div>

          <motion.div
            animate={{ y: [0, -15, 0] }}
            transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut', delay: 0.3 }}
            className="text-6xl"
          >
            🥗
          </motion.div>

          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.5, type: 'spring', stiffness: 200 }}
            className="relative"
          >
            <div className="bg-green-600 text-white rounded-3xl px-6 py-4 shadow-lg">
              <MessageCircle className="w-8 h-8" />
            </div>
            <motion.div
              animate={{ scale: [1, 1.1, 1] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
              className="absolute -top-1 -right-1 w-4 h-4 bg-green-400 rounded-full"
            />
          </motion.div>

          <motion.div
            animate={{ y: [0, -12, 0] }}
            transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut', delay: 0.6 }}
            className="text-6xl"
          >
            🍰
          </motion.div>

          <motion.div
            animate={{ y: [0, -8, 0] }}
            transition={{ duration: 2.8, repeat: Infinity, ease: 'easeInOut', delay: 0.2 }}
            className="text-6xl"
          >
            🍷
          </motion.div>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="text-4xl font-bold mb-4"
        >
          Добро пожаловать!
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7 }}
          className="text-xl text-gray-600 mb-8 max-w-lg mx-auto"
        >
          В меню есть AI-помощник — он подберёт блюда специально для вас
        </motion.p>

        {/* Capability bullets */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
          className="flex flex-col gap-3 mb-10 max-w-sm mx-auto text-left"
        >
          <div className="flex items-center gap-3 bg-white rounded-2xl px-4 py-3 shadow-sm border border-gray-100">
            <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center flex-shrink-0">
              <Heart className="w-5 h-5 text-green-600" />
            </div>
            <span className="text-sm text-gray-700">Подберёт блюда под ваш вкус и ограничения</span>
          </div>

          <div className="flex items-center gap-3 bg-white rounded-2xl px-4 py-3 shadow-sm border border-gray-100">
            <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center flex-shrink-0">
              <Brain className="w-5 h-5 text-green-600" />
            </div>
            <span className="text-sm text-gray-700">Запомнит ваши предпочтения и аллергии</span>
          </div>

          <div className="flex items-center gap-3 bg-white rounded-2xl px-4 py-3 shadow-sm border border-gray-100">
            <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center flex-shrink-0">
              <BookOpen className="w-5 h-5 text-green-600" />
            </div>
            <span className="text-sm text-gray-700">Объяснит состав незнакомых блюд</span>
          </div>
        </motion.div>

        <motion.button
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.0 }}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={handleOpen}
          className="w-full max-w-sm mx-auto bg-green-600 text-white py-4 px-8 rounded-full text-lg font-semibold hover:bg-green-700 active:bg-green-700 transition-colors shadow-lg flex items-center justify-center gap-2"
        >
          <UtensilsCrossed className="w-5 h-5" />
          Открыть меню
        </motion.button>
      </motion.div>
    </div>
  );
}
