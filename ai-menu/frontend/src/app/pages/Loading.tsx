import { useEffect } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'motion/react';
import { Sparkles, ChefHat, Utensils } from 'lucide-react';

export default function Loading() {
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => {
      navigate('/menu');
    }, 3500);

    return () => clearTimeout(timer);
  }, [navigate]);

  const iconVariants = {
    hidden: { opacity: 0, scale: 0 },
    visible: (i: number) => ({
      opacity: 1,
      scale: 1,
      transition: {
        delay: i * 0.2,
        duration: 0.5,
        type: "spring",
        stiffness: 200,
      }
    }),
  };

  const textVariants = {
    hidden: { opacity: 0 },
    visible: (i: number) => ({
      opacity: [0, 1, 1, 0],
      transition: {
        delay: i * 0.8,
        duration: 2.4,
        times: [0, 0.2, 0.8, 1],
        repeat: Infinity,
      }
    }),
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-white flex items-center justify-center p-6">
      <div className="text-center">
        <motion.div className="flex justify-center gap-6 mb-12">
          <motion.div
            custom={0}
            variants={iconVariants}
            initial="hidden"
            animate="visible"
            className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center"
          >
            <Sparkles className="w-8 h-8 text-green-600" />
          </motion.div>
          
          <motion.div
            custom={1}
            variants={iconVariants}
            initial="hidden"
            animate="visible"
            className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center"
          >
            <ChefHat className="w-8 h-8 text-green-600" />
          </motion.div>
          
          <motion.div
            custom={2}
            variants={iconVariants}
            initial="hidden"
            animate="visible"
            className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center"
          >
            <Utensils className="w-8 h-8 text-green-600" />
          </motion.div>
        </motion.div>

        <div className="space-y-3">
          <motion.p
            custom={0}
            variants={textVariants}
            initial="hidden"
            animate="visible"
            className="text-2xl font-semibold"
          >
            Анализируем ваши предпочтения...
          </motion.p>

          <motion.p
            custom={1}
            variants={textVariants}
            initial="hidden"
            animate="visible"
            className="text-2xl font-semibold"
          >
            Подбираем идеальные блюда...
          </motion.p>

          <motion.p
            custom={2}
            variants={textVariants}
            initial="hidden"
            animate="visible"
            className="text-2xl font-semibold"
          >
            Готовим меню специально для вас...
          </motion.p>
        </div>

        <motion.div
          className="mt-12"
          animate={{
            scale: [1, 1.2, 1],
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          <div className="w-2 h-2 bg-green-600 rounded-full mx-auto" />
        </motion.div>
      </div>
    </div>
  );
}
