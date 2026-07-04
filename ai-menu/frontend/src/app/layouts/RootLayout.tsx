import { Outlet } from 'react-router';
import { PreferencesProvider } from '../context/PreferencesContext';
import { BasketProvider } from '../context/BasketContext';

export default function RootLayout() {
  return (
    <PreferencesProvider>
      <BasketProvider>
        <Outlet />
      </BasketProvider>
    </PreferencesProvider>
  );
}