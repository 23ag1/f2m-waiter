import { useState } from 'react';
import { ChevronLeft, ChevronDown, ChevronUp, Minus, Plus, Sparkles, LucideIcon } from 'lucide-react';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { useBasket } from '../context/BasketContext';

interface MenuDetailProps {
  item: {
    id: number;
    name: string;
    price: number;
    weight: string;
    image: string;
    description: string;
    emoji?: string | null;
  };
  tags: Array<{ text: string; color: string }>;
  displayIcon?: { icon: LucideIcon; color: string } | null;
  personalizedComment: string;
  onBack: () => void;
}

const colorClasses = {
  green: 'bg-green-100 text-green-700',
  pink: 'bg-pink-100 text-pink-700',
  blue: 'bg-blue-100 text-blue-700',
  orange: 'bg-orange-100 text-orange-700',
  red: 'bg-red-100 text-red-700',
  gray: 'bg-gray-100 text-gray-700',
};

export default function MenuDetail({ item, tags, displayIcon, personalizedComment, onBack }: MenuDetailProps) {
  const [quantity, setQuantity] = useState(1);
  const [isCommentExpanded, setIsCommentExpanded] = useState(true);
  const IconComponent = displayIcon?.icon;
  const { addItem } = useBasket();

  const increment = () => setQuantity(q => q + 1);
  const decrement = () => setQuantity(q => Math.max(1, q - 1));

  const handleAddToBasket = () => {
    // Add the item multiple times based on quantity
    for (let i = 0; i < quantity; i++) {
      addItem({
        id: item.id,
        name: item.name,
        price: item.price,
        weight: item.weight,
        image: item.image,
      });
    }
    // Reset quantity after adding
    setQuantity(1);
    // Go back to menu
    onBack();
  };

  return (
    <div className="min-h-screen bg-white pb-32">
      {/* Back button */}
      <button
        onClick={onBack}
        className="absolute top-4 left-4 w-11 h-11 bg-white rounded-full shadow-lg flex items-center justify-center z-10 hover:bg-gray-50 transition-all"
      >
        <ChevronLeft className="w-6 h-6" />
      </button>

      {/* Hero Image */}
      <div className="relative h-80 bg-gray-100">
        <ImageWithFallback
          src={item.image}
          alt={item.name}
          className="w-full h-full object-cover"
          loading="eager"
        />

        {/* Icon display */}
        {displayIcon && IconComponent && (
          <div className={`absolute bottom-4 left-4 w-12 h-12 rounded-full flex items-center justify-center ${
            displayIcon.color === 'red' ? 'bg-red-100' : 'bg-green-100'
          }`}>
            <IconComponent className={`w-6 h-6 ${
              displayIcon.color === 'red' ? 'text-red-600' : 'text-green-600'
            }`} />
          </div>
        )}
      </div>

      {/* Content */}
      <div className="px-4 py-5 space-y-5">
        {/* Title and Price */}
        <div>
          <h1 className="text-2xl font-bold mb-2">
            {item.name.split(',')[0]}
            {item.name.includes(',') && `, ${item.weight}`}
          </h1>
          
          {/* Tags under title */}
          <div className="flex flex-wrap gap-2 mb-3">
            {tags.slice(0, 3).map((tag, index) => (
              <div
                key={index}
                className={`px-3 py-1.5 rounded-full text-xs font-medium ${colorClasses[tag.color as keyof typeof colorClasses]}`}
              >
                <span>{tag.text}</span>
              </div>
            ))}
          </div>
          
          <div className="text-2xl font-bold">
            {item.price}
            <span className="text-gray-400 text-xl">,99 ₽</span>
          </div>
        </div>

        {/* AI Personalized Comment */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-5 h-5 text-purple-600" />
            <h2 className="font-semibold text-base">ИИ-комментарий</h2>
          </div>

          {isCommentExpanded && (
            <div className="bg-green-50 rounded-2xl p-4">
              <p className="text-green-800 leading-relaxed text-sm">
                {personalizedComment}
              </p>

              <button
                onClick={() => setIsCommentExpanded(false)}
                className="flex items-center gap-1 mt-3 text-green-700 text-sm font-medium hover:opacity-70 transition-opacity"
              >
                <span>свернуть</span>
                <ChevronUp className="w-4 h-4" />
              </button>
            </div>
          )}

          {!isCommentExpanded && (
            <button
              onClick={() => setIsCommentExpanded(true)}
              className="flex items-center gap-1 text-green-700 text-sm font-medium hover:opacity-70 transition-opacity"
            >
              <span>развернуть</span>
              <ChevronDown className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Description */}
        <div>
          <h2 className="text-gray-500 text-sm mb-2">Описание</h2>
          <p className="text-gray-700 leading-relaxed text-sm">
            {item.description}
          </p>
        </div>
      </div>

      {/* Bottom bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 flex gap-3 safe-area-bottom">
        {/* Quantity selector */}
        <div className="flex items-center gap-3 bg-green-100 rounded-full px-4 py-2.5">
          <button
            onClick={decrement}
            className="w-9 h-9 flex items-center justify-center hover:opacity-70 transition-all"
          >
            <Minus className="w-5 h-5 text-green-700" />
          </button>
          <span className="text-lg font-semibold min-w-[2rem] text-center text-green-700">
            {quantity}
          </span>
          <button
            onClick={increment}
            className="w-9 h-9 flex items-center justify-center hover:opacity-70 transition-all"
          >
            <Plus className="w-5 h-5 text-green-700" />
          </button>
        </div>

        {/* Add to cart button */}
        <button
          onClick={handleAddToBasket}
          className="flex-1 bg-green-600 text-white rounded-full py-3.5 text-base font-semibold hover:bg-green-700 transition-all"
        >
          Добавить
        </button>
      </div>
    </div>
  );
}