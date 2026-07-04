import { X, Plus, Minus, Trash2, ShoppingBag } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useBasket } from '../context/BasketContext';

interface BasketProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function Basket({ isOpen, onClose }: BasketProps) {
  const { items, updateQuantity, removeItem, getTotalPrice, clearBasket, placeOrder } = useBasket();
  const navigate = useNavigate();

  const [orderNumber] = useState(() => Math.floor(1000 + Math.random() * 9000));

  const handlePlaceOrder = () => {
    placeOrder();
    onClose();
    navigate('/order-success', { state: { orderNumber } });
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/50 z-50"
          />

          {/* Basket Panel */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="fixed top-0 right-0 h-full w-full sm:w-96 bg-white z-50 shadow-2xl flex flex-col relative"
          >
            {/* Header */}
            <div className="bg-green-600 text-white px-5 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <ShoppingBag className="w-6 h-6" />
                <div>
                  <h2 className="text-xl font-bold">Корзина</h2>
                  <p className="text-xs text-green-100">
                    {items.length === 0 ? 'Пусто' : `${items.length} ${items.length === 1 ? 'позиция' : 'позиций'}`}
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="w-10 h-10 hover:bg-white/20 rounded-full flex items-center justify-center transition-colors"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Items List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {items.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center px-6">
                  <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                    <ShoppingBag className="w-10 h-10 text-gray-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">Корзина пуста</h3>
                  <p className="text-sm text-gray-500">
                    Добавьте блюда из меню, чтобы начать заказ
                  </p>
                </div>
              ) : (
                <>
                  {items.map((item) => (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, x: -100 }}
                      className="bg-white border border-gray-200 rounded-xl p-3 shadow-sm"
                    >
                      <div className="flex gap-3">
                        {/* Image */}
                        <div className="w-20 h-20 rounded-lg overflow-hidden bg-gray-100 flex-shrink-0">
                          <img
                            src={item.image}
                            alt={item.name}
                            className="w-full h-full object-cover"
                          />
                        </div>

                        {/* Details */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2 mb-2">
                            <div className="flex-1 min-w-0">
                              <h3 className="font-semibold text-sm line-clamp-2 leading-tight mb-1">
                                {item.name}
                              </h3>
                              <p className="text-xs text-gray-500">{item.weight}</p>
                            </div>
                            <button
                              onClick={() => removeItem(item.id)}
                              className="w-7 h-7 hover:bg-red-50 rounded-full flex items-center justify-center transition-colors flex-shrink-0"
                            >
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </button>
                          </div>

                          {/* Quantity and Price */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => updateQuantity(item.id, item.quantity - 1)}
                                className="w-7 h-7 bg-gray-100 hover:bg-gray-200 rounded-full flex items-center justify-center transition-colors"
                              >
                                <Minus className="w-3.5 h-3.5" />
                              </button>
                              <span className="w-8 text-center font-semibold text-sm">
                                {item.quantity}
                              </span>
                              <button
                                onClick={() => updateQuantity(item.id, item.quantity + 1)}
                                className="w-7 h-7 bg-gray-100 hover:bg-gray-200 rounded-full flex items-center justify-center transition-colors"
                              >
                                <Plus className="w-3.5 h-3.5" />
                              </button>
                            </div>
                            <span className="font-bold text-sm">
                              {item.price * item.quantity}₽
                            </span>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ))}

                  {/* Clear basket button */}
                  {items.length > 0 && (
                    <button
                      onClick={clearBasket}
                      className="w-full py-2 text-sm text-red-600 hover:text-red-700 font-medium transition-colors"
                    >
                      Очистить корзину
                    </button>
                  )}
                </>
              )}
            </div>

            {/* Footer with Total */}
            {items.length > 0 && (
              <div className="border-t border-gray-200 p-4 space-y-3 bg-gray-50">
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Итого:</span>
                  <span className="text-2xl font-bold text-gray-900">
                    {getTotalPrice()}₽
                  </span>
                </div>
                <button
                  onClick={handlePlaceOrder}
                  className="w-full bg-green-600 hover:bg-green-700 text-white py-3.5 rounded-xl font-semibold transition-colors shadow-lg"
                >
                  Оформить заказ
                </button>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
