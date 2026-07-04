import { useNavigate } from 'react-router';
import { useState } from 'react';
import { ArrowLeft, ShoppingBag, Plus, Minus, Trash2 } from 'lucide-react';
import { useBasket } from '../context/BasketContext';

export default function BasketPage() {
  const navigate = useNavigate();
  const { items, updateQuantity, removeItem, getTotalPrice, clearBasket, placeOrder } = useBasket();
  const [orderNumber] = useState(() => Math.floor(1000 + Math.random() * 9000));

  const handlePlaceOrder = () => {
    placeOrder();
    navigate('/order-success', { state: { orderNumber } });
  };

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Header */}
      <div className="bg-green-600 text-white px-5 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/menu')}
            className="w-10 h-10 hover:bg-white/20 rounded-full flex items-center justify-center transition-colors"
          >
            <ArrowLeft className="w-6 h-6" />
          </button>
          <ShoppingBag className="w-6 h-6" />
          <div>
            <h2 className="text-xl font-bold">Корзина</h2>
            <p className="text-xs text-green-100">
              {items.length === 0 ? 'Пусто' : `${items.length} ${items.length === 1 ? 'позиция' : 'позиций'}`}
            </p>
          </div>
        </div>
      </div>

      {/* Items */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {items.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-6 pt-20">
            <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mb-4">
              <ShoppingBag className="w-10 h-10 text-gray-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-800 mb-2">Корзина пуста</h3>
            <p className="text-sm text-gray-500 mb-6">Добавьте блюда из меню, чтобы начать заказ</p>
            <button
              onClick={() => navigate('/menu')}
              className="bg-green-600 text-white px-6 py-3 rounded-xl font-semibold"
            >
              Перейти в меню
            </button>
          </div>
        ) : (
          <>
            {items.map((item) => (
              <div key={item.id} className="bg-white border border-gray-200 rounded-xl p-3 shadow-sm">
                <div className="flex gap-3">
                  <div className="w-20 h-20 rounded-lg overflow-hidden bg-gray-100 flex-shrink-0">
                    <img src={item.image} alt={item.name} className="w-full h-full object-cover" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold text-sm line-clamp-2 leading-tight mb-1">{item.name}</h3>
                        <p className="text-xs text-gray-500">{item.weight}</p>
                      </div>
                      <button
                        onClick={() => removeItem(item.id)}
                        className="w-7 h-7 hover:bg-red-50 rounded-full flex items-center justify-center transition-colors flex-shrink-0"
                      >
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </button>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => updateQuantity(item.id, item.quantity - 1)}
                          className="w-7 h-7 bg-gray-100 hover:bg-gray-200 rounded-full flex items-center justify-center transition-colors"
                        >
                          <Minus className="w-3.5 h-3.5" />
                        </button>
                        <span className="w-8 text-center font-semibold text-sm">{item.quantity}</span>
                        <button
                          onClick={() => updateQuantity(item.id, item.quantity + 1)}
                          className="w-7 h-7 bg-gray-100 hover:bg-gray-200 rounded-full flex items-center justify-center transition-colors"
                        >
                          <Plus className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <span className="font-bold text-sm">{item.price * item.quantity}₽</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
            <button
              onClick={clearBasket}
              className="w-full py-2 text-sm text-red-600 hover:text-red-700 font-medium transition-colors"
            >
              Очистить корзину
            </button>
          </>
        )}
      </div>

      {/* Footer */}
      {items.length > 0 && (
        <div className="border-t border-gray-200 p-4 space-y-3 bg-gray-50">
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Итого:</span>
            <span className="text-2xl font-bold text-gray-900">{getTotalPrice()}₽</span>
          </div>
          <button
            onClick={handlePlaceOrder}
            className="w-full bg-green-600 hover:bg-green-700 text-white py-3.5 rounded-xl font-semibold transition-colors shadow-lg"
          >
            Оформить заказ
          </button>
        </div>
      )}
    </div>
  );
}
