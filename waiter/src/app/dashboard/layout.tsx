import { TourOverlay } from "@/features/onboarding";

// Dashboard-wide layout: mounts the onboarding tour overlay so it can span the
// dashboard, profile, settings and order-card screens.
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <TourOverlay />
    </>
  );
}
