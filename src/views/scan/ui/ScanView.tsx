"use client";

import { Suspense, useState, useRef, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { scanQr } from "@/shared/api";
import { Scanner } from "@yudiel/react-qr-scanner";

type CameraStatus = "requesting" | "granted" | "denied" | "unsupported";

export function ScanView() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-black flex items-center justify-center text-ink-subtle">Загрузка...</div>}>
      <QRScannerPage />
    </Suspense>
  );
}

function QRScannerPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = searchParams.get("returnTo");
  const guestIdx = searchParams.get("guestIdx");

  const [payload, setPayload] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [isManual, setIsManual] = useState(false);
  const [cameraStatus, setCameraStatus] = useState<CameraStatus>("requesting");

  // Protect against multiple scans while processing
  const scanningRef = useRef(false);
  const streamRef = useRef<MediaStream | null>(null);

  // Request camera permission on mount
  useEffect(() => {
    async function requestCamera() {
      // Check if getUserMedia is available (requires HTTPS or localhost)
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setCameraStatus("unsupported");
        setIsManual(true);
        return;
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
        });
        // Permission granted — stop the test stream, let Scanner manage its own
        streamRef.current = stream;
        stream.getTracks().forEach((track) => track.stop());
        setCameraStatus("granted");
      } catch (err: any) {
        console.error("Camera access error:", err);
        if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
          setCameraStatus("denied");
        } else {
          setCameraStatus("unsupported");
        }
        setIsManual(true);
      }
    }

    requestCamera();

    return () => {
      // Cleanup
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, []);

  const processPayload = async (code: string) => {
    if (scanningRef.current || !code) return;
    scanningRef.current = true;
    setLoading(true);
    setError("");

    try {
      const res = await scanQr(code);
      if (res.client_id) {
        if (returnTo) {
          // Return to wizard with scanned client info
          const sep = returnTo.includes("?") ? "&" : "?";
          router.push(`${returnTo}${sep}scannedClientId=${res.client_id}&scannedGuestIdx=${guestIdx || 0}`);
        } else {
          router.push(`/dashboard/basket/${res.client_id}`);
        }
      } else {
        setError("Не удалось привязать стол или клиент не найден.");
        scanningRef.current = false;
      }
    } catch (err: any) {
      setError(err.message || "Ошибка сканирования или неверный QR");
      scanningRef.current = false;
    } finally {
      setLoading(false);
    }
  };

  const handleScanSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await processPayload(payload);
  };

  const onScanSuccess = (detectedCodes: any) => {
    let codeText = "";
    if (Array.isArray(detectedCodes) && detectedCodes.length > 0) {
      codeText = detectedCodes[0].rawValue || detectedCodes[0].text;
    } else if (detectedCodes && detectedCodes.text) {
      codeText = detectedCodes.text;
    } else if (typeof detectedCodes === "string") {
      codeText = detectedCodes;
    }

    if (codeText) {
      setPayload(codeText);
      processPayload(codeText);
    }
  };

  const renderCameraHint = () => {
    if (cameraStatus === "requesting") {
      return (
        <div className="w-full max-w-sm aspect-square rounded-3xl flex flex-col items-center justify-center mb-6 bg-gray-900 border-2 border-orange-500">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-orange-500 mb-4"></div>
          <p className="text-orange-400 font-medium">Запрос доступа к камере...</p>
          <p className="text-ink-muted text-xs mt-2">Нажмите «Разрешить» в диалоге браузера</p>
        </div>
      );
    }

    if (cameraStatus === "denied") {
      return (
        <div className="w-full max-w-sm p-6 rounded-2xl bg-red-950/30 border border-red-800 mb-6 text-center">
          <p className="text-red-400 font-medium mb-2">⛔ Доступ к камере запрещён</p>
          <p className="text-ink-subtle text-sm">
            Разрешите доступ к камере в настройках браузера, затем обновите страницу.
          </p>
        </div>
      );
    }

    if (cameraStatus === "unsupported") {
      return (
        <div className="w-full max-w-sm p-6 rounded-2xl bg-yellow-950/30 border border-yellow-800 mb-6 text-center">
          <p className="text-yellow-400 font-medium mb-2">📷 Камера недоступна</p>
          <p className="text-ink-subtle text-sm">
            Камера требует HTTPS-соединения. Используйте ручной ввод кода ниже.
          </p>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="min-h-screen bg-black text-white flex flex-col">
      <header className="p-4 flex items-center border-b border-gray-800">
        <button onClick={() => router.back()} className="text-ink-subtle p-2 -ml-2">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
        </button>
        <h1 className="text-lg font-medium mx-auto">Сканирование QR</h1>
        <div className="w-6"></div>
      </header>

      <main className="flex-1 flex flex-col items-center p-6 mt-4">
        {!isManual && cameraStatus === "granted" ? (
          <div className="w-full max-w-sm flex flex-col items-center">
            <div className="w-full max-w-sm aspect-square rounded-3xl overflow-hidden shadow-[0_0_20px_rgba(255,165,0,0.2)] border-2 border-orange-500 mb-6 bg-gray-900">
               <Scanner
                 onScan={onScanSuccess}
                 onError={() => setError("Ошибка камеры. Попробуйте обновить страницу.")}
               />
            </div>
            {loading && <p className="text-orange-500 font-medium animate-pulse mb-4">Обрабатываем QR...</p>}
            {error && <p className="text-red-400 text-sm text-center mb-4 bg-red-950/40 p-3 rounded-lg">{error}</p>}
            <button
              onClick={() => setIsManual(true)}
              className="mt-2 text-ink-subtle text-sm hover:text-white transition"
            >
              Ввести код вручную (Payload)
            </button>
          </div>
        ) : !isManual && cameraStatus === "requesting" ? (
          <div className="w-full max-w-sm flex flex-col items-center">
            {renderCameraHint()}
          </div>
        ) : (
          <div className="w-full max-w-sm flex flex-col items-center">
            {renderCameraHint()}

            <form onSubmit={handleScanSubmit} className="w-full max-w-sm space-y-4">
              <input
                type="text"
                value={payload}
                onChange={(e) => setPayload(e.target.value)}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl p-4 text-center text-lg text-white placeholder-gray-500 focus:outline-none focus:border-orange-500"
                placeholder="Payload: or123"
                required
                autoFocus
              />
              {error && <p className="text-red-400 text-sm text-center mb-2">{error}</p>}
              <button
                 type="submit"
                 disabled={loading}
                 className="w-full bg-orange-500 hover:bg-orange-600 text-white rounded-xl py-4 font-semibold transition active:scale-95 disabled:opacity-50"
              >
                 {loading ? "Поиск..." : "Отправить"}
              </button>

              {cameraStatus === "granted" && (
                <button
                  type="button"
                  onClick={() => setIsManual(false)}
                  className="w-full mt-4 text-ink-subtle text-sm hover:text-white transition"
                >
                  Вернуться к камере
                </button>
              )}
            </form>
          </div>
        )}
      </main>
    </div>
  );
}
