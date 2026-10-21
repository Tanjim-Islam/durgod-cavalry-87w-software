import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import App from "./App";
import { Boot } from "./Boot";
import { ErrorBoundary } from "./components/ErrorBoundary";

createRoot(document.getElementById("root")!).render(<StrictMode><ErrorBoundary><Boot><App /></Boot></ErrorBoundary></StrictMode>);
