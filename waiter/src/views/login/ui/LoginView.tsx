"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { loginWaiter, registerWaiter } from "@/shared/api";
import { setCookie, getCookie, deleteCookie } from "@/shared/lib/cookies";

type Tab = "login" | "register";

export function LoginView() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [autoLogging, setAutoLogging] = useState(false);

  // Login fields
  const [pin, setPin] = useState("");

  // Register fields
  const [regPassword, setRegPassword] = useState("");
  const [regName, setRegName] = useState("");
  const [regPin, setRegPin] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await loginWaiter(pin);
      if (res.success) {
        setCookie("waiter_token", res.waiter_token, 720);
        localStorage.setItem("waiter_pin", pin);
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    if (regPin.length !== 5 || !/^\d{5}$/.test(regPin)) {
      setError("PIN должен быть 5-значным числом");
      setLoading(false);
      return;
    }

    try {
      const res = await registerWaiter(regPassword, regName, regPin);
      if (res.success) {
        setCookie("waiter_token", res.waiter_token, 720);
        localStorage.setItem("waiter_pin", regPin);
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Ошибка регистрации");
    } finally {
      setLoading(false);
    }
  };

  // Show loading while auto-login in progress
  if (autoLogging) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-inset">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-hair border-t-black rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-ink-subtle">Вход...</p>
        </div>
      </div>
    );
  }

  if (tab === "login") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-between bg-surface py-16 px-6">
        {/* Logo area */}
        <div className="flex-1 flex items-center justify-center">
          <svg width="80" height="56" viewBox="0 0 80 56" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M40 28C40 28 8 10 8 28C8 46 40 28 40 28Z" fill="#2C3333" opacity="0.9"/>
            <path d="M40 28C40 28 72 10 72 28C72 46 40 28 40 28Z" fill="#2C3333" opacity="0.9"/>
          </svg>
        </div>

        {/* Bottom actions */}
        <div className="w-full max-w-sm space-y-3">
          {error && <p className="text-sm text-red-500 text-center">{error}</p>}
          <form onSubmit={handleLogin} className="space-y-3">
            <input
              type="number"
              inputMode="numeric"
              pattern="[0-9]*"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              className="w-full rounded-2xl border border-hair bg-inset p-4 text-lg text-center tracking-[0.3em] focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100 placeholder-gray-300"
              placeholder="• • • • •"
              maxLength={5}
              required
            />
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-2xl bg-blue-500 px-4 py-4 text-base font-semibold text-white transition active:scale-[0.98] disabled:opacity-70 shadow-md"
            >
              {loading ? "Вход..." : "Начать"}
            </button>
          </form>
          <button
            onClick={() => { setTab("register"); setError(""); }}
            className="w-full text-center text-blue-500 font-medium py-2"
          >
            Регистрация
          </button>
          <p className="text-center text-ink-subtle text-xs pb-2">Версия 1.0.0</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-surface py-16 px-6">
      <div className="flex items-center mb-6">
        <button onClick={() => { setTab("login"); setError(""); }} className="text-blue-500 font-medium flex items-center gap-1">
          <ChevronLeft className="h-5 w-5" />
          Назад
        </button>
      </div>
      <h1 className="text-3xl font-bold text-ink mb-8">Регистрация</h1>

      <form onSubmit={handleRegister} className="space-y-4 max-w-sm w-full">
        <div>
          <label className="mb-2 block text-sm font-medium text-ink-muted">Пароль ресторана</label>
          <input
            type="password"
            value={regPassword}
            onChange={(e) => setRegPassword(e.target.value)}
            className="w-full rounded-2xl border border-hair bg-inset p-4 text-base focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            placeholder="Получите у администратора"
            required
          />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium text-ink-muted">Ваше имя</label>
          <input
            type="text"
            value={regName}
            onChange={(e) => setRegName(e.target.value)}
            className="w-full rounded-2xl border border-hair bg-inset p-4 text-base focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            placeholder="Как к вам обращаться"
            required
          />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium text-ink-muted">PIN-код (5 цифр)</label>
          <input
            type="number"
            inputMode="numeric"
            pattern="[0-9]*"
            value={regPin}
            onChange={(e) => { if (e.target.value.length <= 5) setRegPin(e.target.value); }}
            className="w-full rounded-2xl border border-hair bg-inset p-4 text-lg text-center tracking-[0.3em] focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            placeholder="• • • • •"
            maxLength={5}
            required
          />
        </div>
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button
          type="submit"
          disabled={loading || regPin.length !== 5}
          className="w-full rounded-2xl bg-blue-500 px-4 py-4 text-base font-semibold text-white transition active:scale-[0.98] disabled:opacity-70 shadow-md"
        >
          {loading ? "Регистрация..." : "Зарегистрироваться"}
        </button>
      </form>
    </div>
  );
}
