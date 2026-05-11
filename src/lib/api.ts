// Barrel re-exports from `./api/`. Imports stay stable as the surface grows.

export { http } from "./api/client";
// Add named re-exports here as client.ts grows:
// export { listEmployees, getEmployee, createEmployee } from "./api/client";
