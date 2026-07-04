import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router';
import { motion } from 'motion/react';
import { CheckCircle, PartyPopper } from 'lucide-react';
import { useBasket } from '../context/BasketContext';

export default function OrderSuccess() {
  const navigate = useNavigate();
  const location = useLocation();
  const { resetOrder } = useBasket();
  const orderNumber = location.state?.orderNumber ?? Math.floor(1000 + Math.random() * 9000);

  useEffect(() => {
    return () => {
      resetOrder();
    };
  }, []);

  const handleBack = () => {
    navigate('/menu');
  };

  return (
    <div className="min-h-screen bg-white flex flex-col items-center justify-center px-8 text-center">
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: 'spring', damping: 15, stiffness: 300 }}
        className="w-28 h-28 bg-green-100 rounded-full flex items-center justify-center mb-8"
      >
        <CheckCircle className="w-16 h-16 text-green-600" />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="w-full max-w-sm"
      >
        <div className="flex items-center justify-center gap-2 mb-3">
          <PartyPopper className="w-6 h-6 text-yellow-500" />
          <h1 className="text-3xl font-bold text-gray-900">Заказ принят!</h1>
          <PartyPopper className="w-6 h-6 text-yellow-500" />
        </div>
        <p className="text-gray-500 text-sm mb-2">Номер заказа</p>
        <p className="text-4xl font-bold text-green-600 mb-6">#{orderNumber}</p>
        <p className="text-gray-600 text-sm leading-relaxed mb-10">
          Ваш заказ передан на кухню. Мы приготовим всё как можно быстрее. Приятного аппетита! 🍽️
        </p>
        <button
          onClick={handleBack}
          className="w-full bg-green-600 hover:bg-green-700 text-white py-4 rounded-2xl font-semibold text-lg transition-colors shadow-lg"
        >
          Вернуться в меню
        </button>
      </motion.div>
    </div>
  );
}
