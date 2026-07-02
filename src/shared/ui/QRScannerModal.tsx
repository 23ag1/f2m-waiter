"use client";

import { useEffect, useRef, useState } from "react";
import { Scanner } from "@yudiel/react-qr-scanner";

type CameraStatus = "requesting" | "granted" | "denied" | "unsupported";

/** Full-screen QR check-in scanner. `onCheckin` fires when a code is captured. */
export function QRScannerModal({ onClose, onCheckin }: { onClose: () => void; onCheckin: () => void }) {
  const [cameraStatus, setCameraStatus] = useState<CameraStatus>("requesting");
  const [isManual, setIsManual] = useState(false);
  const [payload, setPayload] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const scanningRef = useRef(false);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    async function requestCamera() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setCameraStatus("unsupported"); setIsManual(true); return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        streamRef.current = stream;
        stream.getTracks().forEach((t) => t.stop());
        setCameraStatus("granted");
      } catch {
        setCameraStatus("denied"); setIsManual(true);
      }
    }
    requestCamera();
    return () => { streamRef.current?.getTracks().forEach((t) => t.stop()); };
  }, []);

  const processPayload = async (code: string) => {
    if (scanningRef.current || !code) return;
    scanningRef.current = true;
    setLoading(true); setError("");
    await new Promise((r) => setTimeout(r, 500));
    setLoading(false);
    onCheckin();
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const onScanSuccess = (detectedCodes: any) => {
    let code = "";
    if (Array.isArray(detectedCodes) && detectedCodes.length > 0) code = detectedCodes[0].rawValue || detectedCodes[0].text;
    else if (detectedCodes?.text) code = detectedCodes.text;
    else if (typeof detectedCodes === "string") code = detectedCodes;
    if (code) processPayload(code);
  };

  return (
    <div className="fixed inset-0 bg-black z-50 flex flex-col">
      <div className="flex items-center p-4 border-b border-gray-800">
        <button onClick={onClose} className="text-ink-subtle p-1 -ml-1">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
        </button>
        <span className="text-white text-base font-semibold ml-3">Сканирование QR</span>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center p-6">
        {!isManual && cameraStatus === "granted" ? (
          <>
            <div className="w-full max-w-xs aspect-square rounded-3xl overflow-hidden border-2 border-orange-500 shadow-[0_0_20px_rgba(249,115,22,0.3)] mb-6 bg-gray-900">
              <Scanner onScan={onScanSuccess} onError={() => setError("Ошибка камеры. Попробуйте обновить страницу.")} />
            </div>
            {loading && <p className="text-orange-400 font-medium animate-pulse mb-4">Определяем гостя...</p>}
            {error && <p className="text-red-400 text-sm text-center mb-4">{error}</p>}
            <button onClick={() => setIsManual(true)} className="text-ink-muted text-sm hover:text-white transition">
              Ввести код вручную
            </button>
          </>
        ) : !isManual && cameraStatus === "requesting" ? (
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 rounded-full border-2 border-orange-500 border-t-transparent animate-spin" />
            <p className="text-ink-subtle text-sm">Запрос доступа к камере...</p>
          </div>
        ) : (
          <div className="w-full max-w-xs flex flex-col gap-4">
            {cameraStatus === "denied" && (
              <div className="p-4 rounded-2xl bg-red-950/30 border border-red-800 text-center">
                <p className="text-red-400 font-medium mb-1">⛔ Доступ к камере запрещён</p>
                <p className="text-ink-subtle text-sm">Разрешите доступ в настройках браузера и обновите страницу.</p>
              </div>
            )}
            {cameraStatus === "unsupported" && (
              <div className="p-4 rounded-2xl bg-yellow-950/30 border border-yellow-800 text-center">
                <p className="text-yellow-400 font-medium mb-1">📷 Камера недоступна</p>
                <p className="text-ink-subtle text-sm">Требуется HTTPS. Используйте ручной ввод.</p>
              </div>
            )}
            <form onSubmit={(e) => { e.preventDefault(); processPayload(payload); }} className="flex flex-col gap-3">
              <input
                type="text" value={payload} onChange={(e) => setPayload(e.target.value)}
                placeholder="Код QR (например: or123)"
                className="w-full bg-gray-900 border border-gray-700 rounded-xl p-4 text-center text-white text-base placeholder-gray-500 focus:outline-none focus:border-orange-500"
                autoFocus required
              />
              {error && <p className="text-red-400 text-sm text-center">{error}</p>}
              <button type="submit" disabled={loading}
                className="w-full bg-orange-500 rounded-xl py-4 text-white font-semibold text-sm transition active:scale-95 disabled:opacity-50">
                {loading ? "Поиск..." : "Чекин"}
              </button>
              {cameraStatus === "granted" && (
                <button type="button" onClick={() => setIsManual(false)} className="text-ink-muted text-sm hover:text-white transition">
                  Вернуться к камере
                </button>
              )}
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
