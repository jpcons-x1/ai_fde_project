import { defineConfig } from "@playwright/test";

// The tests run on their own backend and database, apart from `npm run dev`.
const backend = "http://127.0.0.1:8001";

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  use: { baseURL: "http://localhost:5174" },
  webServer: [
    {
      command:
        "uv run -m backend.seed && uv run -m uvicorn backend.main:app --port 8001",
      url: `${backend}/api/health`,
      env: { UNDERCOVER_DB: "e2e/undercover-e2e.db", BACKEND_URL: backend },
      reuseExistingServer: false,
    },
    {
      command: "npx vite dashboard --port 5174 --strictPort",
      url: "http://localhost:5174",
      env: { BACKEND_URL: backend },
      reuseExistingServer: false,
    },
  ],
});
