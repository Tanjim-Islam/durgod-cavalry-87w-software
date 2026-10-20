import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import App from "./App";
import { Boot } from "./Boot";

createRoot(document.getElementById("root")!).render(<StrictMode><Boot><App /></Boot></StrictMode>);
