import AppRouter from "./shell/AppRouter";

/**
 * Cold Case — root component.
 *
 * Routing and shell live under `src/shell/`. Add a feature: create
 * `src/features/<name>/`, add a route to `src/shell/routes.ts`, then a
 * branch to `AppRouter`.
 */

export default function App() {
  return <AppRouter />;
}
