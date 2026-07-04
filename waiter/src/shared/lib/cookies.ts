export function setCookie(name: string, value: string, hours: number) {
  const date = new Date();
  date.setTime(date.getTime() + (hours * 60 * 60 * 1000));
  const expires = "expires=" + date.toUTCString();
  const maxAge = "Max-Age=" + (hours * 60 * 60);
  document.cookie = `${name}=${value}; ${expires}; ${maxAge}; path=/; SameSite=Lax`;
  // Also persist in localStorage as fallback (PWA / mobile browser cookie clearing)
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(name, value);
  }
}

export function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    const cookieVal = parts.pop()?.split(';').shift() || null;
    if (cookieVal) return cookieVal;
  }
  // Fallback to localStorage if cookie was cleared
  if (typeof localStorage !== "undefined") {
    return localStorage.getItem(name);
  }
  return null;
}

export function deleteCookie(name: string) {
  document.cookie = name + '=; Max-Age=-99999999;path=/;';
  if (typeof localStorage !== "undefined") {
    localStorage.removeItem(name);
  }
}
