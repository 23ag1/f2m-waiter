import { createBrowserRouter } from "react-router";
import RootLayout from "./layouts/RootLayout";
import Onboarding from "./pages/Onboarding";
import Menu from "./pages/Menu";
import BasketPage from "./pages/BasketPage";
import OrderSuccess from "./pages/OrderSuccess";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: RootLayout,
    children: [
      {
        index: true,
        Component: Onboarding,
      },
      {
        path: "menu",
        Component: Menu,
      },
      {
        path: "basket",
        Component: BasketPage,
      },
      {
        path: "order-success",
        Component: OrderSuccess,
      },
    ],
  },
]);